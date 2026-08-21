#!/usr/bin/env python3
"""Draw one recorded command as it executed through the graph.

    scripts/plot_trace.py                 # the most recent run
    scripts/plot_trace.py --index 0       # a specific one

Reads backend/app/data/traces/graph_runs.jsonl, which the command policy writes
for every run. The structure of the graph is a fixed diagram; what this adds is
where a particular command went and how long each node held it, which is the
part that differs between a command that succeeded and one that did not.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "backend" / "app" / "data" / "traces" / "graph_runs.jsonl"
INK, ACC, GREY, WARN = "#1a242e", "#0e6b61", "#9aa8b5", "#9a5c07"

# The layout mirrors CommandGraph._build(); node ids are the strings that come
# back in `path`, which is what selects the route to highlight.
LAYOUT = {
    "understand": (0.50, 0.86, "classify intent"),
    "navigate":   (0.17, 0.60, "resolve pose, dispatch"),
    "verify":     (0.17, 0.37, "await the real outcome"),
    "recover":    (0.17, 0.14, "clear both costmaps"),
    "move":       (0.83, 0.60, "velocity primitive"),
    "answer":     (0.50, 0.14, "reply, with the reason"),
}
EDGES = [
    ("understand", "navigate", "names a place"),
    ("understand", "move", "raw motion"),
    ("understand", "answer", "a question"),
    ("navigate", "verify", ""),
    ("verify", "recover", "aborted"),
    ("verify", "answer", "succeeded"),
    ("recover", "navigate", "retry once"),
    ("move", "answer", ""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=int, default=-1)
    ap.add_argument("--out", default=str(REPO / "results" / "figures" / "graph_trace.png"))
    args = ap.parse_args()

    if not LOG.exists():
        print(f"No trace log at {LOG}. Run a command through /api/chat/graph-command.")
        return 1
    runs = [json.loads(l) for l in LOG.read_text().strip().split("\n") if l.strip()]
    r = runs[args.index]
    path = r.get("path") or []
    took = {t["node"]: t["took_ms"] for t in (r.get("trace") or [])}
    taken = {(path[i], path[i + 1]) for i in range(len(path) - 1)}

    print(f"  command : {r['command']}")
    print(f"  route   : {' -> '.join(path)}")
    print(f"  outcome : {r.get('outcome')}   {r['elapsed_ms']/1000:.2f} s")

    fig, ax = plt.subplots(figsize=(9.6, 6.0))
    ax.set_xlim(-0.06, 1.02); ax.set_ylim(0, 1); ax.axis("off")

    for a, b, lab in EDGES:
        ax1, ay1, _ = LAYOUT[a]
        ax2, ay2, _ = LAYOUT[b]
        hot = (a, b) in taken
        # the retry edge is routed round the left so it does not cross recover
        if (a, b) == ("recover", "navigate"):
            ax.annotate("", xy=(ax2 - 0.155, ay2), xytext=(ax1 - 0.155, ay1),
                        arrowprops=dict(arrowstyle="-", lw=1.1,
                                        color=ACC if hot else GREY))
            for yy in (ay1, ay2):
                ax.annotate("", xy=(ax1 - 0.155, yy), xytext=(ax1 - 0.115, yy),
                            arrowprops=dict(arrowstyle="-", lw=1.1,
                                            color=ACC if hot else GREY))
            ax.text(ax1 - 0.168, (ay1 + ay2) / 2, lab, rotation=90, fontsize=7.5,
                    color=GREY, ha="right", va="center")
            continue
        ax.annotate("", xy=(ax2, ay2 + 0.045), xytext=(ax1, ay1 - 0.045),
                    arrowprops=dict(arrowstyle="->", lw=2.2 if hot else 1.1,
                                    color=ACC if hot else GREY,
                                    shrinkA=2, shrinkB=2))
        if lab:
            ax.text((ax1 + ax2) / 2 + 0.015, (ay1 + ay2) / 2, lab, fontsize=7.5,
                    color=ACC if hot else GREY, ha="left", va="center")

    for name, (x, y, sub) in LAYOUT.items():
        on = name in path
        ax.add_patch(FancyBboxPatch((x - 0.115, y - 0.045), 0.23, 0.09,
                                    boxstyle="round,pad=0.012,rounding_size=0.012",
                                    linewidth=2.0 if on else 1.0,
                                    edgecolor=ACC if on else GREY,
                                    facecolor="#eaf3f1" if on else "#f6f8f9",
                                    zorder=3))
        ax.text(x, y + 0.012, name, ha="center", va="center", fontsize=11,
                color=INK if on else GREY, zorder=4,
                fontweight="bold" if on else "normal")
        ax.text(x, y - 0.022, sub, ha="center", va="center", fontsize=7.2,
                color=INK if on else GREY, zorder=4)
        if on and name in took:
            order = path.index(name) + 1
            ax.text(x + 0.118, y + 0.030, f"{order}", ha="center", va="center",
                    fontsize=8.5, color="white", zorder=5,
                    bbox=dict(boxstyle="circle,pad=0.22", fc=ACC, ec="none"))
            ax.text(x, y - 0.062, f"{took[name]:,} ms", ha="center", va="top",
                    fontsize=8.5, color=ACC, zorder=4)

    ax.text(0.5, 0.985, f"“{r['command']}”", ha="center", va="top",
            fontsize=12, color=INK, style="italic")
    ax.text(0.5, 0.945,
            f"{r.get('intent')}  ·  {r.get('place')}  ·  "
            f"{r.get('outcome')}  ·  {r['elapsed_ms']/1000:.2f} s total",
            ha="center", va="top", fontsize=9, color=GREY)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"  wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
