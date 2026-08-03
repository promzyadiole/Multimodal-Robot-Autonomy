from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class YAMLRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Registry file not found: {self.path}")

        with self.path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def reload(self) -> None:
        self.data = self._load()

    def resolve_place(self, name: str) -> Optional[Dict[str, Any]]:
        name = name.strip().lower()

        for place_key, place_data in self.data.get("places", {}).items():
            aliases = [place_key] + place_data.get("aliases", [])
            aliases = [a.lower() for a in aliases]

            if name in aliases:
                return {"key": place_key, **place_data}

        return None

    def resolve_route(self, route_name: str) -> Optional[Dict[str, Any]]:
        route_name = route_name.strip().lower()

        for route_key, route_data in self.data.get("routes", {}).items():
            aliases = [route_key] + route_data.get("aliases", [])
            aliases = [a.lower() for a in aliases]

            if route_name in aliases:
                return {"key": route_key, **route_data}

        return None

    def resolve_motion(self, motion_name: str) -> Optional[Dict[str, Any]]:
        motion_name = motion_name.strip().lower()

        motions = self.data.get("motions", {})
        for motion_key, motion_data in motions.items():
            aliases = [motion_key] + motion_data.get("aliases", [])
            aliases = [a.lower() for a in aliases]

            if motion_name in aliases:
                return {"key": motion_key, **motion_data}

        return None

    def get_vision_labels(self) -> list[str]:
        return self.data.get("vision_labels", [])


_yaml_registry: Optional[YAMLRegistry] = None


def get_yaml_registry() -> YAMLRegistry:
    """Actions and motions from robot_actions.yaml, places from the environment.

    These were one file, and the split mattered. robot_actions.yaml carries the
    motion primitives and route definitions, which do not change when the map
    does; the *places* are map-specific, and are recorded per environment into
    data/places/<environment>_places.yaml by scripts/record_place.py.

    Loading both from robot_actions.yaml meant the action mapper dispatched a
    goal using coordinates from an older map while /api/navigation/places served
    the current ones. Nothing errored: the robot simply drove to where the room
    used to be, and every arrival was measured against a coordinate it was never
    sent to. Places recorded after a re-map now take precedence.
    """
    global _yaml_registry

    if _yaml_registry is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        _yaml_registry = YAMLRegistry(data_dir / "robot_actions.yaml")

        try:
            from app.services.environment_service import get_environment_service

            env = get_environment_service().environment
            places_file = env.get("places_file")
            if places_file:
                path = data_dir / "places" / Path(places_file).name
                if path.exists():
                    with open(path) as fh:
                        places = (yaml.safe_load(fh) or {}).get("places") or {}
                    if places:
                        # The two files disagree on shape: robot_actions.yaml
                        # nests pose: {x, y, yaw}, while record_place.py writes
                        # flat x/y with a quaternion, because that is what a TF
                        # lookup and a nav2 goal both use. Normalise to the
                        # nested form the action mapper expects.
                        for name, place in places.items():
                            if "pose" not in place and "x" in place:
                                yaw = 2.0 * math.atan2(
                                    float(place.get("qz", 0.0)),
                                    float(place.get("qw", 1.0)),
                                )
                                place["pose"] = {
                                    "x": float(place["x"]),
                                    "y": float(place["y"]),
                                    "yaw": yaw,
                                }
                        _yaml_registry.data["places"] = places
        except Exception:  # noqa: BLE001
            # keep the robot usable on the built-in places if the environment
            # cannot be read; the mismatch is logged by the places endpoint
            pass

    return _yaml_registry