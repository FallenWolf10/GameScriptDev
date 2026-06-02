from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from game_script_dev.authoring import (
    check_profile_pack,
    scaffold_profile_pack,
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


REAL_PACK = f"""
version: 1
name: Real Pack
profile_pack:
  game: Example Game
  game_mode: Daily
  detection_strategy: template_matching
  known_limitations:
    - Operator-reviewed example.
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
      - name: done_title
        type: text
        text: Done
    terminal: true
    result: success
"""


class AuthoringTests(unittest.TestCase):
    def test_scaffold_profile_pack_creates_expected_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_dir = Path(temp_dir) / "pack"

            created = scaffold_profile_pack(pack_dir, game="Example", mode="Daily")

            self.assertIn(pack_dir / "profile.yaml", created)
            self.assertTrue((pack_dir / "notes.md").is_file())
            self.assertTrue((pack_dir / "assets" / ".gitkeep").is_file())
            self.assertTrue(
                (pack_dir / "validation_examples" / "valid" / ".gitkeep").is_file()
            )
            self.assertTrue(
                (pack_dir / "validation_examples" / "invalid" / ".gitkeep").is_file()
            )
            profile_text = (pack_dir / "profile.yaml").read_text(encoding="utf-8")
            self.assertIn("input_mode: background_window_messages", profile_text)

    def test_real_pack_passes_without_extra_review_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_dir = Path(temp_dir) / "profiles" / "example" / "daily"
            _write_real_pack(pack_dir)

            result = check_profile_pack(pack_dir)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.warnings, [])


def _write_real_pack(pack_dir: Path) -> None:
    pack_dir.mkdir(parents=True)
    (pack_dir / "assets").mkdir()
    (pack_dir / "validation_examples" / "valid").mkdir(parents=True)
    (pack_dir / "validation_examples" / "invalid").mkdir(parents=True)
    (pack_dir / "notes.md").write_text("Notes", encoding="utf-8")
    (pack_dir / "profile.yaml").write_text(REAL_PACK, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
