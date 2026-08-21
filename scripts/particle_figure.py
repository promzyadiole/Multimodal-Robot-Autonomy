#!/usr/bin/env python3
"""Capture the live particle set and draw it, for the thesis.

    scripts/particles.sh                       one snapshot
    scripts/particles.sh --label "after turn"  annotate it
    scripts/particles.sh --out figures/x.png

Textbook diagrams of a particle filter are one-dimensional: the state is a
position on a line and the belief is a row of spikes. This robot's state is
three-dimensional -- x, y and heading -- so the same particle set has to be
looked at in three views rather than one, and that is what this draws, from
the actual cloud AMCL is holding rather than from an illustration.

Everything plotted comes off /particle_cloud, whose message is literally a
list of (pose, weight) pairs -- the same <x[j], w[j]> the theory writes down.
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav2_msgs.msg import ParticleCloud
from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                       QoSReliabilityPolicy)

REPO = Path(__file__).resolve().parents[1]


def yaw_of(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def truth():
    """Gazebo's pose for the robot, so the cloud can be judged, not just shown."""
    try:
        o = subprocess.run(["gz", "model", "-m", "romr", "-p"],
                           capture_output=True, text=True, timeout=20).stdout.split()
        return (float(o[0]), float(o[1]), float(o[5])) if len(o) >= 6 else None
    except Exception:  # noqa: BLE001
        return None


def capture(timeout: float = 25.0, nudge: float = 0.0):
    """Wait for one particle cloud, optionally rotating gently to provoke it.

    AMCL publishes on update, not on a timer: the filter only runs once the
    robot has moved past update_min_d or update_min_a. A parked robot therefore
    publishes nothing at all, and a subscriber waits forever on a topic that
    has a publisher and is behaving correctly. Rotating slowly is the cheapest
    way to make the filter tick, and cannot collide with anything.
    """
    rclpy.init()
    node = rclpy.create_node("particle_figure")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    got = {}
    qos = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.BEST_EFFORT,
                     durability=QoSDurabilityPolicy.VOLATILE,
                     history=QoSHistoryPolicy.KEEP_LAST)
    node.create_subscription(ParticleCloud, "/particle_cloud",
                             lambda m: got.__setitem__("c", m), qos)
    vel = node.create_publisher(Twist, "/cmd_vel", 10) if nudge else None
    t0 = time.time()
    while time.time() - t0 < timeout and "c" not in got:
        if vel is not None:
            tw = Twist()
            tw.angular.z = nudge
            vel.publish(tw)
        rclpy.spin_once(node, timeout_sec=0.1)
    if vel is not None:
        for _ in range(12):
            vel.publish(Twist())
            rclpy.spin_once(node, timeout_sec=0.02)
            time.sleep(0.03)
        # let the filter settle on the pose it actually ended at
        t1 = time.time()
        while time.time() - t1 < 2.0:
            rclpy.spin_once(node, timeout_sec=0.1)
    rclpy.shutdown()
    if "c" not in got:
        return None
    msg = got["c"]
    x = np.array([p.pose.position.x for p in msg.particles])
    y = np.array([p.pose.position.y for p in msg.particles])
    th = np.array([yaw_of(p.pose.orientation) for p in msg.particles])
    w = np.array([p.weight for p in msg.particles], dtype=float)
    return x, y, th, w


def circular_mean(th, w):
    """Headings live on a circle, so the arithmetic mean of 359 deg and 1 deg
    is 180 deg -- exactly wrong. Average the unit vectors instead."""
    s = float(np.sum(w * np.sin(th)))
    c = float(np.sum(w * np.cos(th)))
    return math.atan2(s, c)


def circular_std(th, w, mu):
    d = np.arctan2(np.sin(th - mu), np.cos(th - mu))
    return float(math.sqrt(np.sum(w * d * d)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "results" / "particle_set.png"))
    ap.add_argument("--label", default="")
    ap.add_argument("--nudge", type=float, default=0.35,
                    help="rad/s rotation used to make AMCL publish; 0 to disable")
    args = ap.parse_args()

    cloud = capture(nudge=args.nudge)
    if cloud is None:
        print("No /particle_cloud received.\n"
              "  AMCL publishes only when the filter updates, so a parked robot\n"
              "  is silent -- this already rotates to provoke one. If nothing\n"
              "  arrives, nav2 is down or AMCL has no initial pose: run\n"
              "  scripts/seed.sh, or use RViz's 2D Pose Estimate.")
        return 1
    x, y, th, w = cloud
    J = len(x)
    if w.sum() <= 0:
        w = np.ones(J) / J
    w = w / w.sum()

    mx, my = float(np.sum(w * x)), float(np.sum(w * y))
    mth = circular_mean(th, w)
    sx = float(math.sqrt(np.sum(w * (x - mx) ** 2)))
    sy = float(math.sqrt(np.sum(w * (y - my) ** 2)))
    sth = circular_std(th, w, mth)
    t = truth()

    print(f"  particles J          : {J}")
    print(f"  weighted mean        : ({mx:+.3f}, {my:+.3f})  yaw {math.degrees(mth):+.1f} deg")
    print(f"  sigma  x / y / yaw   : {sx:.3f} m / {sy:.3f} m / {sth:.3f} rad")
    print(f"  weight  min/max/mean : {w.min():.2e} / {w.max():.2e} / {w.mean():.2e}")
    if t:
        print(f"  gazebo truth         : ({t[0]:+.3f}, {t[1]:+.3f})  yaw {math.degrees(t[2]):+.1f} deg")
        print(f"  belief error         : {math.dist((mx, my), t[:2]):.3f} m")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(12, 4.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.5, 1, 1], wspace=0.28)
    ACC, TRU = "#0f6b61", "#c2410c"

    # --- the set in the plane, sized by weight -------------------------
    ax = fig.add_subplot(gs[0, 0])
    ax.scatter(x, y, s=6 + 5000 * w, c=w, cmap="viridis", alpha=0.75,
               linewidths=0, zorder=2)
    ax.plot(mx, my, "x", color=ACC, ms=11, mew=2.4, zorder=4,
            label=f"weighted mean  $\\sigma$={sx:.2f}, {sy:.2f} m")
    if t:
        ax.plot(t[0], t[1], "+", color=TRU, ms=13, mew=2.4, zorder=5,
                label="Gazebo ground truth")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    ax.set_title(f"Particle set in the plane   J = {J}", fontsize=10)
    ax.legend(fontsize=7.5, loc="best"); ax.set_aspect("equal", "datalim")
    ax.grid(alpha=0.25, lw=0.5)

    # --- the marginal the textbook draws in 1-D ------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.hist(x, bins=40, weights=w, color="#94a3b8", edgecolor="none")
    ax2.axvline(mx, color=ACC, lw=1.8, label="mean")
    if t:
        ax2.axvline(t[0], color=TRU, lw=1.8, ls="--", label="truth")
    ax2.set_xlabel("x (m)"); ax2.set_ylabel("posterior mass")
    ax2.set_title("Marginal over x  (the 1-D picture)", fontsize=10)
    ax2.legend(fontsize=7.5); ax2.grid(alpha=0.25, lw=0.5)

    # --- heading, the dimension a 1-D diagram cannot show --------------
    ax3 = fig.add_subplot(gs[0, 2])
    d = np.degrees(np.arctan2(np.sin(th - mth), np.cos(th - mth)))
    ax3.hist(d, bins=40, weights=w, color="#94a3b8", edgecolor="none")
    ax3.axvline(0, color=ACC, lw=1.8, label="mean heading")
    if t:
        dt = math.degrees(math.atan2(math.sin(t[2] - mth), math.cos(t[2] - mth)))
        ax3.axvline(dt, color=TRU, lw=1.8, ls="--", label="truth")
    ax3.set_xlabel("heading, deg from mean"); ax3.set_ylabel("posterior mass")
    ax3.set_title(f"Marginal over $\\theta$   $\\sigma$ = {sth:.3f} rad", fontsize=10)
    ax3.legend(fontsize=7.5); ax3.grid(alpha=0.25, lw=0.5)

    head = "AMCL particle set"
    if args.label:
        head += f" — {args.label}"
    if t:
        head += f"   (belief error {math.dist((mx, my), t[:2]):.3f} m)"
    fig.suptitle(head, fontsize=12, y=1.0)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"\n  written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
