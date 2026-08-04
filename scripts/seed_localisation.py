#!/usr/bin/env python3
"""Tell AMCL where the robot is, then move it so the filter converges.

    scripts/seed.sh

AMCL starts with no idea where the robot is and `set_initial_pose` is false, so
until it is given a pose it publishes no map -> odom transform and every goal
fails to plan. RViz's "2D Pose Estimate" button does this by hand; this does it
from Gazebo's ground truth, which is exact.

The nudge afterwards is not optional. A particle filter only updates when the
robot moves past update_min_d / update_min_a, so a stationary robot keeps
whatever spread it was seeded with. Rotating in place is the cheapest way to
force updates and cannot collide with anything.
"""
from __future__ import annotations

import math
import subprocess
import sys
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav2_msgs.srv import ClearEntireCostmap


def truth() -> tuple[float, float, float] | None:
    try:
        out = subprocess.run(["gz", "model", "-m", "romr", "-p"],
                             capture_output=True, text=True, timeout=25).stdout.split()
        return (float(out[0]), float(out[1]), float(out[5])) if len(out) >= 6 else None
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    t = truth()
    if t is None:
        print("Gazebo is not running, or the robot is not spawned.")
        return 1
    x, y, yaw = t

    rclpy.init()
    node = rclpy.create_node("seed_localisation")
    # Without this the node stamps messages from the wall clock while the rest
    # of the system runs on simulation time, and AMCL answers with
    #   "Failed to transform initial pose in time ... requested 1785828275.18
    #    but the latest data is at 1514.31"
    # -- a unix epoch against a simulation clock. AMCL then falls back to an
    # identity odometry correction, which happens to be right only because the
    # robot is stationary while being seeded.
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    pose_pub = node.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
    vel_pub = node.create_publisher(Twist, "/cmd_vel", 10)
    time.sleep(1.5)

    m = PoseWithCovarianceStamped()
    m.header.frame_id = "map"
    m.pose.pose.position.x = x
    m.pose.pose.position.y = y
    m.pose.pose.orientation.z = math.sin(yaw / 2)
    m.pose.pose.orientation.w = math.cos(yaw / 2)
    m.pose.covariance[0] = m.pose.covariance[7] = 0.05
    m.pose.covariance[35] = 0.02
    for _ in range(8):
        m.header.stamp = node.get_clock().now().to_msg()
        pose_pub.publish(m)
        rclpy.spin_once(node, timeout_sec=0.2)
        time.sleep(0.4)
    print(f"  seeded at ({x:+.3f}, {y:+.3f}) yaw {math.degrees(yaw):+.1f} deg")

    for svc in ("/global_costmap/clear_entirely_global_costmap",
                "/local_costmap/clear_entirely_local_costmap"):
        cli = node.create_client(ClearEntireCostmap, svc)
        if cli.wait_for_service(timeout_sec=6.0):
            fut = cli.call_async(ClearEntireCostmap.Request())
            rclpy.spin_until_future_complete(node, fut, timeout_sec=6.0)

    def drive(ang: float, secs: float) -> None:
        tw = Twist()
        tw.angular.z = ang
        t0 = time.time()
        while time.time() - t0 < secs:
            vel_pub.publish(tw)
            rclpy.spin_once(node, timeout_sec=0.02)
            time.sleep(0.05)
        for _ in range(10):
            vel_pub.publish(Twist())
            rclpy.spin_once(node, timeout_sec=0.02)
            time.sleep(0.05)

    print("  rotating to make the filter converge...")
    drive(0.5, 5.0)
    time.sleep(1.0)
    drive(-0.5, 5.0)
    print("  done. Check /api/robot/status for the particle spread.")
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
