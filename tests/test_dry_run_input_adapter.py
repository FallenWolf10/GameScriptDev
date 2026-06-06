from __future__ import annotations

import logging
import unittest

from game_script_dev.adapters.dry_run import DryRunInputAdapter


def quiet_logger(name: str) -> logging.Logger:
    test_logger = logging.getLogger(name)
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())
    test_logger.propagate = False
    return test_logger


class DryRunInputAdapterTests(unittest.TestCase):
    def test_reuses_continuous_input_name_after_wait_expires_stop_after(self) -> None:
        adapter = DryRunInputAdapter(quiet_logger("tests.dry_run.reuse_after_wait"))

        adapter.start_continuous_input(
            "press_esc",
            "press_key",
            {
                "key": "esc",
                "repeat_every_seconds": 0.2,
                "seconds": 0.1,
                "stop_after_seconds": 1.0,
            },
        )
        adapter.wait(1.5)
        adapter.start_continuous_input(
            "press_esc",
            "press_key",
            {
                "key": "esc",
                "repeat_every_seconds": 0.2,
                "seconds": 0.1,
                "stop_after_seconds": 1.0,
            },
        )

        self.assertEqual(set(adapter.active_continuous_inputs), {"press_esc"})

    def test_rejects_reusing_continuous_input_name_before_stop_after_expires(self) -> None:
        adapter = DryRunInputAdapter(quiet_logger("tests.dry_run.reject_overlap"))

        adapter.start_continuous_input(
            "press_esc",
            "press_key",
            {
                "key": "esc",
                "repeat_every_seconds": 0.2,
                "seconds": 0.1,
                "stop_after_seconds": 1.0,
            },
        )
        adapter.wait(0.5)

        with self.assertRaisesRegex(
            ValueError,
            "continuous input 'press_esc' is already active",
        ):
            adapter.start_continuous_input(
                "press_esc",
                "press_key",
                {
                    "key": "esc",
                    "repeat_every_seconds": 0.2,
                    "seconds": 0.1,
                    "stop_after_seconds": 1.0,
                },
            )

    def test_blocking_action_advance_time_allows_name_reuse_after_expiry(self) -> None:
        adapter = DryRunInputAdapter(
            quiet_logger("tests.dry_run.reuse_after_blocking_action")
        )

        adapter.start_continuous_input(
            "forward_motion",
            "hold_key",
            {
                "key": "w",
                "stop_after_seconds": 1.0,
            },
        )
        adapter.hold_key("shift", 1.2)
        adapter.start_continuous_input(
            "forward_motion",
            "hold_key",
            {
                "key": "w",
                "stop_after_seconds": 1.0,
            },
        )

        self.assertEqual(set(adapter.active_continuous_inputs), {"forward_motion"})


if __name__ == "__main__":
    unittest.main()
