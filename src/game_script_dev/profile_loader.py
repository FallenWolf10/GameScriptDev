from __future__ import annotations

from pathlib import Path

import yaml

from game_script_dev.schema import Profile, profile_from_mapping


class ProfileLoadError(Exception):
    """Raised when a profile file cannot be loaded."""


def load_profile(path: Path) -> Profile:
    if not path.exists():
        raise ProfileLoadError(f"profile does not exist: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ProfileLoadError(f"invalid YAML in {path}: {error}") from error

    if not isinstance(raw, dict):
        raise ProfileLoadError("profile root must be a mapping")

    try:
        return profile_from_mapping(raw)
    except (TypeError, ValueError) as error:
        raise ProfileLoadError(str(error)) from error
