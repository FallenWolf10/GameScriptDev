from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from game_script_dev.profile_loader import ProfileLoadError, load_profile
from game_script_dev.schema import (
    REQUIRED_COMPATIBILITY_CHECKS,
    ProfileValidationError,
    validate_profile,
)

PROFILE_TEMPLATE = """version: 1
name: {name}

profile_pack:
  game: {game}
  game_mode: {mode}
  detection_strategy: template_matching
  known_limitations:
    - Replace with target-specific limitations before live use.
  compatibility:
{compatibility}

target:
  window_title_contains: {window_title}
  input_mode: background_window_messages

window:
  resolution:
    width: 1280
    height: 720
    policy: verify_only

execution:
  max_retries: 1

initial_state: {initial_state}

states:
  {initial_state}:
    required_anchors:
      - name: {initial_state}_title
        type: text
        text: {initial_state_label}
    terminal: true
    result: success
"""

NOTES_TEMPLATE = """# {name}

## Known Limitations

- Replace this placeholder before live use.
"""


@dataclass(frozen=True)
class PackCheckResult:
    path: Path
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def scaffold_profile_pack(
    pack_dir: Path,
    *,
    game: str,
    mode: str,
    name: str | None = None,
    initial_state: str = "home",
) -> list[Path]:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", initial_state):
        raise ValueError(
            "initial_state must start with a lowercase letter and contain only "
            "lowercase letters, numbers, and underscores"
        )
    profile_name = name or f"{game} {mode}"
    pack_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = pack_dir / "assets"
    valid_dir = pack_dir / "validation_examples" / "valid"
    invalid_dir = pack_dir / "validation_examples" / "invalid"
    for directory in (assets_dir, valid_dir, invalid_dir):
        directory.mkdir(parents=True, exist_ok=True)
        keep_path = directory / ".gitkeep"
        if not keep_path.exists():
            keep_path.write_text("", encoding="utf-8")

    compatibility = "".join(
        f"    {check}: false\n" for check in sorted(REQUIRED_COMPATIBILITY_CHECKS)
    )
    profile_path = pack_dir / "profile.yaml"
    notes_path = pack_dir / "notes.md"
    if not profile_path.exists():
        profile_path.write_text(
            PROFILE_TEMPLATE.format(
                name=_yaml_string(profile_name),
                game=_yaml_string(game),
                mode=_yaml_string(mode),
                window_title=_yaml_string("Replace Me"),
                initial_state=initial_state,
                initial_state_label=_yaml_string(
                    initial_state.replace("_", " ").title()
                ),
                compatibility=compatibility.rstrip(),
            ),
            encoding="utf-8",
        )
    if not notes_path.exists():
        notes_path.write_text(
            NOTES_TEMPLATE.format(name=profile_name),
            encoding="utf-8",
        )
    return [profile_path, notes_path, assets_dir, valid_dir, invalid_dir]


def check_profile_pack(pack_dir: Path) -> PackCheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    profile_path = pack_dir / "profile.yaml"
    notes_path = pack_dir / "notes.md"
    assets_dir = pack_dir / "assets"
    valid_dir = pack_dir / "validation_examples" / "valid"
    invalid_dir = pack_dir / "validation_examples" / "invalid"
    if not profile_path.is_file():
        errors.append("profile.yaml is required")
    if not notes_path.is_file():
        errors.append("notes.md is required")
    elif not notes_path.read_text(encoding="utf-8").strip():
        errors.append("notes.md must not be empty")
    if not assets_dir.is_dir():
        errors.append("assets/ directory is required")
    if not valid_dir.is_dir():
        errors.append("validation_examples/valid/ directory is required")
    if not invalid_dir.is_dir():
        errors.append("validation_examples/invalid/ directory is required")

    if profile_path.is_file():
        try:
            profile = load_profile(profile_path)
            validate_profile(profile, pack_dir)
            if profile.profile_pack is None:
                errors.append("profile_pack metadata is required")
            else:
                missing = profile.profile_pack.missing_compatibility_checks
                if missing:
                    warnings.append(
                        "profile_pack compatibility incomplete: " + ", ".join(missing)
                    )
                if not profile.profile_pack.known_limitations:
                    errors.append(
                        "profile_pack.known_limitations must include at least one item"
                    )
        except (ProfileLoadError, ProfileValidationError, ValueError) as error:
            errors.append(str(error))

    return PackCheckResult(path=pack_dir, ok=not errors, errors=errors, warnings=warnings)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
