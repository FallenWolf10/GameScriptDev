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

    def test_rejects_blank_common_action_text_fields(self) -> None:
        actions = (
            ("log", "message"),
            ("stop", "result"),
        )
        for action_type, field_name in actions:
            with self.subTest(action_type=action_type):
                profile_yaml = f"""
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
    actions:
      - type: {action_type}
        {field_name}: ""
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
      - type: press_key
        key: f4
        seconds: 0.1
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_manual_stop_is_dry_run_success_execution_flag(self) -> None:
        profile_yaml = """
version: 1
name: Manual Stop Dry Run Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
  manual_stop_is_dry_run_success: true
initial_state: home_screen
states:
  home_screen:
    actions:
      - type: start_continuous_input
        name: repeat_f_key
        action: press_key
        key: f
        repeat_every_seconds: 0.2
        seconds: 0.1
    on_success: keep_alive
    on_failure: failed
  keep_alive:
    actions:
      - type: wait
        seconds: 1
    on_success: keep_alive
    on_failure: failed
  failed:
    terminal: true
    result: failed_manual_stop
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_allow_infinite_run_execution_flag_without_terminal_state(self) -> None:
        profile_yaml = """
version: 1
name: Infinite Keep Alive Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
  allow_infinite_run: true
initial_state: keep_alive
states:
  keep_alive:
    actions:
      - type: wait
        seconds: 1
    on_success: keep_alive
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

    def test_accepts_hold_keys_combo(self) -> None:
        profile_yaml = """
version: 1
name: Combo Profile
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
      - type: hold_keys
        keys: [shift, w]
        seconds: 0.5
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_explicit_left_shift_key(self) -> None:
        profile_yaml = """
version: 1
name: Left Shift Profile
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
      - type: hold_keys
        keys: [left_shift, w]
        seconds: 0.5
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_repeat_key(self) -> None:
        profile_yaml = """
version: 1
name: Repeat Key Profile
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
      - type: repeat_key
        key: space
        repeat_for_seconds: 2
        repeat_every_seconds: 0.5
        tap_duration_seconds: 0.1
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_rejects_repeat_key_without_positive_interval(self) -> None:
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
      - type: repeat_key
        key: space
        repeat_for_seconds: 2
        repeat_every_seconds: 0
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_hold_keys_without_keys(self) -> None:
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
      - type: hold_keys
        seconds: 0.5
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_press_keys_with_unsupported_key(self) -> None:
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
      - type: press_keys
        keys: [ctrl, volume_up]
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_accepts_hold_key_while_repeating_key(self) -> None:
        profile_yaml = """
version: 1
name: Repeat Profile
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
      - type: hold_key_while_repeating_key
        hold_key: w
        hold_seconds: 5
        tap_key: space
        tap_every_seconds: 1
        tap_duration_seconds: 0.1
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_start_continuous_input(self) -> None:
        profile_yaml = """
version: 1
name: Continuous Input Profile
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
      - type: start_continuous_input
        name: forward_motion
        action: hold_key
        key: w
      - type: press_key
        key: e
      - type: stop_continuous_input
        name: forward_motion
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_rejects_duplicate_continuous_input_start_across_states(self) -> None:
        profile_yaml = """
version: 1
name: Duplicate Continuous Input Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: first
states:
  first:
    actions:
      - type: start_continuous_input
        name: hold_s
        action: hold_key
        key: s
    on_success: second
  second:
    actions:
      - type: start_continuous_input
        name: hold_s
        action: hold_key
        key: s
    on_success: done
  done:
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaisesRegex(
                ProfileValidationError,
                "continuous input 'hold_s' is already active before "
                "state 'second' actions\\[0\\]",
            ):
                validate_profile(profile, profile_path.parent)

    def test_accepts_continuous_input_restart_after_stop(self) -> None:
        profile_yaml = """
version: 1
name: Restart Continuous Input Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: first
states:
  first:
    actions:
      - type: start_continuous_input
        name: hold_s
        action: hold_key
        key: s
      - type: stop_continuous_input
        name: hold_s
    on_success: second
  second:
    actions:
      - type: start_continuous_input
        name: hold_s
        action: hold_key
        key: s
    on_success: done
  done:
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_rejects_stop_for_inactive_continuous_input(self) -> None:
        profile_yaml = """
version: 1
name: Inactive Continuous Input Stop Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: home
states:
  home:
    actions:
      - type: stop_continuous_input
        name: hold_s
    on_success: done
  done:
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaisesRegex(
                ProfileValidationError,
                "continuous input 'hold_s' is not active before "
                "state 'home' actions\\[0\\]",
            ):
                validate_profile(profile, profile_path.parent)

    def test_rejects_continuous_press_key_without_repeat_interval(self) -> None:
        profile_yaml = """
version: 1
name: Broken Continuous Profile
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
      - type: start_continuous_input
        name: scanner
        action: press_key
        key: tab
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_accepts_continuous_click_point(self) -> None:
        profile_yaml = """
version: 1
name: Continuous Click Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: home_screen
regions:
  start_button:
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
      - type: start_continuous_input
        name: keep_clicking
        action: click_point
        region: start_button
        repeat_every_seconds: 0.5
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_continuous_scroll_mouse(self) -> None:
        profile_yaml = """
version: 1
name: Continuous Scroll Profile
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
      - type: start_continuous_input
        name: keep_scrolling
        action: scroll_mouse
        direction: down
        steps: 2
        repeat_every_seconds: 0.5
        input_mode: foreground
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_continuous_sequence(self) -> None:
        profile_yaml = """
version: 1
name: Continuous Sequence Profile
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
      - type: start_continuous_input
        name: combat_cycle
        action: sequence
        sequence:
          - action: press_key
            key: "1"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
          - action: press_key
            key: "2"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
      - type: stop_continuous_input
        name: combat_cycle
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_rejects_continuous_sequence_without_step_duration(self) -> None:
        profile_yaml = """
version: 1
name: Broken Continuous Sequence Profile
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
      - type: start_continuous_input
        name: combat_cycle
        action: sequence
        sequence:
          - action: press_key
            key: "1"
            repeat_every_seconds: 0.1
            seconds: 0.1
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_continuous_click_point_without_repeat_interval(self) -> None:
        profile_yaml = """
version: 1
name: Broken Continuous Click Profile
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: home_screen
regions:
  start_button:
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
      - type: start_continuous_input
        name: keep_clicking
        action: click_point
        region: start_button
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_continuous_scroll_mouse_without_repeat_interval(self) -> None:
        profile_yaml = """
version: 1
name: Broken Continuous Scroll Profile
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
      - type: start_continuous_input
        name: keep_scrolling
        action: scroll_mouse
        direction: down
        input_mode: foreground
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError):
                validate_profile(profile, profile_path.parent)

    def test_rejects_hold_key_while_repeating_key_without_positive_interval(self) -> None:
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
      - type: hold_key_while_repeating_key
        hold_key: w
        hold_seconds: 5
        tap_key: space
        tap_every_seconds: 0
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

    def test_accepts_click_action_input_mode_override(self) -> None:
        profile_yaml = """
version: 1
name: Click Override Profile
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
      - type: click_point
        region: button
        input_mode: foreground
      - type: hold_click
        region: button
        seconds: 0.5
        input_mode: background_window_messages
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_foreground_mouse_look_actions(self) -> None:
        profile_yaml = """
version: 1
name: Mouse Look Profile
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
      - type: move_mouse
        dx: 120
        dy: -30
        seconds: 0.2
        input_mode: foreground
      - type: hold_mouse_button_and_move
        button: right
        dx: 50
        dy: 10
        seconds: 0.15
        input_mode: foreground
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_rejects_background_mouse_look_action_override(self) -> None:
        profile_yaml = """
version: 1
name: Broken Mouse Look Profile
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
      - type: move_mouse
        dx: 120
        dy: -30
        input_mode: background_window_messages
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
                "input_mode must be foreground for mouse-look actions",
                str(captured.exception),
            )

    def test_rejects_unknown_mouse_button(self) -> None:
        profile_yaml = """
version: 1
name: Broken Mouse Button Profile
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
      - type: hold_mouse_button_and_move
        button: middle
        dx: 20
        dy: 5
        input_mode: foreground
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            with self.assertRaises(ProfileValidationError) as captured:
                validate_profile(profile, profile_path.parent)

            self.assertIn("unsupported mouse button", str(captured.exception))

    def test_accepts_scroll_mouse_action(self) -> None:
        profile_yaml = """
version: 1
name: Scroll Mouse Profile
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
      - type: scroll_mouse
        direction: down
        steps: 2
        input_mode: foreground
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_accepts_scroll_mouse_background_override(self) -> None:
        profile_yaml = """
version: 1
name: Background Scroll Mouse Profile
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
      - type: scroll_mouse
        direction: down
        input_mode: background_window_messages
    terminal: true
    result: success
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(profile_yaml, encoding="utf-8")

            profile = load_profile(profile_path)

            validate_profile(profile, profile_path.parent)

    def test_rejects_unknown_click_action_input_mode_override(self) -> None:
        profile_yaml = """
version: 1
name: Broken Click Override Profile
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
      - type: click_point
        region: button
        input_mode: teleport
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
                "state 'home_screen' actions[0].click_point.input_mode uses unknown input mode",
                str(captured.exception),
            )

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
