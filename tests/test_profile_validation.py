from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from game_script_dev.profile_loader import load_profile
from game_script_dev.schema import ProfileValidationError, validate_profile


class ProfileValidationTests(unittest.TestCase):
    def test_demo_profile_is_valid(self) -> None:
        profile_path = Path("profiles/demo/profile.yaml")

        profile = load_profile(profile_path)

        validate_profile(profile, profile_path.parent)

    def test_rejects_unknown_transition(self) -> None:
        profile_yaml = """
version: 1
name: Broken Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: home_screen
states:
  home_screen:
    required_anchors:
      - name: home_title
        type: text
        text: Home
    actions: []
    on_success: missing_state
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_unknown_action_type(self) -> None:
        profile_yaml = """
version: 1
name: Broken Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: home_screen
states:
  home_screen:
    required_anchors:
      - name: home_title
        type: text
        text: Home
    actions:
      - type: click_magic_button
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)


if __name__ == "__main__":
    unittest.main()
