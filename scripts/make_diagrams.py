#!/usr/bin/env python3
"""Render the thesis system diagrams as vector PDFs (plus PNG previews).

  backend/.venv/bin/python scripts/make_diagrams.py

Drawn rather than screenshotted, so they carry the architecture rather than the
state of a particular run, and stay legible in print.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

OUT = "thesis/source/overleaf/figures"

INK   = "#1c2530"
MUTED = "#6b7b8c"
RULE  = "#9aa9b8"
TEAL  = "#2f8f86"
AMBER = "#c8862c"
FILL  = "#eef3f6"
FILL2 = "#e2ecef"

def box(ax, x, y, w, h, title, sub=None, fc=FILL, ec=RULE, tc=INK, fs=9.5, lw=1.1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(x + w/2, y + (h*0.63 if sub else h/2), title, ha="center", va="center",
            fontsize=fs, color=tc, zorder=3, family="DejaVu Sans")
    if sub:
        ax.text(x + w/2, y + h*0.29, sub, ha="center", va="center",
                fontsize=fs-2.4, color=MUTED, zorder=3, family="DejaVu Sans")

def arrow(ax, p, q, color=RULE, lw=1.3, style="-|>", rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=12,
                                 color=color, lw=lw, zorder=1, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=2, shrinkB=3))

def label(ax, x, y, t, color=MUTED, fs=7.8, rot=0, ha="center"):
    ax.text(x, y, t, ha=ha, va="center", fontsize=fs, color=color, rotation=rot,
            family="DejaVu Sans", zorder=4)

def finish(fig, ax, name, xlim=(0,1), ylim=(0,1)):
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.axis("off")
    fig.tight_layout(pad=0.2)
    fig.savefig(f"{OUT}/{name}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/{name}.png", dpi=190, bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}.pdf / .png")


# ---------------------------------------------------------------- 1. architecture
def architecture():
    fig, ax = plt.subplots(figsize=(11, 5.4))
    # lanes
    for y0, h, t, c in ((0.055, 0.30, "ROS 2 / DDS  (Cyclone DDS, unicast loopback, domain 42)", "#e8f1f0"),
                        (0.60, 0.33, "HTTP / JSON", "#f2eee6")):
        ax.add_patch(FancyBboxPatch((0.02, y0), 0.96, h, boxstyle="round,pad=0.004,rounding_size=0.01",
                                    fc=c, ec="none", zorder=0))
        label(ax, 0.035, y0 + h - 0.035, t, color=MUTED, fs=8, ha="left")

    box(ax, 0.04, 0.115, 0.185, 0.16, "Gazebo Classic 11", "world, physics, sensors\nGROUND TRUTH", fc="#dbe9e7")
    box(ax, 0.355, 0.115, 0.235, 0.16, "ROS 2 Navigation 2", "AMCL · NavFn · DWB\nbehaviour tree")
    box(ax, 0.645, 0.115, 0.15, 0.16, "robot_state_\npublisher", "URDF → TF")
    box(ax, 0.825, 0.115, 0.135, 0.16, "ROMR", "10 links, URDF")

    box(ax, 0.05, 0.66, 0.34, 0.21, "Reasoning backend  (FastAPI)",
        "LLM intent parser · action mapper · LangGraph policy\nSAM+CLIP · state store · RAG", fc="#f6efe2")
    box(ax, 0.46, 0.66, 0.22, 0.21, "Command centre", "Next.js · speech capture\ngraph + live trace", fc="#f6efe2")
    box(ax, 0.74, 0.66, 0.21, 0.21, "External services", "OpenAI · Pinecone\nLangSmith", fc="#f6efe2")

    # bridge
    box(ax, 0.355, 0.44, 0.235, 0.115, "ROS 2 bridge node", "the process boundary", fc="#ffffff", ec=TEAL, lw=1.5)
    arrow(ax, (0.22, 0.66), (0.42, 0.556), TEAL, 1.5)
    arrow(ax, (0.4725, 0.44), (0.4725, 0.276), TEAL, 1.5)
    label(ax, 0.10, 0.60, "NumPy 1.x  |  NumPy 2.x\ncannot share an interpreter", color=TEAL, fs=7.4)

    arrow(ax, (0.46, 0.765), (0.39, 0.765), MUTED, 1.2, style="<|-|>")
    arrow(ax, (0.74, 0.765), (0.39, 0.80), MUTED, 1.1, rad=-0.12)
    arrow(ax, (0.225, 0.215), (0.355, 0.215), MUTED)
    label(ax, 0.29, 0.243, "/scan  /odom", fs=7)
    arrow(ax, (0.355, 0.150), (0.225, 0.150), MUTED)
    label(ax, 0.29, 0.122, "/cmd_vel", fs=7)
    arrow(ax, (0.645, 0.195), (0.59, 0.195), MUTED)
    label(ax, 0.6175, 0.222, "/tf", fs=7)
    arrow(ax, (0.825, 0.195), (0.795, 0.195), MUTED)

    ax.add_patch(FancyArrowPatch((0.132, 0.115), (0.132, 0.048), arrowstyle="-|>",
                                 mutation_scale=12, color=AMBER, lw=1.5, zorder=3))
    label(ax, 0.155, 0.030, "gz model -m romr -p   →   ground truth, outside the estimator",
          color=AMBER, fs=7.8, ha="left")
    finish(fig, ax, "Figure3_0_system_architecture")


# ---------------------------------------------------------------- 2. command graph
def command_graph():
    fig, ax = plt.subplots(figsize=(9.2, 6.0))
    W, H = 0.225, 0.085
    C = {"understand": (0.45, 0.855), "navigate": (0.16, 0.665), "verify": (0.16, 0.495),
         "recover": (0.16, 0.325), "move": (0.78, 0.665), "answer": (0.45, 0.135)}
    subs = {"understand": "LLM \u00b7 classify intent", "navigate": "resolve pose, dispatch",
            "verify": "await the real outcome", "recover": "clear both costmaps",
            "move": "velocity primitive", "answer": "reply, with the reason"}

    def pill(cx, cy, t):
        ax.add_patch(FancyBboxPatch((cx-0.075, cy-0.022), 0.15, 0.044,
                                    boxstyle="round,pad=0.005,rounding_size=0.022",
                                    fc="#dfeceb", ec=TEAL, lw=1.2, zorder=2))
        ax.text(cx, cy, t, ha="center", va="center", fontsize=8.6, color=INK)

    pill(0.45, 0.965, "command")
    pill(0.45, 0.032, "reply")
    for k, (cx, cy) in C.items():
        box(ax, cx-W/2, cy-H/2, W, H, k, subs[k], fs=9.2,
            fc=FILL2 if k in ("verify", "recover") else FILL)

    T = lambda k: (C[k][0], C[k][1] + H/2)
    B = lambda k: (C[k][0], C[k][1] - H/2)
    L = lambda k: (C[k][0] - W/2, C[k][1])
    R = lambda k: (C[k][0] + W/2, C[k][1])

    arrow(ax, (0.45, 0.943), T("understand"))
    arrow(ax, (0.365, 0.815), (0.225, 0.712));  label(ax, 0.212, 0.792, "names a place")
    arrow(ax, (0.535, 0.815), (0.715, 0.712));  label(ax, 0.700, 0.792, "raw motion")
    arrow(ax, B("understand"), T("answer"));    label(ax, 0.472, 0.50, "a question", rot=90)
    arrow(ax, B("navigate"), T("verify"))
    arrow(ax, B("verify"), T("recover"), AMBER); label(ax, 0.207, 0.410, "aborted", color=AMBER)
    arrow(ax, R("verify"), (0.352, 0.170), TEAL, rad=-0.32)
    label(ax, 0.352, 0.400, "succeeded", color=TEAL)
    for a, b in (((0.16-W/2, 0.325), (0.022, 0.325)), ((0.022, 0.325), (0.022, 0.665))):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-", color=AMBER, lw=1.3, zorder=1))
    arrow(ax, (0.022, 0.665), L("navigate"), AMBER)
    label(ax, 0.0065, 0.495, "retry once, then give up", color=AMBER, rot=90, fs=7.2)
    arrow(ax, B("move"), (0.548, 0.170), rad=0.30)
    arrow(ax, B("answer"), (0.45, 0.054))

    ax.legend(handles=[Line2D([], [], color=TEAL, lw=1.4, label="verification path"),
                       Line2D([], [], color=AMBER, lw=1.4, label="recovery cycle"),
                       Line2D([], [], color=RULE, lw=1.4, label="intent routing")],
              loc="lower right", fontsize=8, frameon=False, bbox_to_anchor=(1.02, 0.02))
    finish(fig, ax, "Figure3_8_command_graph")


# ---------------------------------------------------------------- 3. RAG
def rag():
    fig, ax = plt.subplots(figsize=(11, 4.6))
    label(ax, 0.02, 0.93, "INGESTION  (offline, idempotent)", color=MUTED, fs=8.4, ha="left")
    xs = [0.03, 0.215, 0.40, 0.585]
    for x, (t, s) in zip(xs, [("PDF corpus", "thesis · profile"),
                              ("per-page text", "PyMuPDF → page no."),
                              ("token-aware chunks", "1200 tok, 150 overlap"),
                              ("embeddings", "text-embedding-3-large")]):
        box(ax, x, 0.63, 0.165, 0.20, t, s)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, (a+0.165, 0.73), (b, 0.73))
    box(ax, 0.775, 0.63, 0.195, 0.20, "Pinecone", "cosine · namespaced\nper document", fc="#dbe9e7")
    arrow(ax, (0.75, 0.73), (0.775, 0.73))

    box(ax, 0.40, 0.335, 0.35, 0.14, "content-addressed embedding cache",
        "key = SHA-256 of the chunk's own text", fc="#f6efe2", ec=AMBER)
    arrow(ax, (0.575, 0.475), (0.63, 0.63), AMBER, ls=(0,(3,2)))
    label(ax, 0.755, 0.40, "unchanged text → no API call\n(60/60 hits on re-index)",
          color=AMBER, fs=7.6, ha="left")

    label(ax, 0.02, 0.24, "QUERY", color=MUTED, fs=8.4, ha="left")
    for x, (t, s) in zip([0.03, 0.215, 0.40, 0.585],
                         [("question", "speech or text"), ("embed", "same model"),
                          ("retrieve", "quota per namespace"), ("generate", "cite or decline")]):
        box(ax, x, 0.02, 0.165, 0.165, t, s)
    for a, b in zip([0.03, 0.215, 0.40], [0.215, 0.40, 0.585]):
        arrow(ax, (a+0.165, 0.1025), (b, 0.1025))
    arrow(ax, (0.4825, 0.185), (0.80, 0.63), MUTED, rad=-0.18)
    box(ax, 0.775, 0.02, 0.195, 0.165, "answer cache", "key = normalised question", fc="#f6efe2", ec=AMBER)
    arrow(ax, (0.75, 0.1025), (0.775, 0.1025), AMBER)
    label(ax, 0.8725, 0.235, "repeat question → 0 ms", color=AMBER, fs=7.6)
    finish(fig, ax, "Figure3_9_rag_pipeline")


# ---------------------------------------------------------------- 4. embodiment loop
def embodiment():
    fig, ax = plt.subplots(figsize=(10, 4.4))
    stages = [("perceive", "laser → costmaps", 0.02), ("localise", "AMCL particle filter", 0.215),
              ("plan", "NavFn over the grid", 0.41), ("control", "DWB dynamic window", 0.605),
              ("act", "wheel velocities", 0.80)]
    for t, s, x in stages:
        box(ax, x, 0.52, 0.175, 0.20, t, s,
            fc="#f6e4e0" if t == "localise" else FILL,
            ec=AMBER if t == "localise" else RULE,
            lw=1.6 if t == "localise" else 1.1)
    for a, b in zip([s[2] for s in stages][:-1], [s[2] for s in stages][1:]):
        arrow(ax, (a+0.175, 0.62), (b, 0.62))
    # feedback
    ax.add_patch(FancyArrowPatch((0.8875, 0.52), (0.8875, 0.40), arrowstyle="-", color=RULE, lw=1.2))
    ax.add_patch(FancyArrowPatch((0.8875, 0.40), (0.1075, 0.40), arrowstyle="-", color=RULE, lw=1.2))
    ax.add_patch(FancyArrowPatch((0.1075, 0.40), (0.1075, 0.52), arrowstyle="-|>", mutation_scale=12,
                                 color=RULE, lw=1.2))
    label(ax, 0.50, 0.375, "the world closes the loop", fs=8)

    label(ax, 0.02, 0.905, "where each stage can fail, and what this work measured",
          color=MUTED, fs=8.6, ha="left")
    notes = [(0.105, "scan plane hit\nthe chassis"), (0.30, "diverged up to\n15.5 m, undetected"),
             (0.497, "refused to plan\nwhen start was lethal"), (0.692, "'no valid trajectories\nout of 419'"),
             (0.887, "14% of commanded\nspeed")]
    for x, t in notes:
        label(ax, x, 0.815, t, color=AMBER if "diverged" in t else MUTED, fs=7.3)
    for x, _ in notes:
        ax.add_patch(FancyArrowPatch((x, 0.755), (x, 0.723), arrowstyle="-",
                                     color="#c9d3dc", lw=0.9))

    label(ax, 0.50, 0.20, "every stage consumes the localisation estimate as though it were fact",
          color=AMBER, fs=9)
    label(ax, 0.50, 0.115, "no component in the standard stack is positioned to audit it",
          color=AMBER, fs=9)
    finish(fig, ax, "Figure3_10_embodiment_loop")


for f in (architecture, command_graph, rag, embodiment):
    f()
print("done")
