from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class FixtureManifest:
    name: str
    safe_to_commit: bool
    contains_third_party_content: bool
    provenance: str
    states: list[str]
    files: list[str]
    expected_anchors: list[str]
    limitations: list[str]


def load_fixture_manifest(path: Path) -> FixtureManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return FixtureManifest(
        name=str(raw["name"]),
        safe_to_commit=bool(raw.get("safe_to_commit", raw.get("safe", False))),
        contains_third_party_content=bool(
            raw.get("contains_third_party_content", False)
        ),
        provenance=str(raw.get("provenance", "")),
        states=[str(state) for state in raw.get("states", [])],
        files=[str(file_name) for file_name in raw.get("files", [])],
        expected_anchors=[
            str(anchor) for anchor in raw.get("expected_anchors", [])
        ],
        limitations=[str(item) for item in raw.get("limitations", [])],
    )


def validate_fixture_pack(fixture_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = fixture_dir / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is required"]

    manifest = load_fixture_manifest(manifest_path)
    if not manifest.safe_to_commit:
        errors.append("fixture manifest must set safe_to_commit=true")
    if manifest.contains_third_party_content:
        errors.append("fixture manifest must not contain third-party content")
    if not manifest.provenance:
        errors.append("fixture manifest must document provenance")
    if not manifest.states:
        errors.append("fixture manifest must list expected states")
    if not manifest.expected_anchors:
        errors.append("fixture manifest must list expected anchors")
    for file_name in manifest.files:
        path = fixture_dir / file_name
        if not path.is_file():
            errors.append(f"fixture file missing: {file_name}")
            continue
        if path.suffix.lower() == ".png":
            try:
                with Image.open(path) as image:
                    image.verify()
            except Exception as error:
                errors.append(f"fixture image invalid: {file_name}: {error}")
    return errors
