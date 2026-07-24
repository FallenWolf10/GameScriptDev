from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from game_script_dev.dashboard.structured_actions import (
    StructuredActionMutationError,
    mutate_action_source,
)
from game_script_dev.schema import (
    ProfileValidationError,
    profile_from_mapping,
    validate_profile,
)


SOURCE = """\
version: 1
name: Structured Actions
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: home
states:
  home:
    # State context must survive.
    actions:
      - type: log
        message: Before
      # This comment belongs with the wait.
      - type: wait
        seconds: 1 # keep inline context
      - type: log
        message: After
    on_success: done
  done:
    terminal: true
    result: success
"""


class StructuredActionMutationTests(unittest.TestCase):
    def test_insert_update_move_duplicate_disable_and_delete(self) -> None:
        inserted = mutate_action_source(
            SOURCE,
            {
                "operation": "insert",
                "state": "home",
                "index": 1,
                "action_type": "wait",
                "fields": {"seconds": 0.5},
            },
        )
        document = yaml.safe_load(inserted)
        self.assertEqual(document["states"]["home"]["actions"][1]["seconds"], 0.5)
        self.assertIn("# State context must survive.", inserted)

        updated = mutate_action_source(
            inserted,
            {
                "operation": "update",
                "state": "home",
                "index": 1,
                "fields": {"seconds": 2.25},
            },
        )
        self.assertIn("seconds: 2.25", updated)

        moved = mutate_action_source(
            updated,
            {
                "operation": "move",
                "state": "home",
                "index": 1,
                "target_index": 0,
            },
        )
        self.assertEqual(
            yaml.safe_load(moved)["states"]["home"]["actions"][0]["seconds"],
            2.25,
        )

        duplicated = mutate_action_source(
            moved,
            {
                "operation": "duplicate",
                "state": "home",
                "index": 0,
            },
        )
        self.assertEqual(
            len(yaml.safe_load(duplicated)["states"]["home"]["actions"]),
            5,
        )

        disabled = mutate_action_source(
            duplicated,
            {
                "operation": "disable",
                "state": "home",
                "index": 0,
            },
        )
        self.assertTrue(
            yaml.safe_load(disabled)["states"]["home"]["actions"][0]["disabled"]
        )

        deleted = mutate_action_source(
            disabled,
            {
                "operation": "delete",
                "state": "home",
                "index": 0,
            },
        )
        self.assertEqual(
            len(yaml.safe_load(deleted)["states"]["home"]["actions"]),
            4,
        )
        self.assertIn("# This comment belongs with the wait.", deleted)

    def test_update_preserves_inline_comment_and_unrelated_formatting(self) -> None:
        updated = mutate_action_source(
            SOURCE,
            {
                "operation": "update",
                "state": "home",
                "index": 1,
                "fields": {"seconds": 3},
            },
        )

        self.assertIn("seconds: 3 # keep inline context", updated)
        self.assertEqual(
            SOURCE.replace("seconds: 1", "seconds: 3"),
            updated,
        )

    def test_insert_supports_missing_and_empty_action_lists(self) -> None:
        missing = SOURCE.replace(
            "    actions:\n"
            "      - type: log\n"
            "        message: Before\n"
            "      # This comment belongs with the wait.\n"
            "      - type: wait\n"
            "        seconds: 1 # keep inline context\n"
            "      - type: log\n"
            "        message: After\n",
            "",
        )
        inserted_missing = mutate_action_source(
            missing,
            {
                "operation": "insert",
                "state": "home",
                "action_type": "wait",
                "fields": {"seconds": 1},
            },
        )
        self.assertEqual(
            yaml.safe_load(inserted_missing)["states"]["home"]["actions"],
            [{"type": "wait", "seconds": 1}],
        )

        empty = SOURCE.replace(
            "    actions:\n"
            "      - type: log\n"
            "        message: Before\n"
            "      # This comment belongs with the wait.\n"
            "      - type: wait\n"
            "        seconds: 1 # keep inline context\n"
            "      - type: log\n"
            "        message: After\n",
            "    actions: []\n",
        )
        inserted_empty = mutate_action_source(
            empty,
            {
                "operation": "insert",
                "state": "home",
                "action_type": "wait",
                "fields": {"seconds": 1},
            },
        )
        self.assertEqual(
            yaml.safe_load(inserted_empty)["states"]["home"]["actions"],
            [{"type": "wait", "seconds": 1}],
        )

    def test_rejects_unknown_states_indexes_and_fields(self) -> None:
        invalid_mutations = [
            {"operation": "delete", "state": "missing", "index": 0},
            {"operation": "delete", "state": "home", "index": 99},
            {
                "operation": "insert",
                "state": "home",
                "action_type": "wait",
                "fields": {"mystery": 1},
            },
        ]
        for mutation in invalid_mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(StructuredActionMutationError):
                    mutate_action_source(SOURCE, mutation)

    def test_delete_only_action_leaves_an_empty_list(self) -> None:
        single = SOURCE.replace(
            "      - type: log\n"
            "        message: Before\n"
            "      # This comment belongs with the wait.\n",
            "",
        ).replace(
            "      - type: log\n"
            "        message: After\n",
            "",
        )

        deleted = mutate_action_source(
            single,
            {"operation": "delete", "state": "home", "index": 0},
        )

        self.assertEqual(
            yaml.safe_load(deleted)["states"]["home"]["actions"],
            [],
        )

    def test_disabled_action_is_excluded_from_authoritative_validation(self) -> None:
        document = yaml.safe_load(SOURCE)
        document["states"]["home"]["actions"][1]["seconds"] = -1
        document["states"]["home"]["actions"][1]["disabled"] = True
        profile = profile_from_mapping(document)

        with TemporaryDirectory() as temp_dir:
            validate_profile(profile, Path(temp_dir))

        self.assertTrue(profile.states["home"].actions[1].disabled)

    def test_disabled_unknown_action_is_still_rejected(self) -> None:
        document = yaml.safe_load(SOURCE)
        document["states"]["home"]["actions"][1] = {
            "type": "unknown_action",
            "disabled": True,
        }
        profile = profile_from_mapping(document)

        with TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ProfileValidationError,
                "uses unknown action type",
            ):
                validate_profile(profile, Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
