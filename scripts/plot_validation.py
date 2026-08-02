#!/usr/bin/env python3
"""Plot the gap between what the robot believed and where it actually was.

  scripts/plot_validation.py [validation_results_groundtruth.csv] [out.png]

Panel (a) is the argument of the thesis in one picture: each trial is placed at
(error AMCL believed, error actually measured). Points on the diagonal are
trials where the belief was honest. Points far above it are trials where the
robot believed it was close and was not -- and the shaded band at the bottom
marks the region AMCL calls "arrived", so anything in the lower-right of that
band is a goal reported successful while the robot was metres away.

Panel (b) shows how the belief-truth gap is distributed across the suite.
"""
import csv, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = sys.argv[1] if len(sys.argv) > 1 else "validation_results_groundtruth.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "thesis/source/overleaf/figures/Figure5_2_error_scatter.png"
TOL = 0.5

rows = list(csv.DictReader(open(SRC)))
num = lambda r, k: float(r[k]) if r.get(k) not in ("", "nan", None) else None

amcl, true, claimed = [], [], []
for r in rows:
    a, t = num(r, "error_amcl_m"), num(r, "error_true_m")
    if a is None or t is None:
        continue
    amcl.append(a); true.append(t); claimed.append(r["outcome"] == "succeeded")

drift = sorted(d for d in (num(r, "amcl_drift_m") for r in rows) if d is not None)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))

# --- (a) believed error vs measured error --------------------------------
hi = max(max(amcl), max(true)) * 1.08
ax1.axhspan(0, TOL, color="#3fbfb3", alpha=0.10, zorder=0)
ax1.axvspan(0, TOL, color="#3fbfb3", alpha=0.10, zorder=0)
ax1.plot([0, hi], [0, hi], "--", color="#888", lw=1, zorder=1,
         label="belief = truth")
for a, t, c in zip(amcl, true, claimed):
    ax1.scatter(a, t, s=46, zorder=3,
                facecolor="#e8a33d" if c else "none",
                edgecolor="#e8a33d" if c else "#4a6070",
                linewidth=1.4, alpha=0.95 if c else 0.8)
false_pos = sum(1 for a, t, c in zip(amcl, true, claimed) if c and t > TOL)
ax1.scatter([], [], s=46, facecolor="#e8a33d", edgecolor="#e8a33d",
            label=f"nav2 reported success ({sum(claimed)})")
ax1.scatter([], [], s=46, facecolor="none", edgecolor="#4a6070",
            label=f"nav2 reported failure ({len(claimed)-sum(claimed)})")
ax1.set_xlabel("error the robot believed it had (m)")
ax1.set_ylabel("error actually measured (m)")
ax1.set_title("(a) belief against ground truth", fontsize=11, loc="left")
ax1.set_xlim(-0.4, hi); ax1.set_ylim(-0.4, hi)
ax1.legend(fontsize=8, loc="lower right", frameon=False)
ax1.annotate(
    f"{false_pos} goals reported reached\nwhile metres away",
    xy=(0.6, 9.0), xytext=(2.6, 13.2), fontsize=8.5, color="#b5651d",
    arrowprops=dict(arrowstyle="->", color="#b5651d", lw=1.1))
ax1.grid(alpha=0.18, lw=0.6)

# --- (b) distribution of the belief-truth gap ----------------------------
ax2.plot(range(1, len(drift) + 1), drift, marker="o", ms=3.4,
         color="#2f6f7f", lw=1.3)
for th, lab in ((1.0, "1 m"), (5.0, "5 m"), (10.0, "10 m")):
    ax2.axhline(th, ls=":", lw=0.9, color="#999")
    ax2.text(0.6, th * 1.06, lab, fontsize=7.5, color="#777")
ax2.set_xlabel("trials, sorted by belief-truth gap")
ax2.set_ylabel("gap between belief and truth (m)")
ax2.set_title("(b) how far the estimate strayed", fontsize=11, loc="left")
ax2.grid(alpha=0.18, lw=0.6)
over = lambda t: sum(1 for d in drift if d > t)
ax2.text(0.03, 0.96,
         f">1 m on {over(1.0)}/{len(drift)} trials\n"
         f">5 m on {over(5.0)}\n>10 m on {over(10.0)}",
         transform=ax2.transAxes, va="top", fontsize=8.5,
         bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#ccc", lw=0.7))

fig.tight_layout()
fig.savefig(OUT, dpi=200)
print(f"wrote {OUT}")
print(f"  {len(true)} trials plotted, {false_pos} false positives, "
      f"max drift {max(drift):.2f} m")
