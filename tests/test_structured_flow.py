from __future__ import annotations

import unittest

import yaml

from game_script_dev.dashboard.structured_flow import (
    StructuredFlowMutationError,
    deterministic_flow_layout,
    mutate_flow_source,
)


SOURCE = """\
version: 1
name: Structured Flow
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
initial_state: home # keep root context
states:
  home:
    # Keep State context.
    actions: []
    on_success: done # keep transition context
    on_failure: graceful_termination
  done:
    terminal: true
    result: success
"""


class StructuredFlowMutationTests(unittest.TestCase):
    def test_updates_initial_state_and_transitions_without_reformatting(self) -> None:
        updated = mutate_flow_source(
            SOURCE,
            {
                "operation": "update_state",
                "state": "done",
                "make_initial": True,
                "terminal": False,
                "on_success": "home",
                "on_failure": "graceful_termination",
            },
        )

        document = yaml.safe_load(updated)
        self.assertEqual(document["initial_state"], "done")
        self.assertFalse(document["states"]["done"].get("terminal", False))
        self.assertNotIn("result", document["states"]["done"])
        self.assertEqual(document["states"]["done"]["on_success"], "home")
        self.assertIn("initial_state: done # keep root context", updated)
        self.assertIn("# Keep State context.", updated)

    def test_makes_terminal_and_removes_transitions(self) -> None:
        updated = mutate_flow_source(
            SOURCE,
            {
                "operation": "update_state",
                "state": "home",
                "terminal": True,
                "result": "completed",
            },
        )

        state = yaml.safe_load(updated)["states"]["home"]
        self.assertTrue(state["terminal"])
        self.assertEqual(state["result"], "completed")
        self.assertNotIn("on_success", state)
        self.assertNotIn("on_failure", state)
        self.assertIn("# Keep State context.", updated)

    def test_rejects_unknown_states_and_targets(self) -> None:
        for mutation in (
            {
                "operation": "update_state",
                "state": "missing",
                "terminal": True,
            },
            {
                "operation": "update_state",
                "state": "home",
                "terminal": False,
                "on_success": "missing",
            },
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(StructuredFlowMutationError):
                    mutate_flow_source(SOURCE, mutation)

    def test_deterministic_layout_uses_transition_levels(self) -> None:
        document = yaml.safe_load(SOURCE)
        first = deterministic_flow_layout(document)
        second = deterministic_flow_layout(document)

        self.assertEqual(first, second)
        self.assertLess(first["home"]["x"], first["done"]["x"])
        self.assertEqual(first["home"]["y"], 48)


if __name__ == "__main__":
    unittest.main()
