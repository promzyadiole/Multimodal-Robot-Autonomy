from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in YAML file: {file_path}")

    return data


ENVIRONMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "environments"

# new_world is this project's own scene, paired with maps/custom_map. Override
# with the MRA_ENVIRONMENT env var (name or path) to work in another, e.g.
# MRA_ENVIRONMENT=small_house for the AWS residential house.
DEFAULT_ENVIRONMENT_CONFIG = ENVIRONMENTS_DIR / "new_world.yaml"


def resolve_environment(name_or_path: str | Path) -> Path:
    """Accept either an environment name or a path to its yaml."""
    p = Path(name_or_path).expanduser()
    if p.suffix in {".yaml", ".yml"} or p.is_absolute():
        return p
    return ENVIRONMENTS_DIR / f"{p}.yaml"


def load_environment_config(
    path: str | Path | None = None,
) -> dict[str, Any]:
    if path is None:
        path = resolve_environment(os.environ.get("MRA_ENVIRONMENT", DEFAULT_ENVIRONMENT_CONFIG))
    return load_yaml_file(path)


def load_places_config(environment_config: dict[str, Any]) -> dict[str, Any]:
    places_file = environment_config.get("places_file")
    if not places_file:
        raise ValueError("Environment config is missing 'places_file'")
    return load_yaml_file(places_file)