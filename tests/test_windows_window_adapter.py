from __future__ import annotations

import logging
import unittest

from game_script_dev.adapters.base import TargetWindow
from game_script_dev.adapters.live import (
    LiveAdaptersUnavailable,
    TargetWindowNotReady,
    WindowCandidate,
    WindowsWindowAdapter,
    find_matching_window,
)
from game_script_dev.schema import Resolution


class WindowsWindowAdapterTests(unittest.TestCase):
    def test_matches_by_process_and_title(self) -> None:
        candidates = [
            WindowCandidate(
                handle=1,
                title="Launcher",
                process_id=10,
                process_name="launcher.exe",
                left=0,
                top=0,
                width=800,
                height=600,
            ),
            WindowCandidate(
                handle=2,
                title="Neverness to Everness",
                process_id=20,
                process_name="NTE.exe",
                left=100,
                top=200,
                width=1280,
                height=720,
            ),
        ]

        match = find_matching_window(
            candidates=candidates,
            process_name="nte.exe",
            window_title_contains="everness",
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.handle, 2)

    def test_returns_none_when_process_does_not_match(self) -> None:
        candidates = [
            WindowCandidate(
                handle=1,
                title="Neverness to Everness",
                process_id=20,
                process_name="launcher.exe",
                left=0,
                top=0,
                width=1280,
                height=720,
            )
        ]

        self.assertIsNone(
            find_matching_window(
                candidates=candidates,
                process_name="NTE.exe",
                window_title_contains="everness",
            )
        )

    def test_verify_only_accepts_matching_resolution(self) -> None:
        adapter = WindowsWindowAdapter(logging.getLogger("tests.window"))

        adapter.prepare_window(
            TargetWindow("test", "test.exe", 0, 0, 1280, 720, handle=1),
            Resolution(width=1280, height=720, policy="verify_only"),
        )

    def test_verify_only_rejects_mismatched_resolution(self) -> None:
        adapter = WindowsWindowAdapter(logging.getLogger("tests.window"))

        with self.assertRaises(TargetWindowNotReady):
            adapter.prepare_window(
                TargetWindow("test", "test.exe", 0, 0, 1024, 768, handle=1),
                Resolution(width=1280, height=720, policy="verify_only"),
            )

    def test_attempt_resize_is_explicitly_unavailable(self) -> None:
        adapter = WindowsWindowAdapter(logging.getLogger("tests.window"))

        with self.assertRaises(LiveAdaptersUnavailable):
            adapter.prepare_window(
                TargetWindow("test", "test.exe", 0, 0, 1024, 768, handle=1),
                Resolution(width=1280, height=720, policy="attempt_resize"),
            )


if __name__ == "__main__":
    unittest.main()
