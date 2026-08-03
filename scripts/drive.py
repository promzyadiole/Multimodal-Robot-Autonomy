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
    W A S D        the same, if you prefer letters
    SPACE          stop
    + / -          faster / slower
    q              quit

Velocity is released a short time after the last keypress, so a forgotten
session cannot drive the robot away -- a real failure here, where a teleop left
open crept the robot 588 mm in 60 s with nobody at the keyboard.

Publishing runs on its own thread. The first version drove the ROS timer from
the same loop that waited on the keyboard, so the publish rate collapsed to 5 Hz
and the plugin saw a near-static command.
"""
from __future__ import annotations

import os
import select
import sys
import termios
import threading
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
KEY_TIMEOUT = 0.4           # seconds a keypress keeps commanding
PUBLISH_HZ = 20.0

# Arrow keys arrive as ESC [ A .. D. Letters are offered as an alternative
# because a few terminals swallow the escape sequence entirely.
ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}
LETTERS = {"w": "up", "s": "down", "a": "left", "d": "right",
           "W": "up", "S": "down", "A": "left", "D": "right"}


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


def read_key(timeout: float = 0.05) -> str | None:
    """Return a key name, decoding arrow escape sequences.

    Reads everything the terminal has buffered in one go rather than a byte at
    a time. Byte-at-a-time with a 20 ms inner timeout dropped arrow keys under
    load: the escape sequence arrived split, the reader gave up after the ESC,
    and the keypress was discarded.
    """
    if not select.select([sys.stdin], [], [], timeout)[0]:
        return None
    data = os.read(sys.stdin.fileno(), 32).decode(errors="ignore")
    if not data:
        return None
    if data[0] == "\x1b":
        # take the last arrow in the buffer, so held keys do not queue up
        for i in range(len(data) - 1, 0, -1):
            if data[i] in ARROWS and data[i - 1] == "[":
                return ARROWS[data[i]]
        return None
    ch = data[-1]
    return LETTERS.get(ch, ch)


def main() -> int:
    rclpy.init()
    node = Drive()

    # Spin on its own thread so the publish rate does not depend on how long
    # the keyboard read blocks.
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()

    interactive = sys.stdin.isatty()
    settings = termios.tcgetattr(sys.stdin) if interactive else None
    print("\r\n  arrow keys or WASD drive   SPACE stop   + / - speed   q quit\r\n"
          "  UP/DOWN straight, LEFT/RIGHT turn in place\r\n")
    try:
        if interactive:
            tty.setcbreak(sys.stdin.fileno())
        while rclpy.ok():
            k = read_key()
            if k is None:
                continue
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
            else:
                continue
            print(f"\r  speed {node.lin:.2f} m/s  {node.ang:.2f} rad/s"
                  f"   commanding ({node.x:+.2f}, {node.th:+.2f})       ", end="", flush=True)
    finally:
        if interactive and settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        # Order matters. Stop commanding, then take the executor down and wait
        # for the spin thread to actually exit before shutting rclpy down --
        # tearing the context out from under a live thread aborts the process.
        try:
            if rclpy.ok():
                node.x, node.th = 0.0, 0.0
                stop = Twist()
                for _ in range(10):
                    node.pub.publish(stop)
                    threading.Event().wait(0.02)
        except Exception:  # noqa: BLE001
            pass
        try:
            executor.shutdown()
            spinner.join(timeout=2.0)
        except Exception:  # noqa: BLE001
            pass
        try:
            node.destroy_node()
        except Exception:  # noqa: BLE001
            pass
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:  # noqa: BLE001
            pass
        print("\r\n  stopped.\r")
    return 0


if __name__ == "__main__":
    sys.exit(main())
