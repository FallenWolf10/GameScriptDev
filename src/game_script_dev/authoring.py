from __future__ import annotations

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
  window_title_contains: Replace Me

window:
  resolution:
    width: 1280
    height: 720
    policy: verify_only

execution:
  max_retries: 1

initial_state: home

states:
  home:
    required_anchors:
      - name: home_title
        type: text
        text: Home
    terminal: true
    result: success
"""

NOTES_TEMPLATE = """# {name}

## Expansion Review

Status: deferred

- Target rules reviewed: no
- Permitted local automation documented: no
- Operator confirmation recorded: no

## Known Limitations

- Replace this placeholder before live use.

## Do Not Automate

- Anti-cheat bypass, stealth behavior, account farming, monetized grinding, and
  evasion logic remain outside the project boundary.
"""


@dataclass(frozen=True)
class PackCheckResult:
    path: Path
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def scaffold_profile_pack(pack_dir: Path, *, game: str, mode: str) -> list[Path]:
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
                name=f"{game} {mode}",
                game=game,
                mode=mode,
                compatibility=compatibility.rstrip(),
            ),
            encoding="utf-8",
        )
    if not notes_path.exists():
        notes_path.write_text(
            NOTES_TEMPLATE.format(name=f"{game} {mode}"),
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
    expansion_review = pack_dir / "expansion_review.md"

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

    if not _is_demo_pack(pack_dir):
        if not expansion_review.is_file():
            errors.append("expansion_review.md is required for real target packs")
        elif not expansion_review_complete(expansion_review):
            errors.append(
                "expansion_review.md must document reviewed rules, permitted "
                "automation, operator confirmation, and do-not-automate boundaries"
            )

    return PackCheckResult(path=pack_dir, ok=not errors, errors=errors, warnings=warnings)


def expansion_review_complete(review_path: Path) -> bool:
    if not review_path.is_file():
        return False
    text = review_path.read_text(encoding="utf-8").lower()
    required = (
        "expansion review",
        "target rules reviewed: yes",
        "permitted local automation documented: yes",
        "operator confirmation recorded: yes",
        "do not automate",
    )
    return all(item in text for item in required)


def _is_demo_pack(pack_dir: Path) -> bool:
    parts = pack_dir.as_posix().lower().split("/")
    return "profiles" in parts and "demo" in parts
