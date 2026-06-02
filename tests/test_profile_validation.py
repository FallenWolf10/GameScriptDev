from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from game_script_dev.profile_loader import ProfileLoadError, load_profile
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

    def test_rejects_unknown_click_region(self) -> None:
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
      - type: click_point
        region: missing_region
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_negative_wait_duration(self) -> None:
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
      - type: wait
        seconds: -1
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_invalid_wait_for_state_duration(self) -> None:
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
      - type: wait_for_state
        state: done
        timeout_seconds: .inf
    on_success: done
  done:
    required_anchors:
      - name: done_title
        type: text
        text: Done
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_invalid_hold_key_duration(self) -> None:
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
      - type: hold_key
        key: enter
        seconds: nope
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_accepts_supported_function_key(self) -> None:
        profile_yaml = """
version: 1
name: Function Key Profile
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
      - type: hold_key
        key: f1
        seconds: 0.1
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_rejects_hold_click_without_duration(self) -> None:
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
regions:
  button:
    x: 10
    y: 20
    width: 30
    height: 40
states:
  home_screen:
    required_anchors:
      - name: home_title
        type: text
        text: Home
    actions:
      - type: hold_click
        region: button
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_hold_click_unknown_region(self) -> None:
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
      - type: hold_click
        region: missing_region
        seconds: 1
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_unsupported_keyboard_key(self) -> None:
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
      - type: press_key
        key: volume_up
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_invalid_press_key_duration(self) -> None:
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
      - type: press_key
        key: enter
        seconds: nope
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_invalid_default_timeout(self) -> None:
        profile_yaml = """
version: 1
name: Broken Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  default_timeout_seconds: -1
initial_state: home_screen
states:
  home_screen:
    required_anchors:
      - name: home_title
        type: text
        text: Home
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_unknown_target_input_mode(self) -> None:
        profile_yaml = """
version: 1
name: Broken Profile
target:
  process_name: demo.exe
  input_mode: teleport
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
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError) as captured:
                validate_profile(profile, profile_path.parent)

            self.assertIn("unknown target input_mode", str(captured.exception))

    def test_rejects_unknown_target_foreground_key_method(self) -> None:
        profile_yaml = """
version: 1
name: Broken Profile
target:
  process_name: demo.exe
  input_mode: foreground
  foreground_key_method: telepathy
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
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError) as captured:
                validate_profile(profile, profile_path.parent)

            self.assertIn(
                "unknown target foreground_key_method",
                str(captured.exception),
            )

    def test_rejects_non_boolean_qwerty_physical_key_flag(self) -> None:
        profile_yaml = """
version: 1
name: Broken Profile
target:
  process_name: demo.exe
  use_qwerty_physical_keys: "yes"
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
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            with self.assertRaises(ProfileLoadError) as captured:
                load_profile(profile_path)

            self.assertIn("use_qwerty_physical_keys must be a boolean", str(captured.exception))

    def test_defaults_target_input_mode_to_background_messages(self) -> None:
        profile_yaml = """
version: 1
name: Default Background Profile
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
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)
            self.assertEqual(profile.target.input_mode, "background_window_messages")

    def test_rejects_unreachable_state(self) -> None:
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
    terminal: true
    result: success
  unused:
    required_anchors:
      - name: unused_title
        type: text
        text: Unused
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError) as captured:
                validate_profile(profile, profile_path.parent)

            self.assertIn("unreachable", str(captured.exception))

    def test_rejects_graph_without_reachable_terminal_state(self) -> None:
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
    on_success: home_screen
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError) as captured:
                validate_profile(profile, profile_path.parent)

            self.assertIn("reachable terminal state", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
