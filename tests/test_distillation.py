from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

from game_script_dev.authoring import check_profile_pack
from game_script_dev.distillation import (
    DistillationError,
    distill_repository,
    format_distillation_report,
    write_distillation_report,
)

COMPATIBILITY = """
    target_identity: true
    supported_resolution: true
    required_assets: true
    full_state_graph: true
    terminal_states: true
    failure_transitions: true
    interruption_recovery: true
    known_limitations: true
    successful_validation_or_dry_run: true
"""


def _profile_yaml(*, image: str = "assets/button.jpg", actions: bool = True) -> str:
    action_block = (
        """
    actions:
      - type: log
        message: Imported checkpoint
"""
        if actions
        else ""
    )
    return f"""
version: 1
name: Imported Pack
profile_pack:
  game: Example
  game_mode: Daily
  detection_strategy: template_matching
  known_limitations:
    - Requires operator review.
  compatibility:
{COMPATIBILITY}
target:
  window_title_contains: Example
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
initial_state: done
states:
  done:
    required_anchors:
      - name: done_marker
        type: template
        asset: {image}
{action_block}    terminal: true
    result: success
"""


class DistillationTests(unittest.TestCase):
    def test_dry_run_reports_conversion_without_destination_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            workspace = root / "workspace"
            pack = source / "profiles" / "example" / "daily"
            workspace.mkdir()
            _write_source_pack(pack)
            (source / "helper.py").write_text("print('not executed')", encoding="utf-8")

            report = distill_repository(
                source,
                workspace,
                Path("profiles/imported"),
            )

            self.assertTrue(report.ok, report.to_dict())
            self.assertFalse(report.applied)
            self.assertFalse((workspace / "profiles" / "imported").exists())
            self.assertGreaterEqual(report.summary["converted"], 2)
            self.assertEqual(report.summary["skipped"], 1)
            rendered = format_distillation_report(report)
            self.assertIn("Repository distillation DRY RUN: ok", rendered)
            self.assertIn("WOULD CONVERTED:", rendered)

    def test_apply_converts_all_retained_images_and_updates_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            workspace = root / "workspace"
            pack = source / "profiles" / "example" / "daily"
            workspace.mkdir()
            _write_source_pack(pack)

            report = distill_repository(
                source,
                workspace,
                Path("profiles/imported"),
                apply=True,
            )

            target = workspace / "profiles" / "imported" / "example" / "daily"
            self.assertTrue(report.ok, report.to_dict())
            self.assertTrue((target / "assets" / "button.png").is_file())
            self.assertTrue(
                (target / "validation_examples" / "valid" / "screen.png").is_file()
            )
            retained_images = [
                path
                for path in target.rglob("*")
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".ppm"}
            ]
            self.assertEqual(retained_images, [])
            raw = yaml.safe_load((target / "profile.yaml").read_text(encoding="utf-8"))
            asset = raw["states"]["done"]["required_anchors"][0]["asset"]
            self.assertEqual(asset, "assets/button.png")
            self.assertTrue(check_profile_pack(target).ok)

    def test_actionless_profile_is_reported_and_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            workspace = root / "workspace"
            pack = source / "profiles" / "empty" / "daily"
            workspace.mkdir()
            _write_source_pack(pack, actions=False)

            report = distill_repository(
                source,
                workspace,
                Path("profiles/imported"),
                apply=True,
            )

            target = workspace / "profiles" / "imported" / "empty" / "daily"
            self.assertFalse(report.ok)
            self.assertEqual(report.summary["removed"], 1)
            self.assertFalse(target.exists())
            self.assertIn("has no state Actions", report.items[0].reason)

    def test_destination_outside_workspace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            workspace = root / "workspace"
            source.mkdir()
            workspace.mkdir()

            with self.assertRaisesRegex(DistillationError, "inside the workspace"):
                distill_repository(source, workspace, root / "outside")

    def test_existing_destination_pack_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            workspace = root / "workspace"
            pack = source / "profiles" / "example" / "daily"
            target = workspace / "profiles" / "imported" / "example" / "daily"
            workspace.mkdir()
            target.mkdir(parents=True)
            marker = target / "user-file.txt"
            marker.write_text("preserve me", encoding="utf-8")
            _write_source_pack(pack)

            report = distill_repository(
                source,
                workspace,
                Path("profiles/imported"),
                apply=True,
            )

            self.assertFalse(report.ok)
            self.assertEqual(report.summary["failed"], 1)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me")
            self.assertFalse((target / "profile.yaml").exists())

    def test_json_report_requires_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            workspace = root / "workspace"
            pack = source / "profile"
            workspace.mkdir()
            _write_source_pack(pack)
            report = distill_repository(source, workspace, Path("imported"))
            report_path = write_distillation_report(report, Path("reports/run.json"))

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"], report.summary)
            self.assertFalse(payload["applied"])
            with self.assertRaisesRegex(DistillationError, "already exists"):
                write_distillation_report(report, Path("reports/run.json"))


def _write_source_pack(pack: Path, *, actions: bool = True) -> None:
    (pack / "assets").mkdir(parents=True)
    (pack / "validation_examples" / "valid").mkdir(parents=True)
    (pack / "profile.yaml").write_text(
        _profile_yaml(actions=actions),
        encoding="utf-8",
    )
    (pack / "notes.md").write_text("Operator review required.", encoding="utf-8")
    Image.new("RGB", (4, 4), "red").save(pack / "assets" / "button.jpg")
    Image.new("RGB", (4, 4), "blue").save(
        pack / "validation_examples" / "valid" / "screen.ppm"
    )


if __name__ == "__main__":
    unittest.main()
