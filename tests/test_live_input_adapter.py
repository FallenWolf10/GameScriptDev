from __future__ import annotations

import unittest
from math import inf
from unittest.mock import patch

from game_script_dev.adapters.live import (
    LiveAdaptersUnavailable,
    LiveInputAdapter,
    Win32KeyboardSender,
)
from game_script_dev.adapters.base import TargetWindow


TARGET_WINDOW = TargetWindow(
    title="test",
    process_name="test.exe",
    left=0,
    top=0,
    width=1280,
    height=720,
    handle=100,
)


class FakeKeyboardSender:
    def __init__(self) -> None:
        self.events: list[tuple[str, int]] = []

    def key_down(self, virtual_key: int) -> None:
        self.events.append(("down", virtual_key))

    def key_up(self, virtual_key: int) -> None:
        self.events.append(("up", virtual_key))


class FakeFocusVerifier:
    def __init__(self, is_foreground: bool = True) -> None:
        self.is_foreground_result = is_foreground
        self.checked_windows: list[TargetWindow] = []

    def is_foreground(self, window: TargetWindow) -> bool:
        self.checked_windows.append(window)
        return self.is_foreground_result


class FakeBackgroundKeyboardSender:
    def __init__(self) -> None:
        self.events: list[tuple[str, int, int]] = []

    def key_down(self, window: TargetWindow, virtual_key: int) -> None:
        assert window.handle is not None
        self.events.append(("down", window.handle, virtual_key))

    def key_up(self, window: TargetWindow, virtual_key: int) -> None:
        assert window.handle is not None
        self.events.append(("up", window.handle, virtual_key))


class FakeBackgroundMouseSender:
    def __init__(self) -> None:
        self.events: list[tuple[int, int, int]] = []

    def click(self, window: TargetWindow, x: int, y: int) -> None:
        assert window.handle is not None
        self.events.append((window.handle, x, y))


class FakeMouseSender:
    def __init__(self) -> None:
        self.events: list[tuple[int, int]] = []

    def click(self, x: int, y: int) -> None:
        self.events.append((x, y))


class FakeWindowAdapter:
    def __init__(self, can_focus: bool = True) -> None:
        self.can_focus = can_focus
        self.controllers_requested = 0
        self.confirm_calls: list[TargetWindow] = []

    def _controller(self) -> object:
        self.controllers_requested += 1
        return object()

    def _confirm_foreground(self, controller: object, window: TargetWindow) -> bool:
        self.confirm_calls.append(window)
        return self.can_focus


class LiveInputAdapterTests(unittest.TestCase):
    def test_press_key_sends_down_then_up_for_allowed_key(self) -> None:
        sender = FakeKeyboardSender()
        focus = FakeFocusVerifier()
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=focus,
        )

        adapter.press_key("enter")

        self.assertEqual(sender.events, [("down", 0x0D), ("up", 0x0D)])
        self.assertEqual(focus.checked_windows, [TARGET_WINDOW])

    def test_press_key_normalizes_single_letter_keys(self) -> None:
        sender = FakeKeyboardSender()
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
        )

        adapter.press_key(" w ")

        self.assertEqual(sender.events, [("down", ord("W")), ("up", ord("W"))])

    def test_press_key_rejects_unsupported_keys(self) -> None:
        sender = FakeKeyboardSender()
        adapter = LiveInputAdapter(sender=sender)

        with self.assertRaises(ValueError):
            adapter.press_key("volume_up")

        self.assertEqual(sender.events, [])

    def test_press_key_rejects_missing_target_context_before_sending(self) -> None:
        sender = FakeKeyboardSender()
        adapter = LiveInputAdapter(
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
        )

        with self.assertRaises(LiveAdaptersUnavailable):
            adapter.press_key("enter")

        self.assertEqual(sender.events, [])

    def test_press_key_rejects_non_foreground_target_before_sending(self) -> None:
        sender = FakeKeyboardSender()
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(is_foreground=False),
        )

        with self.assertRaises(LiveAdaptersUnavailable):
            adapter.press_key("enter")

        self.assertEqual(sender.events, [])

    def test_press_key_refocuses_target_window_before_sending(self) -> None:
        sender = FakeKeyboardSender()
        window_adapter = FakeWindowAdapter(can_focus=True)
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(is_foreground=False),
            window_adapter=window_adapter,  # type: ignore[arg-type]
        )

        adapter.press_key("enter")

        self.assertEqual(sender.events, [("down", 0x0D), ("up", 0x0D)])
        self.assertEqual(window_adapter.controllers_requested, 1)
        self.assertEqual(window_adapter.confirm_calls, [TARGET_WINDOW])

    def test_press_key_without_sender_fails_closed_when_win32_unavailable(self) -> None:
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            focus_verifier=FakeFocusVerifier(),
        )

        with patch.object(
            Win32KeyboardSender,
            "create",
            side_effect=LiveAdaptersUnavailable("unavailable"),
        ):
            with self.assertRaises(LiveAdaptersUnavailable):
                adapter.press_key("enter")

    def test_background_mode_sends_key_without_foreground_check(self) -> None:
        sender = FakeBackgroundKeyboardSender()
        focus = FakeFocusVerifier(is_foreground=False)
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            background_sender=sender,
            focus_verifier=focus,
            input_mode="background_window_messages",
        )

        adapter.press_key("enter")

        self.assertEqual(
            sender.events,
            [("down", 100, 0x0D), ("up", 100, 0x0D)],
        )
        self.assertEqual(focus.checked_windows, [])

    def test_hold_key_sends_up_after_sleep(self) -> None:
        sender = FakeKeyboardSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            sleeper=slept.append,
        )

        adapter.hold_key("space", 1.25)

        self.assertEqual(slept, [1.25])
        self.assertEqual(sender.events, [("down", 0x20), ("up", 0x20)])

    def test_hold_key_attempts_key_up_when_sleep_fails(self) -> None:
        sender = FakeKeyboardSender()

        def failing_sleep(seconds: float) -> None:
            raise RuntimeError(f"sleep failed at {seconds}")

        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            sleeper=failing_sleep,
        )

        with self.assertRaises(RuntimeError):
            adapter.hold_key("left", 0.5)

        self.assertEqual(sender.events, [("down", 0x25), ("up", 0x25)])

    def test_hold_key_rejects_unsafe_durations_before_sending_input(self) -> None:
        sender = FakeKeyboardSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            sleeper=slept.append,
            max_wait_seconds=2,
        )

        unsafe_durations = [-1, inf, 2.1]
        for seconds in unsafe_durations:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    adapter.hold_key("enter", seconds)

        self.assertEqual(slept, [])
        self.assertEqual(sender.events, [])

    def test_mouse_methods_remain_unavailable(self) -> None:
        adapter = LiveInputAdapter(sender=FakeKeyboardSender())

        with self.assertRaises(LiveAdaptersUnavailable):
            adapter.click_region("start")
        with self.assertRaises(LiveAdaptersUnavailable):
            adapter.click_template(
                "button.png",
                screenshot=object(),  # type: ignore[arg-type]
            )

    def test_background_mode_clicks_region_without_foreground_check(self) -> None:
        sender = FakeBackgroundMouseSender()
        focus = FakeFocusVerifier(is_foreground=False)
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            background_mouse_sender=sender,
            focus_verifier=focus,
            regions={"start": type("Region", (), {"x": 10, "y": 20, "width": 30, "height": 40})()},
            input_mode="background_window_messages",
        )

        adapter.click_region("start")

        self.assertEqual(sender.events, [(100, 25, 40)])
        self.assertEqual(focus.checked_windows, [])

    def test_click_region_refocuses_target_window_before_foreground_click(self) -> None:
        sender = FakeMouseSender()
        window_adapter = FakeWindowAdapter(can_focus=True)
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            mouse_sender=sender,
            focus_verifier=FakeFocusVerifier(is_foreground=False),
            window_adapter=window_adapter,  # type: ignore[arg-type]
            regions={"start": type("Region", (), {"x": 10, "y": 20, "width": 30, "height": 40})()},
        )

        adapter.click_region("start")

        self.assertEqual(sender.events, [(25, 40)])
        self.assertEqual(window_adapter.controllers_requested, 1)
        self.assertEqual(window_adapter.confirm_calls, [TARGET_WINDOW])

    def test_wait_sleeps_for_requested_duration(self) -> None:
        slept: list[float] = []
        adapter = LiveInputAdapter(sleeper=slept.append)

        adapter.wait(1.25)

        self.assertEqual(slept, [1.25])

    def test_wait_rejects_unsafe_durations(self) -> None:
        slept: list[float] = []
        adapter = LiveInputAdapter(sleeper=slept.append, max_wait_seconds=2)

        unsafe_durations = [-1, inf, 2.1]
        for seconds in unsafe_durations:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    adapter.wait(seconds)

        self.assertEqual(slept, [])


if __name__ == "__main__":
    unittest.main()
