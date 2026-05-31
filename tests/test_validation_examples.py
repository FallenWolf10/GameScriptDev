from __future__ import annotations

import unittest
from pathlib import Path

from game_script_dev.profile_loader import load_profile
from game_script_dev.schema import ProfileValidationError, validate_profile


class ValidationExampleTests(unittest.TestCase):
    def test_valid_examples_pass_validation(self) -> None:
        for profile_path in Path("profiles/validation_examples/valid").glob("*.yaml"):
            with self.subTest(profile_path=profile_path):
                profile = load_profile(profile_path)
                validate_profile(profile, profile_path.parent)

    def test_invalid_examples_fail_with_expected_authoring_context(self) -> None:
        expected_fragments = {
            "bad_retry_count.yaml": "execution.max_retries must be at least 1",
            "bad_action_duration.yaml": "state 'home' actions[0].wait.seconds",
            "failure_transition_loop.yaml": "failure transition loop detected",
            "missing_region.yaml": "state 'home' actions[0].click_point.region",
            "profile_pack_missing_checklist_item.yaml": (
                "profile_pack.compatibility.successful_validation_or_dry_run "
                "is required"
            ),
            "unknown_action.yaml": "state 'home' actions[0].click_magic_button",
        }

        for filename, fragment in expected_fragments.items():
            profile_path = Path("profiles/validation_examples/invalid") / filename
            with self.subTest(profile_path=profile_path):
                profile = load_profile(profile_path)
                with self.assertRaises(ProfileValidationError) as captured:
                    validate_profile(profile, profile_path.parent)
                self.assertIn(fragment, str(captured.exception))


if __name__ == "__main__":
    unittest.main()
