#!/usr/bin/env python3
"""Run a language-command suite against the live stack and report the results.

The CPS thesis objectives call for validation with 50+ language commands. This
drives the real path a user takes -- natural language into the backend, intent
parsing, place resolution, nav2 -- and records what actually happened, so the
numbers are measured rather than asserted.

Two modes:

  --mode chat    POST /api/chat/command        (dispatch, no outcome check)
  --mode graph   POST /api/chat/graph-command  (waits for the real outcome,
                                                clears costmaps and retries once)

Each trial records the phrasing, the intent the parser returned, the place it
resolved to, whether that matched what the phrasing asked for, the nav2
outcome, and the final distance to the target. Results go to CSV and a summary
table.

  scripts/validate_commands.py --mode graph --out results.csv
  scripts/validate_commands.py --mode graph --limit 8      # quick smoke run

Needs the sim, nav2 and the backend up, and AMCL seeded.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
import urllib.error
import urllib.request

API = "http://localhost:8000"

# Phrasings per destination. Deliberately varied: bare names, polite requests,
# aliases from the registry, indirect phrasing, and articles/filler that a
# brittle parser would trip on.
PHRASINGS: dict[str, list[str]] = {
    "kitchen": [
        "go to the kitchen",
        "kitchen",
        "please head to the kitchen",
        "can you drive to the kitchen",
        "move to the kitchen now",
        "I need you in the kitchen",
        "navigate to kitchen",
        "take yourself to the kitchen",
    ],
    "parlour": [
        "go to the parlour",
        "go to the living room",
        "head to the lounge",
        "drive to the sitting room",
        "please go to the parlour",
        "move to the living room",
        "navigate to the lounge",
    ],
    "garage": [
        "go to the garage",
        "drive into the garage",
        "please move to the garage",
        "head over to the garage",
        "navigate to the garage",
        "take the robot to the garage",
        "go park in the garage",
        "could you go to the garage",
    ],
    "store_area": [
        "go to the store area",
        "head to the storage",
        "drive to the store",
        "please go to the store area",
        "move to storage",
        "navigate to the store area",
        "go to the storage area",
        "drive over to the store area",
    ],
    "dining_room": [
        "go to the dining room",
        "head to the dining area",
        "please drive to the dining room",
        "move to the dining room",
        "navigate to the dining area",
        "take me to the dining room",
        "go and wait in the dining room",
        "head for the dining area please",
    ],
    "master_bedroom": [
        "go to the master bedroom",
        "head to the bedroom",
        "please go to the master bedroom",
        "drive to the bedroom",
        "navigate to the master bedroom",
        "move to the master bedroom",
        "go up to the master bedroom",
        "please make your way to the bedroom",
    ],
    "home": [
        "go home",
        "return home",
        "head back home",
        "please go to home",
        "navigate home",
        "take the robot home",
        "go back to home base",
    ],
}


def post(path: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def get(path: str, timeout: float = 20.0) -> dict:
    with urllib.request.urlopen(API + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def places() -> dict[str, dict]:
    return get("/api/navigation/places")["data"]["places"]


def pose() -> tuple[float, float] | None:
    st = get("/api/robot/status")
    p = st.get("current_pose")
    return (p["x"], p["y"]) if p else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["chat", "graph"], default="graph")
    ap.add_argument("--out", default="validation_results.csv")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N trials")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--settle", type=float, default=3.0, help="pause between trials")
    args = ap.parse_args()

    try:
        reg = places()
    except (urllib.error.URLError, OSError) as exc:
        print(f"backend not reachable at {API}: {exc}")
        return 1

    if not get("/api/robot/status").get("nav2_ready"):
        print("nav2 is not ready — start it and seed AMCL before validating.")
        return 1

    trials: list[tuple[str, str]] = [
        (place, text) for place, texts in PHRASINGS.items() for text in texts
        if place in reg
    ]
    random.Random(args.seed).shuffle(trials)
    if args.limit:
        trials = trials[: args.limit]

    endpoint = "/api/chat/command" if args.mode == "chat" else "/api/chat/graph-command"
    print(f"{len(trials)} commands via {endpoint}\n")
    print(f"{'#':>3}  {'phrasing':38} {'resolved':15} {'ok':3} {'outcome':10} {'err(m)':>7}")

    rows = []
    for i, (expected, text) in enumerate(trials, 1):
        target = reg[expected]
        t0 = time.time()
        try:
            resp = post(endpoint, {"command": text}, args.timeout)
        except Exception as exc:  # noqa: BLE001
            rows.append({"n": i, "phrasing": text, "expected": expected, "resolved": "",
                         "correct": False, "outcome": f"error:{type(exc).__name__}",
                         "error_m": "", "seconds": round(time.time() - t0, 1)})
            print(f"{i:3}  {text[:38]:38} {'-':15} {'no':3} {'ERROR':10} {'':>7}")
            time.sleep(args.settle)
            continue

        d = resp.get("data") or {}
        resolved = d.get("place") or d.get("target_place") or ""
        outcome = d.get("outcome") or ("dispatched" if resp.get("success") else "refused")
        correct = resolved == expected

        p = pose()
        err = (
            math.dist(p, (float(target["x"]), float(target["y"])))
            if p and correct else None
        )
        rows.append({
            "n": i, "phrasing": text, "expected": expected, "resolved": resolved,
            "correct": correct, "outcome": outcome,
            "error_m": round(err, 3) if err is not None else "",
            "seconds": round(time.time() - t0, 1),
        })
        print(f"{i:3}  {text[:38]:38} {resolved[:15]:15} "
              f"{'yes' if correct else 'NO':3} {str(outcome)[:10]:10} "
              f"{err if err is not None else float('nan'):7.3f}")
        time.sleep(args.settle)

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    understood = sum(1 for r in rows if r["correct"])
    arrived = sum(1 for r in rows if r["outcome"] == "succeeded")
    errs = [r["error_m"] for r in rows if isinstance(r["error_m"], float)]
    print(f"\n{'-'*72}")
    print(f"commands run            {n}")
    print(f"resolved to the right place  {understood}/{n}  ({100*understood/n:.0f}%)")
    if args.mode == "graph":
        print(f"confirmed arrival            {arrived}/{n}  ({100*arrived/n:.0f}%)")
    if errs:
        errs_sorted = sorted(errs)
        print(f"final error   mean {sum(errs)/len(errs):.3f} m   "
              f"median {errs_sorted[len(errs)//2]:.3f} m   max {max(errs):.3f} m")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
