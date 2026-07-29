from __future__ import annotations

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


DEFAULT_ENVIRONMENT_CONFIG = (
    Path(__file__).resolve().parents[1] / "data" / "environments" / "small_house.yaml"
)


def load_environment_config(
    path: str | Path = DEFAULT_ENVIRONMENT_CONFIG,
) -> dict[str, Any]:
    return load_yaml_file(path)


def load_places_config(environment_config: dict[str, Any]) -> dict[str, Any]:
    places_file = environment_config.get("places_file")
    if not places_file:
        raise ValueError("Environment config is missing 'places_file'")
    return load_yaml_file(places_file)