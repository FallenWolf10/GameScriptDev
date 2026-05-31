from __future__ import annotations

import unittest
from pathlib import Path

from game_script_dev.adapters.pillow_vision import find_template_center
from game_script_dev.fixtures import load_fixture_manifest, validate_fixture_pack


class RegressionFixtureTests(unittest.TestCase):
    def test_local_demo_fixture_manifest_is_safe_and_valid(self) -> None:
        fixture_dir = Path("fixtures/local_demo")

        manifest = load_fixture_manifest(fixture_dir / "manifest.json")

        self.assertTrue(manifest.safe_to_commit)
        self.assertFalse(manifest.contains_third_party_content)
        self.assertIn("home_screen", manifest.states)
        self.assertIn("home_title", manifest.expected_anchors)
        self.assertEqual(validate_fixture_pack(fixture_dir), [])

    def test_local_demo_fixture_supports_template_matching(self) -> None:
        fixture_dir = Path("fixtures/local_demo")

        center = find_template_center(
            fixture_dir / "screens" / "home_screen.png",
            fixture_dir / "anchors" / "home_marker.png",
        )

        self.assertEqual(center, (160, 82))


if __name__ == "__main__":
    unittest.main()
