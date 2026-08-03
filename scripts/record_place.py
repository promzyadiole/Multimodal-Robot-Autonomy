#!/usr/bin/env python3
"""Record the robot's current pose as a named place in the registry.

Drive the robot where you want the place to be, point it the way it should end
up facing, then:

    scripts/record_place.py garage
    scripts/record_place.py parlour --alias "living room" --alias lounge
    scripts/record_place.py --list
    scripts/record_place.py --check          # audit every place against the map

The pose is taken from TF ``map -> base_link``, because that is the frame nav2
plans in and therefore the only frame a goal is meaningful in. Gazebo's ground
truth is read as well, purely to report the gap: if localisation is off by half
a metre when you record, that error is baked into the place forever, so the tool
refuses to record when the two disagree badly.

Places are written to the environment's registry file, preserving any aliases
already there. Existing entries are updated in place rather than duplicated.
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO / "backend/app/data/places/new_world_places.yaml"

# Refuse to record a place if belief and truth differ by more than this. A place
# is a permanent coordinate; recording it while mislocalised is a silent, lasting
# error of exactly the kind this project exists to catch.
MAX_DISAGREEMENT_M = 0.35


def truth() -> tuple[float, float, float] | None:
    """Gazebo's own pose for the robot, or None if the simulator is not up."""
    try:
        out = subprocess.run(["gz", "model", "-m", "romr", "-p"],
                             capture_output=True, text=True, timeout=25).stdout.split()
        return (float(out[0]), float(out[1]), float(out[5])) if len(out) >= 6 else None
    except Exception:  # noqa: BLE001
        return None


def believed() -> tuple[float, float, float]:
    """Pose from TF map -> base_link. This is what a goal is expressed against."""
    import rclpy
    from rclpy.duration import Duration
    from tf2_ros import Buffer, TransformListener

    rclpy.init()
    node = rclpy.create_node("record_place")
    buf = Buffer()
    TransformListener(buf, node)
    deadline = time.time() + 10.0
    tr = None
    while time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        try:
            tr = buf.lookup_transform("map", "base_link", rclpy.time.Time(),
                                      timeout=Duration(seconds=0.5))
            break
        except Exception:  # noqa: BLE001
            continue
    rclpy.shutdown()
    if tr is None:
        raise SystemExit(
            "No map -> base_link transform. Is nav2 (or SLAM) running and localised?"
        )
    t, q = tr.transform.translation, tr.transform.rotation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    return t.x, t.y, yaw


def load(path: Path) -> dict:
    import yaml
    if path.exists():
        return yaml.safe_load(path.read_text()) or {"places": {}}
    return {"places": {}}


def save(path: Path, doc: dict) -> None:
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(doc, sort_keys=False, default_flow_style=False))
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="canonical place name, e.g. garage")
    ap.add_argument("--alias", action="append", default=[],
                    help="phrasing that should also resolve here; repeatable")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--list", action="store_true", help="show the current registry")
    ap.add_argument("--force", action="store_true",
                    help="record even if belief and truth disagree")
    args = ap.parse_args()

    path = Path(args.registry)
    doc = load(path)
    places = doc.setdefault("places", {})

    if args.list or not args.name:
        print(f"{'place':18} {'x':>8} {'y':>8} {'yaw':>8}   aliases")
        for n, p in places.items():
            yaw = 2 * math.atan2(p.get("qz", 0.0), p.get("qw", 1.0))
            print(f"{n:18} {p['x']:8.3f} {p['y']:8.3f} {yaw:8.3f}   "
                  f"{', '.join(p.get('aliases') or [])}")
        return 0

    bx, by, byaw = believed()
    t = truth()

    print(f"  believed (map frame) : {bx:+.3f}, {by:+.3f}  yaw {math.degrees(byaw):+.1f}°")
    if t is not None:
        gap = math.dist((bx, by), t[:2])
        print(f"  gazebo ground truth  : {t[0]:+.3f}, {t[1]:+.3f}  yaw {math.degrees(t[2]):+.1f}°")
        print(f"  disagreement         : {gap:.3f} m")
        if gap > MAX_DISAGREEMENT_M and not args.force:
            print(f"\n  REFUSING to record: belief and truth differ by {gap:.2f} m "
                  f"(limit {MAX_DISAGREEMENT_M}).")
            print("  Re-seed localisation, let it settle, and try again — or pass --force.")
            print("  A place recorded while mislocalised stays wrong for every future run.")
            return 1
    else:
        print("  gazebo ground truth  : unavailable (simulator not running)")

    existing = places.get(args.name, {})
    aliases = list(dict.fromkeys((existing.get("aliases") or []) + args.alias))
    if args.name not in aliases:
        aliases.insert(0, args.name)

    places[args.name] = {
        "x": round(bx, 4),
        "y": round(by, 4),
        "z": 0.0,
        "qz": round(math.sin(byaw / 2), 6),
        "qw": round(math.cos(byaw / 2), 6),
        "aliases": aliases,
        **({"metadata": existing["metadata"]} if "metadata" in existing else {}),
    }
    save(path, doc)
    verb = "updated" if existing else "recorded"
    print(f"\n  {verb} '{args.name}' in {path.relative_to(REPO)}")
    print(f"  aliases: {', '.join(aliases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
