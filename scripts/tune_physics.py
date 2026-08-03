#!/usr/bin/env python3
"""Read, change and test the robot's contact physics.

    scripts/tune_physics.py --show
    scripts/tune_physics.py --set maxVel=0.0 minDepth=0.001
    scripts/tune_physics.py --test
    scripts/tune_physics.py --set kp=500000 --test

Every value lives in gazebo/romr_gazebo_physics.gazebo. --set rewrites it,
rebuilds the workspace, and (with --test) relaunches the simulator and measures
the result, so a tuning cycle is one command.

WHAT EACH PARAMETER DOES, and what a wrong value looks like:

  maxVel      Contact CORRECTION velocity. When two bodies overlap, ODE shoves
              them apart at up to this speed. Default 0.01 m/s. If the robot
              creeps at a constant ~0.01 m/s and then stops, this is why: it is
              being pushed out of a persistent overlap. 0.0 disables the shove.

  minDepth    Penetration tolerated before ODE corrects at all. Default 0.0,
              which means every numerical wobble is corrected. ~0.001 lets a
              resting wheel sit still.

  kp          Contact stiffness. Default 1e12, effectively rigid, which makes
              the solver ring and the robot jitter. Too low and the wheels sink
              into the floor.

  kd          Contact damping. Too low and contacts bounce; too high and the
              robot feels stuck to the ground.

  wheels_mu   Drive-wheel friction. Too low and the wheels spin without moving
              the robot; too high and any contact with an edge becomes a violent
              pivot. 1.5 is about rubber on wood.

  casters_mu  Caster friction. These are modelled as fixed skids, not rollers,
              so they drag. Too high and the robot fights itself on every turn;
              0.0 is too far, because it then slides and yaws on its own while
              parked, which the wheel encoders never see.

READING THE TEST OUTPUT:

  settle drift   Distance moved with nothing commanding, after spawning.
                 Should be under ~5 mm over 60 s. A constant rate that stops
                 abruptly means contact correction. A rate that decays means
                 the robot is still settling. A rate that never stops means
                 friction is too low or something is publishing to /cmd_vel.

  straight       Commanded 0.10 m/s. Expect >90% of distance and under 1 degree
                 of yaw error. Low percentage with large yaw error means the
                 robot is touching something.

  rotate         Commanded 0.5 rad/s in place. Expect >85% and under 50 mm of
                 translation. Large translation during rotation means the
                 casters are scrubbing.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PHYS = REPO / "gazebo/romr_gazebo_physics.gazebo"

PARAMS = {
    "kp": "contact_kp",
    "kd": "contact_kd",
    "minDepth": "contact_min_depth",
    "maxVel": "contact_max_vel",
    "wheels_mu": "wheels_friction",
    "casters_mu": "caster_friction",
    "body_mu": "standard_friction",
}


def read_params() -> dict[str, str]:
    s = PHYS.read_text()
    out = {}
    for name, prop in PARAMS.items():
        m = re.search(r'name="%s"\s+value="([^"]+)"' % re.escape(prop), s)
        out[name] = m.group(1) if m else "?"
    return out


def set_params(pairs: list[str]) -> None:
    s = PHYS.read_text()
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"expected name=value, got {pair!r}")
        name, value = pair.split("=", 1)
        if name not in PARAMS:
            raise SystemExit(f"unknown parameter {name!r}. Known: {', '.join(PARAMS)}")
        prop = PARAMS[name]
        s, n = re.subn(r'(name="%s"\s+value=")[^"]+(")' % re.escape(prop),
                       r"\g<1>%s\g<2>" % value, s)
        if not n:
            raise SystemExit(f"could not find property {prop} in {PHYS}")
        print(f"  {name} -> {value}")
    PHYS.write_text(s)


def rebuild() -> None:
    print("  rebuilding…")
    subprocess.run(
        "source /opt/ros/humble/setup.bash && cd ~/turtlebot3_ws && "
        "colcon build --symlink-install --packages-select multimodal_robot_autonomy",
        shell=True, executable="/bin/bash", capture_output=True, timeout=300,
    )


def relaunch() -> None:
    print("  restarting the simulator…")
    subprocess.run([str(REPO / "scripts/clean.sh")], capture_output=True, timeout=120)
    subprocess.Popen(
        f"source {REPO}/scripts/env.sh && "
        f"exec ros2 launch multimodal_robot_autonomy gazebo_romr.launch.py",
        shell=True, executable="/bin/bash", start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        time.sleep(3)
        if subprocess.run(["pgrep", "-x", "gzserver"], capture_output=True).returncode == 0:
            break
    time.sleep(22)


def measure() -> None:
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry

    rclpy.init()
    node = rclpy.create_node("tune_test")
    st: dict = {}

    def cb(m):
        q = m.pose.pose.orientation
        st["p"] = (m.pose.pose.position.x, m.pose.pose.position.y, m.pose.pose.position.z,
                   math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)))
        st["v"] = abs(m.twist.twist.linear.x)

    node.create_subscription(Odometry, "/odom", cb, 20)
    pub = node.create_publisher(Twist, "/cmd_vel", 10)
    t0 = time.time()
    while time.time() - t0 < 12 and "p" not in st:
        rclpy.spin_once(node, timeout_sec=0.2)
    if "p" not in st:
        print("  no /odom — is the simulator up?")
        return

    # 1. settle drift, nothing commanded
    p0 = st["p"]
    vmax = 0.0
    t0 = time.time()
    while time.time() - t0 < 60:
        rclpy.spin_once(node, timeout_sec=0.05)
        vmax = max(vmax, st["v"])
    p1 = st["p"]
    drift = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    print(f"  settle drift   {drift*1000:8.2f} mm over 60 s   peak |v| {vmax:.5f} m/s"
          f"   {'OK' if drift < 0.005 else 'HIGH'}")

    def run(lin, ang, secs):
        a = st["p"]
        t = Twist(); t.linear.x = lin; t.angular.z = ang
        s = time.time()
        while time.time() - s < secs:
            pub.publish(t); rclpy.spin_once(node, timeout_sec=0.02); time.sleep(0.05)
        for _ in range(12):
            pub.publish(Twist()); rclpy.spin_once(node, timeout_sec=0.02); time.sleep(0.05)
        time.sleep(0.8); rclpy.spin_once(node, timeout_sec=0.3)
        b = st["p"]
        return (math.hypot(b[0] - a[0], b[1] - a[1]),
                math.degrees((b[3] - a[3] + math.pi) % (2 * math.pi) - math.pi))

    # RTF matters: the expectation is sim-time distance, wall clock is longer
    d, dy = run(0.10, 0.0, 5)
    print(f"  straight       {d*1000:8.2f} mm of ~420 expected ({100*d/0.42:3.0f}%)"
          f"   yaw error {dy:+6.2f} deg   {'OK' if d > 0.34 and abs(dy) < 1 else 'POOR'}")
    d, dy = run(0.0, 0.5, 4)
    exp = math.degrees(0.5 * 4 * 0.84)
    print(f"  rotate         {dy:+8.2f} deg of ~{exp:.0f} expected ({100*abs(dy)/exp:3.0f}%)"
          f"   translation {d*1000:5.1f} mm   {'OK' if abs(dy) > 0.85*exp and d < 0.05 else 'POOR'}")
    rclpy.shutdown()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--set", nargs="+", default=[], metavar="NAME=VALUE")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--no-restart", action="store_true",
                    help="test against the running simulator instead of relaunching")
    args = ap.parse_args()

    if args.set:
        set_params(args.set)
        rebuild()
    if args.show or not (args.set or args.test):
        print(f"  {'parameter':12} value          file: {PHYS.relative_to(REPO)}")
        for k, v in read_params().items():
            print(f"  {k:12} {v}")
    if args.test:
        if not args.no_restart:
            relaunch()
        print("\n  measuring (about 80 s)…")
        measure()
    return 0


if __name__ == "__main__":
    sys.exit(main())
