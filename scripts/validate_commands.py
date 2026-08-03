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

Each trial records the phrasing, the place it resolved to, whether that matched
what the phrasing asked for, the nav2 outcome, and three distances: to the goal
from Gazebo ground truth, to the goal as AMCL believes it, and the gap between
those two. Results go to CSV and a summary table.

Arrival is scored against **ground truth**. nav2 reporting "succeeded" only
means AMCL believes it arrived; that was measured being wrong by 9.6 m, so the
summary reports claimed success and real arrival separately, and counts the
false positives between them.

Each trial begins correctly localised: if the robot has left the mapped area it
is returned to the spawn pose, and if belief and truth differ by more than
RELOCALISE_ABOVE_M the estimate is re-seeded from truth. Both events are
counted and reported, since needing them is itself a result.

  scripts/validate_commands.py --mode graph --out results.csv
  scripts/validate_commands.py --mode graph --limit 8      # quick smoke run

Needs the sim, nav2 and the backend up, and `gz` on PATH for ground truth.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
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
        "take yourself to the cooking area",
    ],
    "parlour": [
        "go to the parlour",
        "go to the living room",
        "head to the lounge",
        "drive to the sitting room",
        "please go to the parlour",
        "move to the living area",
        "navigate to the lounge",
    ],
    "waiting_area": [
        "go to the waiting area",
        "drive to the visitors waiting area",
        "head to reception",
        "please go to the lobby",
        "take the robot to the waiting area",
        "navigate to the visitors area",
        "wait in the waiting area",
    ],
    "garage": [
        "go to the garage",
        "drive into the garage",
        "please move to the garage",
        "head over to the garage",
        "navigate to the garage",
        "take the robot to the car park",
        "go park in the parking space",
        "could you go to the garage",
    ],
    "store_area": [
        "go to the store area",
        "head to the storage",
        "drive to the store",
        "please go to the store area",
        "move to storage",
        "navigate to the storage area",
        "go to the store room",
        "drive over to the storeroom",
    ],
    "dining_room": [
        "go to the dining room",
        "head to the dining area",
        "please drive to the dining room",
        "move to the dining room",
        "navigate to the dining area",
        "take me to the dinner table",
        "go and wait in the dining room",
        "head for the dining area please",
    ],
    "master_bedroom": [
        "go to the master bedroom",
        "head to the bedroom",
        "please go to the master bedroom",
        "drive to the bedroom",
        "navigate to the main bedroom",
        "move to the master room",
        "go up to the master bedroom",
        "please make your way to the bedroom",
    ],
    "home": [
        "go home",
        "return home",
        "head back home",
        "please go to home base",
        "navigate home",
        "take the robot to the docking station",
        "go back to base",
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
    """The robot's *believed* pose, as AMCL reports it through the backend."""
    st = get("/api/robot/status")
    p = st.get("current_pose")
    return (p["x"], p["y"]) if p else None


# --- ground truth ------------------------------------------------------
#
# AMCL's estimate is the thing under test, so it cannot also be the ruler.
# It was measured diverging by up to 10.5 m from the simulator's own state,
# while nav2 still reported "succeeded", so arrival scored against /amcl_pose
# measures the robot's belief rather than where it physically is. Gazebo is
# the only ground truth available here.
#
# The map frame and the world frame coincide in this environment (the place
# registry was georeferenced onto the world), so no transform is needed.

MAP_BOUNDS = (-6.68, 7.17, -7.95, 3.65)    # xmin xmax ymin ymax of custom_map_v2
RELOCALISE_ABOVE_M = 1.0            # belief-vs-truth error we refuse to start a trial with
SPAWN = (-2.92, -3.43, 0.0)         # the launch spawn pose, used to recover an escape


def truth() -> tuple[float, float, float] | None:
    """(x, y, yaw) of the robot in Gazebo, i.e. where it actually is."""
    try:
        out = subprocess.run(
            ["gz", "model", "-m", "romr", "-p"],
            capture_output=True, text=True, timeout=25,
        ).stdout.split()
        return (float(out[0]), float(out[1]), float(out[5])) if len(out) >= 6 else None
    except Exception:  # noqa: BLE001
        return None


def inside_map(x: float, y: float) -> bool:
    x0, x1, y0, y1 = MAP_BOUNDS
    return x0 <= x <= x1 and y0 <= y <= y1


def teleport(x: float, y: float, yaw: float = 0.0) -> None:
    """Put the robot back inside the building after it has driven out of the map."""
    subprocess.run(
        ["gz", "model", "-m", "romr", "-x", str(x), "-y", str(y), "-z", "0.16",
         "-R", "0", "-P", "0", "-Y", str(yaw)],
        capture_output=True, timeout=25,
    )
    time.sleep(3.0)


class Localiser:
    """Re-seeds AMCL from ground truth and clears the costmaps.

    Trials are made independent on purpose. Run back-to-back without this,
    a single divergence poisons every remaining trial -- the robot follows a
    valid map-frame path into a wall, its believed pose lands in an inflated
    cell, and the planner then refuses *every* goal. That cascade is a real
    property of the system and is reported separately, but averaged into a
    per-command success rate it would say more about trial ordering than
    about language understanding. Each re-seed is counted and reported.
    """

    def __init__(self) -> None:
        self.ok = False
        try:
            import rclpy  # noqa: PLC0415
            from geometry_msgs.msg import PoseWithCovarianceStamped  # noqa: PLC0415
            from nav2_msgs.srv import ClearEntireCostmap  # noqa: PLC0415

            self._rclpy = rclpy
            self._Msg = PoseWithCovarianceStamped
            self._Clear = ClearEntireCostmap
            rclpy.init()
            self._node = rclpy.create_node("validation_localiser")
            self._pub = self._node.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
            time.sleep(1.0)
            self.ok = True
        except Exception as exc:  # noqa: BLE001
            print(f"  (no ROS available for re-seeding: {exc}; trials will run uncorrected)")

    def reseed(self, x: float, y: float, yaw: float) -> None:
        if not self.ok:
            return
        m = self._Msg()
        m.header.frame_id = "map"
        m.pose.pose.position.x = x
        m.pose.pose.position.y = y
        m.pose.pose.orientation.z = math.sin(yaw / 2.0)
        m.pose.pose.orientation.w = math.cos(yaw / 2.0)
        m.pose.covariance[0] = 0.05
        m.pose.covariance[7] = 0.05
        m.pose.covariance[35] = 0.02
        for _ in range(6):
            m.header.stamp = self._node.get_clock().now().to_msg()
            self._pub.publish(m)
            self._rclpy.spin_once(self._node, timeout_sec=0.2)
            time.sleep(0.35)
        for svc in ("/global_costmap/clear_entirely_global_costmap",
                    "/local_costmap/clear_entirely_local_costmap"):
            cli = self._node.create_client(self._Clear, svc)
            if cli.wait_for_service(timeout_sec=6.0):
                fut = cli.call_async(self._Clear.Request())
                self._rclpy.spin_until_future_complete(self._node, fut, timeout_sec=6.0)
        time.sleep(2.0)

    def shutdown(self) -> None:
        if self.ok:
            try:
                self._rclpy.shutdown()
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["chat", "graph"], default="graph")
    ap.add_argument("--out", default="validation_results.csv")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N trials")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--settle", type=float, default=3.0, help="pause between trials")
    ap.add_argument("--arrival-tol", type=float, default=0.5,
                    help="metres from the goal, against ground truth, that counts as arrived")
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
    print(f"{len(trials)} commands via {endpoint}")
    print("arrival is scored against Gazebo ground truth, not AMCL\n")
    print(f"{'#':>3}  {'phrasing':34} {'resolved':15} {'ok':3} {'outcome':10} "
          f"{'true':>6} {'amcl':>6} {'drift':>6}")

    loc = Localiser()
    rows = []
    relocalisations = 0
    escapes = 0

    for i, (expected, text) in enumerate(trials, 1):
        target = reg[expected]
        gx, gy = float(target["x"]), float(target["y"])

        # --- start the trial correctly localised -----------------------
        t_start = truth()
        seeded = False
        if t_start is not None:
            if not inside_map(t_start[0], t_start[1]):
                escapes += 1
                teleport(*SPAWN)
                t_start = truth() or SPAWN
                loc.reseed(t_start[0], t_start[1], t_start[2])
                seeded = True
            else:
                believed = pose()
                if believed and math.dist(believed, t_start[:2]) > RELOCALISE_ABOVE_M:
                    loc.reseed(*t_start)
                    seeded = True
        if seeded:
            relocalisations += 1

        t0 = time.time()
        try:
            resp = post(endpoint, {"command": text}, args.timeout)
        except Exception as exc:  # noqa: BLE001
            rows.append({"n": i, "phrasing": text, "expected": expected, "resolved": "",
                         "correct": False, "outcome": f"error:{type(exc).__name__}",
                         "error_true_m": "", "error_amcl_m": "", "amcl_drift_m": "",
                         "reseeded": seeded, "seconds": round(time.time() - t0, 1)})
            print(f"{i:3}  {text[:34]:34} {'-':15} {'no':3} {'ERROR':10}")
            time.sleep(args.settle)
            continue

        d = resp.get("data") or {}
        resolved = d.get("place") or d.get("target_place") or ""
        outcome = d.get("outcome") or ("dispatched" if resp.get("success") else "refused")
        correct = resolved == expected

        t_end = truth()
        believed = pose()
        err_true = math.dist(t_end[:2], (gx, gy)) if (t_end and correct) else None
        err_amcl = math.dist(believed, (gx, gy)) if (believed and correct) else None
        drift = math.dist(believed, t_end[:2]) if (believed and t_end) else None

        rows.append({
            "n": i, "phrasing": text, "expected": expected, "resolved": resolved,
            "correct": correct, "outcome": outcome,
            "error_true_m": round(err_true, 3) if err_true is not None else "",
            "error_amcl_m": round(err_amcl, 3) if err_amcl is not None else "",
            "amcl_drift_m": round(drift, 3) if drift is not None else "",
            "reseeded": seeded,
            "seconds": round(time.time() - t0, 1),
        })
        fmt = lambda v: f"{v:6.3f}" if v is not None else "     -"  # noqa: E731
        print(f"{i:3}  {text[:34]:34} {resolved[:15]:15} "
              f"{'yes' if correct else 'NO':3} {str(outcome)[:10]:10} "
              f"{fmt(err_true)} {fmt(err_amcl)} {fmt(drift)}")
        time.sleep(args.settle)

    loc.shutdown()

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def stats(key: str) -> tuple[float, float, float] | None:
        vals = sorted(r[key] for r in rows if isinstance(r[key], float))
        if not vals:
            return None
        return sum(vals) / len(vals), vals[len(vals) // 2], max(vals)

    n = len(rows)
    understood = sum(1 for r in rows if r["correct"])
    claimed = sum(1 for r in rows if r["outcome"] == "succeeded")
    # arrival is only real if the robot is physically at the goal
    arrived = sum(1 for r in rows
                  if isinstance(r["error_true_m"], float)
                  and r["error_true_m"] <= args.arrival_tol)
    false_pos = sum(1 for r in rows
                    if r["outcome"] == "succeeded"
                    and isinstance(r["error_true_m"], float)
                    and r["error_true_m"] > args.arrival_tol)

    print(f"\n{'-'*78}")
    print(f"commands run                      {n}")
    print(f"resolved to the right place       {understood}/{n}  ({100*understood/n:.0f}%)")
    if args.mode == "graph":
        print(f"nav2 *reported* success           {claimed}/{n}  ({100*claimed/n:.0f}%)")
        print(f"actually arrived (<= {args.arrival_tol} m truth)  "
              f"{arrived}/{n}  ({100*arrived/n:.0f}%)")
        print(f"  of which falsely reported ok    {false_pos}"
              f"   <-- nav2 said succeeded while physically elsewhere")
    for key, name in (("error_true_m", "true position error"),
                      ("error_amcl_m", "AMCL-scored error "),
                      ("amcl_drift_m", "AMCL belief drift  ")):
        s = stats(key)
        if s:
            print(f"{name}  mean {s[0]:6.3f} m   median {s[1]:6.3f} m   max {s[2]:7.3f} m")
    print(f"re-localisations needed           {relocalisations}/{n}")
    print(f"robot found outside the map       {escapes}")
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
