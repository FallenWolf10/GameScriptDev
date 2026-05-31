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
        controller = FakeWindowController()
        adapter = WindowsWindowAdapter(
            logging.getLogger("tests.window"),
            candidates_provider=lambda: [candidate(width=1280, height=720)],
            window_controller=controller,
        )

        adapter.prepare_window(
            TargetWindow("test", "test.exe", 0, 0, 1280, 720, handle=1),
            Resolution(width=1280, height=720, policy="verify_only"),
        )

        self.assertEqual(controller.focused_handles, [1])

    def test_verify_only_rejects_mismatched_resolution(self) -> None:
        adapter = WindowsWindowAdapter(
            logging.getLogger("tests.window"),
            candidates_provider=lambda: [candidate(width=1024, height=768)],
            window_controller=FakeWindowController(),
        )

        with self.assertRaises(TargetWindowNotReady):
            adapter.prepare_window(
                TargetWindow("test", "test.exe", 0, 0, 1024, 768, handle=1),
                Resolution(width=1280, height=720, policy="verify_only"),
            )

    def test_attempt_resize_is_explicitly_unavailable(self) -> None:
        adapter = WindowsWindowAdapter(
            logging.getLogger("tests.window"),
            candidates_provider=lambda: [candidate(width=1024, height=768)],
            window_controller=FakeWindowController(),
        )

        with self.assertRaises(LiveAdaptersUnavailable):
            adapter.prepare_window(
                TargetWindow("test", "test.exe", 0, 0, 1024, 768, handle=1),
                Resolution(width=1280, height=720, policy="attempt_resize"),
            )

    def test_focus_must_be_confirmed_after_prepare(self) -> None:
        adapter = WindowsWindowAdapter(
            logging.getLogger("tests.window"),
            candidates_provider=lambda: [candidate(width=1280, height=720)],
            window_controller=FakeWindowController(foreground_after_focus=False),
        )

        with self.assertRaises(TargetWindowNotReady):
            adapter.prepare_window(
                TargetWindow("test", "test.exe", 0, 0, 1280, 720, handle=1),
                Resolution(width=1280, height=720, policy="verify_only"),
            )

    def test_verify_window_rejects_identity_change(self) -> None:
        adapter = WindowsWindowAdapter(
            logging.getLogger("tests.window"),
            candidates_provider=lambda: [
                candidate(process_name="other.exe", width=1280, height=720)
            ],
            window_controller=FakeWindowController(),
        )

        with self.assertRaises(TargetWindowNotReady):
            adapter.verify_window(
                TargetWindow("test", "test.exe", 0, 0, 1280, 720, handle=1),
                profile=type(
                    "ProfileStub",
                    (),
                    {
                        "target": type(
                            "TargetStub",
                            (),
                            {
                                "process_name": "test.exe",
                                "window_title_contains": "test",
                            },
                        )()
                    },
                )(),
            )


class FakeWindowController:
    def __init__(self, foreground_after_focus: bool = True) -> None:
        self.foreground_after_focus = foreground_after_focus
        self.focused_handles: list[int] = []

    def focus(self, window: TargetWindow) -> None:
        assert window.handle is not None
        self.focused_handles.append(window.handle)

    def is_foreground(self, window: TargetWindow) -> bool:
        return bool(self.focused_handles) and self.foreground_after_focus


def candidate(
    process_name: str = "test.exe",
    width: int = 1280,
    height: int = 720,
) -> WindowCandidate:
    return WindowCandidate(
        handle=1,
        title="test",
        process_id=10,
        process_name=process_name,
        left=0,
        top=0,
        width=width,
        height=height,
    )


if __name__ == "__main__":
    unittest.main()
