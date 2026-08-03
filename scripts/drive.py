#!/usr/bin/env python3
"""Drive the robot with the arrow keys.

    scripts/drive.sh

teleop_twist_keyboard uses a 3x3 letter grid whose corners deliberately mix
linear and angular velocity, so `u` and `m` curve rather than going straight,
and every unbound key silently stops the robot. It is also laid out for a US
keyboard. Arrow keys sit in the same place on every layout and each one commands
exactly one axis, which is what mapping needs: a clean straight line gives
slam_toolbox a far better scan match than a drifting arc.

    UP / DOWN      forward / back      (linear only)
    LEFT / RIGHT   rotate in place     (angular only)
    SPACE          stop
    + / -          faster / slower
    q              quit

Velocity is held while a key is down and released on a short timeout, so the
robot coasts to a stop rather than requiring an explicit stop keystroke.
"""
from __future__ import annotations

import os
import select
import sys
import termios
import tty

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

# Deliberately slow. The robot cruises at 0.35 m/s and its casters are fixed
# skids, so quick turns scrub instead of rolling; mapping wants gentle motion.
LINEAR_START = 0.08
ANGULAR_START = 0.3
LINEAR_MAX = 0.35
ANGULAR_MAX = 1.2
KEY_TIMEOUT = 0.25          # seconds a keypress keeps commanding
PUBLISH_HZ = 20.0

ESC = "\x1b"
ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}


class Drive(Node):
    def __init__(self) -> None:
        super().__init__("drive")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.lin = LINEAR_START
        self.ang = ANGULAR_START
        self.x = 0.0
        self.th = 0.0
        self.held = 0.0
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)

    def tick(self) -> None:
        now = self.get_clock().now().nanoseconds / 1e9
        if now - self.held > KEY_TIMEOUT:
            self.x, self.th = 0.0, 0.0
        t = Twist()
        t.linear.x = self.x
        t.angular.z = self.th
        self.pub.publish(t)

    def command(self, x: float, th: float) -> None:
        self.x, self.th = x, th
        self.held = self.get_clock().now().nanoseconds / 1e9


def read_key(timeout: float = 0.1) -> str | None:
    """Return a key name, decoding the escape sequences arrow keys emit."""
    if not select.select([sys.stdin], [], [], timeout)[0]:
        return None
    ch = sys.stdin.read(1)
    if ch != ESC:
        return ch
    if not select.select([sys.stdin], [], [], 0.02)[0]:
        return ESC
    if sys.stdin.read(1) != "[":
        return ESC
    return ARROWS.get(sys.stdin.read(1), None)


def main() -> int:
    rclpy.init()
    node = Drive()
    settings = termios.tcgetattr(sys.stdin)
    banner = (
        "\r\n  arrow keys drive   SPACE stop   + / - speed   q quit\r\n"
        "  UP/DOWN move straight, LEFT/RIGHT turn in place\r\n"
    )
    print(banner)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while rclpy.ok():
            k = read_key()
            if k == "q":
                break
            if k == "up":
                node.command(node.lin, 0.0)
            elif k == "down":
                node.command(-node.lin, 0.0)
            elif k == "left":
                node.command(0.0, node.ang)
            elif k == "right":
                node.command(0.0, -node.ang)
            elif k == " ":
                node.x, node.th = 0.0, 0.0
            elif k in ("+", "="):
                node.lin = min(LINEAR_MAX, node.lin * 1.15)
                node.ang = min(ANGULAR_MAX, node.ang * 1.15)
            elif k in ("-", "_"):
                node.lin = max(0.02, node.lin / 1.15)
                node.ang = max(0.05, node.ang / 1.15)
            if k:
                print(f"\r  linear {node.lin:.2f} m/s   angular {node.ang:.2f} rad/s"
                      f"   commanding ({node.x:+.2f}, {node.th:+.2f})      ", end="")
            rclpy.spin_once(node, timeout_sec=0.0)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        # Publish the stop only while the context is still valid. Exiting after
        # rclpy has shut down raised "publisher's context is invalid" and buried
        # the real error under a second traceback.
        try:
            if rclpy.ok():
                stop = Twist()
                for _ in range(10):
                    node.pub.publish(stop)
                    rclpy.spin_once(node, timeout_sec=0.01)
        except Exception:  # noqa: BLE001
            pass
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:  # noqa: BLE001
            pass
        print("\r\n  stopped.\r")
    return 0


if __name__ == "__main__":
    sys.exit(main())
