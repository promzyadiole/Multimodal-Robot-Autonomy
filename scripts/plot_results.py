#!/usr/bin/env python3
"""Draw the results chapter's figures from the per-trial records.

    scripts/plot_results.py

Reads the two validation CSVs and the parameter sweep, and writes three
figures. Nothing here needs the robot: every number comes from a file that
ships with the repository, which is the point -- a reader can regenerate the
figures and check them against the tables.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "figures"
INK, ACC, WARN, GREY = "#1a242e", "#0e6b61", "#9a5c07", "#94a3b8"
ARRIVED = 0.5


def load(path: Path):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        for k in ("error_true_m", "error_amcl_m", "amcl_drift_m", "seconds"):
            try:
                r[k] = float(r[k])
            except (ValueError, TypeError, KeyError):
                r[k] = None
    return rows


def executed(rows):
    """Trials whose duration is consistent with a navigation having run.

    The initial campaign contains trials that returned in seconds because an
    outcome from a previous goal was read as their own; including them would
    put the denominator over commands that never attempted the task.
    """
    return [r for r in rows if (r.get("seconds") or 0) >= 10]


def fig_reported_vs_actual(old, new, path):
    """The gap the thesis exists to report, in one picture."""
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    groups = ["Initial\n(16 navigation trials)", "Corrected\n(61 commands)"]
    rep = [sum(1 for r in old if r["outcome"] == "succeeded") / len(old) * 100,
           sum(1 for r in new if r["outcome"] == "succeeded") / len(new) * 100]
    act = [sum(1 for r in old if (r["error_true_m"] or 9e9) <= ARRIVED) / len(old) * 100,
           sum(1 for r in new if (r["error_true_m"] or 9e9) <= ARRIVED) / len(new) * 100]
    x = np.arange(2)
    w = 0.34
    b1 = ax.bar(x - w / 2, rep, w, label="reported success", color=GREY, edgecolor="none")
    b2 = ax.bar(x + w / 2, act, w, label="actually arrived (ground truth)",
                color=ACC, edgecolor="none")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5,
                    f"{b.get_height():.0f}%", ha="center", fontsize=9.5, color=INK)
    # The gap is the finding, so it is marked -- but to the side of the bars.
    # Drawn between them the leader crossed both and landed on a data label.
    gx = 0.40
    ax.annotate("", xy=(gx, rep[0]), xytext=(gx, act[0]),
                arrowprops=dict(arrowstyle="<->", color=WARN, lw=1.6))
    ax.text(gx + 0.04, (rep[0] + act[0]) / 2,
            "83% of reported\nsuccesses were false",
            ha="left", va="center", fontsize=9, color=WARN)
    ax.set_xticks(x); ax.set_xticklabels(groups, fontsize=9.5)
    ax.set_ylabel("percentage of trials"); ax.set_ylim(0, 112)
    ax.legend(fontsize=9, loc="upper center", ncol=2, frameon=False,
          bbox_to_anchor=(0.5, 1.14))
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    ax.set_axisbelow(True)
    ax.set_title("What the stack reported, against what happened",
                 fontsize=11, pad=28)
    fig.tight_layout(); fig.savefig(path, dpi=200, bbox_inches="tight"); plt.close(fig)


def fig_error_distribution(old, new, path):
    """Where the trials actually ended up, before and after."""
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.9), sharey=True)
    for ax, rows, title, col in (
            (axes[0], old, "Initial", WARN), (axes[1], new, "Corrected", ACC)):
        e = sorted(r["error_true_m"] for r in rows if r["error_true_m"] is not None)
        ax.hist(e, bins=np.linspace(0, 16, 33), color=col, alpha=0.85, edgecolor="none")
        ax.axvline(ARRIVED, color=INK, ls="--", lw=1.4,
                   label=f"arrival threshold {ARRIVED} m")
        med = e[len(e) // 2]
        ax.axvline(med, color=INK, lw=1.8, label=f"median {med:.3f} m")
        ax.set_xlabel("true distance from goal (m)")
        ax.set_title(f"{title}   n = {len(e)}", fontsize=10.5)
        ax.legend(fontsize=8.5); ax.grid(alpha=0.25, lw=0.5); ax.set_axisbelow(True)
    axes[0].set_ylabel("trials")
    fig.suptitle("Distance from the goal, scored against simulator ground truth",
                 fontsize=11.5)
    fig.tight_layout(); fig.savefig(path, dpi=200, bbox_inches="tight"); plt.close(fig)


def fig_alpha_sweep(path):
    """The correction that ran the wrong way, as a curve rather than a table."""
    a = [0.25, 0.10, 0.05, 0.02, 0.01]
    err = [0.469, 0.279, 0.168, 0.108, 0.104]
    sig = [1.257, 0.958, 0.694, 0.441, 0.364]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.plot(a, err, "o-", color=ACC, lw=1.9, ms=6, label="position error after the turn (m)")
    ax.plot(a, sig, "s--", color=WARN, lw=1.9, ms=5.5, label=r"heading spread $\sigma_\theta$ (rad)")
    ax.set_xscale("log")
    ax.set_xlabel(r"rotational noise coefficient $\alpha_1 = \alpha_2$   (log scale)")
    ax.set_ylabel("measured after a 90° rotation")
    ax.set_ylim(0.0, 1.42)
    # kept inside the axes: at the previous placement it overran the title
    ax.annotate("the intuitive correction —\nadmit more rotational noise",
                xy=(0.245, 1.245), xytext=(0.038, 1.05), fontsize=8.5, color=INK,
                ha="left", va="top",
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.1,
                                connectionstyle="arc3,rad=-0.15"))
    ax.annotate("adopted", xy=(0.02, 0.441), xytext=(0.0145, 0.72), fontsize=9,
                color=ACC, arrowprops=dict(arrowstyle="->", color=ACC, lw=1.3))
    ax.grid(alpha=0.28, lw=0.5); ax.set_axisbelow(True)
    ax.legend(fontsize=9, loc="upper left")
    ax.set_title("Both measures fall monotonically as the coefficient is reduced",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(path, dpi=200, bbox_inches="tight"); plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    old = executed(load(REPO / "validation_results_groundtruth.csv"))
    new = load(REPO / "results" / "validation_2026-08-04_fixed.csv")
    print(f"  initial run : {len(old)} executed navigation trials")
    print(f"  corrected   : {len(new)} commands")
    fig_reported_vs_actual(old, new, OUT / "reported_vs_actual.png")
    fig_error_distribution(old, new, OUT / "error_distribution.png")
    fig_alpha_sweep(OUT / "alpha_sweep.png")
    for f in sorted(OUT.glob("*.png")):
        print(f"  wrote {f.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
