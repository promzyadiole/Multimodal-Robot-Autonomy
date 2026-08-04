#!/usr/bin/env python3
"""Live view of where the robot is, where it thinks it is, and how far off.

    scripts/watch.sh

Run this beside the web interface while sending goals. nav2 reporting success
is not evidence of arrival -- this project exists partly to measure that gap --
so every line is scored against Gazebo's own pose for the robot, with AMCL's
belief shown alongside rather than trusted.

Columns:
  truth      Gazebo's pose. The only ground truth available.
  belief     AMCL's estimate, which is what nav2 plans and reports against.
  drift      distance between the two: how wrong the robot's self-knowledge is.
  sigma      AMCL's own stated uncertainty. Rising sigma precedes divergence.
  nearest    closest recorded place, and the distance to it.
"""
from __future__ import annotations

import math
import subprocess
import sys
import time
from pathlib import Path

import rclpy
import yaml
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "backend/app/data/places/new_world_places.yaml"
ARRIVED_M = 0.60


def truth() -> tuple[float, float, float] | None:
    try:
        o = subprocess.run(["gz", "model", "-m", "romr", "-p"],
                           capture_output=True, text=True, timeout=20).stdout.split()
        return (float(o[0]), float(o[1]), float(o[5])) if len(o) >= 6 else None
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    places = {}
    if REGISTRY.exists():
        doc = yaml.safe_load(REGISTRY.read_text()) or {}
        places = {n: (p["x"], p["y"]) for n, p in (doc.get("places") or {}).items()}

    rclpy.init()
    node = rclpy.create_node("watch_robot")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    latest: dict = {}
    q = QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                   reliability=QoSReliabilityPolicy.RELIABLE,
                   history=QoSHistoryPolicy.KEEP_LAST)
    node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose",
                             lambda m: latest.__setitem__("a", m), q)

    # Line-buffered by hand: redirected to a file or piped into tee, Python
    # buffers in 8 KB blocks and a live monitor shows nothing for minutes.
    def out(line: str) -> None:
        print(line, flush=True)

    out(f"{'truth':>17} {'belief':>17} {'drift':>7} {'sigma':>16}   nearest place")
    out("-" * 88)
    try:
        while True:
            rclpy.spin_once(node, timeout_sec=0.5)
            t = truth()
            if t is None:
                out("  Gazebo is not running.")
                time.sleep(2)
                continue
            tx, ty, _ = t
            near = ""
            if places:
                n, (px, py) = min(places.items(),
                                  key=lambda kv: math.dist((tx, ty), kv[1]))
                d = math.dist((tx, ty), (px, py))
                near = f"{n} {d:.2f} m" + ("  ARRIVED" if d <= ARRIVED_M else "")
            if "a" in latest:
                a = latest["a"].pose.pose
                c = latest["a"].pose.covariance
                ax, ay = a.position.x, a.position.y
                drift = math.dist((tx, ty), (ax, ay))
                sig = (f"{math.sqrt(c[0]):.2f}/{math.sqrt(c[7]):.2f}/"
                       f"{math.sqrt(c[35]):.2f}")
                flag = "  <-- LOST" if drift > 1.0 else ""
                out(f"({tx:+7.2f},{ty:+7.2f}) ({ax:+7.2f},{ay:+7.2f}) "
                    f"{drift:7.3f} {sig:>16}   {near}{flag}")
            else:
                out(f"({tx:+7.2f},{ty:+7.2f}) {'no /amcl_pose':>17} "
                    f"{'':>7} {'':>16}   {near}")
            time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
