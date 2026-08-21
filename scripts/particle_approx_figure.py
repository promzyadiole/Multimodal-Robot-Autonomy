#!/usr/bin/env python3
"""Draw the sample-approximation idea using this robot's own particles.

    scripts/particles_approx.sh

The textbook figure shows a smooth density above a rug of sample ticks, and
makes one claim: the more samples fall in a region, the more probable that
region. This draws the same picture from the live filter, so the claim can be
checked against the belief the robot is actually holding rather than an
illustration of one.

The density curve here is estimated from the samples themselves, by kernel
density estimation. That is the point: nothing stores the curve. The particles
are the belief, and any smooth function drawn through them is a reconstruction.
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


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def truth():
    try:
        o = subprocess.run(["gz", "model", "-m", "romr", "-p"],
                           capture_output=True, text=True, timeout=20).stdout.split()
        return (float(o[0]), float(o[1]), float(o[5])) if len(o) >= 6 else None
    except Exception:  # noqa: BLE001
        return None


def capture(timeout=25.0, nudge=0.35):
    rclpy.init()
    node = rclpy.create_node("particle_approx")
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
            tw = Twist(); tw.angular.z = nudge
            vel.publish(tw)
        rclpy.spin_once(node, timeout_sec=0.1)
    if vel is not None:
        for _ in range(12):
            vel.publish(Twist()); rclpy.spin_once(node, timeout_sec=0.02); time.sleep(0.03)
    rclpy.shutdown()
    if "c" not in got:
        return None
    m = got["c"]
    return (np.array([p.pose.position.x for p in m.particles]),
            np.array([yaw_of(p.pose.orientation) for p in m.particles]),
            np.array([p.weight for p in m.particles], dtype=float))


def kde(samples, grid, bandwidth):
    """Gaussian KDE, written out rather than imported.

    scipy on this host is built against a NumPy the rest of the stack has moved
    past, and this is six lines.
    """
    d = (grid[:, None] - samples[None, :]) / bandwidth
    return np.exp(-0.5 * d * d).sum(axis=1) / (len(samples) * bandwidth * math.sqrt(2 * math.pi))


def panel(ax, samples, label, unit, truth_val=None, sub=200):
    lo, hi = samples.min(), samples.max()
    pad = 0.12 * (hi - lo + 1e-9)
    grid = np.linspace(lo - pad, hi + pad, 400)
    # Silverman's rule, so the bandwidth is derived rather than tuned to taste
    bw = 1.06 * samples.std() * len(samples) ** (-1 / 5) or 1e-3
    dens = kde(samples, grid, bw)
    ax.plot(grid, dens, color="#3b4a6b", lw=1.9, label="$f(x)$ reconstructed from the samples")
    ax.fill_between(grid, dens, color="#3b4a6b", alpha=0.10)
    # the rug: every tick is one particle, thinned only so the ink stays readable
    idx = np.random.default_rng(0).choice(len(samples), size=min(sub, len(samples)),
                                          replace=False)
    ax.plot(samples[idx], np.zeros(len(idx)) - 0.03 * dens.max(), "|",
            color="#111827", ms=9, mew=0.8, alpha=0.55,
            label=f"particles ({len(samples)} held, {len(idx)} drawn)")
    if truth_val is not None:
        ax.axvline(truth_val, color="#c2410c", lw=1.8, ls="--", label="ground truth")
    ax.set_xlabel(f"{label} ({unit})")
    ax.set_ylabel("probability density")
    ax.set_ylim(-0.09 * dens.max(), 1.12 * dens.max())
    ax.grid(alpha=0.22, lw=0.5)
    ax.legend(fontsize=7.5, loc="upper right")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "results" / "particle_approximation.png"))
    args = ap.parse_args()

    got = capture()
    if got is None:
        print("No /particle_cloud received. Is nav2 up and AMCL seeded?")
        return 1
    x, th, w = got
    t = truth()
    print(f"  particles: {len(x)}")
    print(f"  weights  : min {w.min():.3e}  max {w.max():.3e}  "
          f"{'UNIFORM (post-resample)' if np.allclose(w, w[0]) else 'non-uniform'}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0))
    panel(axes[0], x, "x", "m", t[0] if t else None)
    axes[0].set_title("Position: the density is where the particles are", fontsize=10)
    thd = np.degrees(np.arctan2(np.sin(th - np.mean(th)), np.cos(th - np.mean(th))))
    td = None
    if t:
        td = math.degrees(math.atan2(math.sin(t[2] - np.mean(th)),
                                     math.cos(t[2] - np.mean(th))))
    panel(axes[1], thd, r"$\theta$, degrees from the mean", "deg", td)
    axes[1].set_title("Heading: the same construction, third dimension", fontsize=10)
    fig.suptitle("Approximating the belief by samples — from the live filter", fontsize=12)
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"  written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
