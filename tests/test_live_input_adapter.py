from __future__ import annotations

import unittest
from math import inf
from unittest.mock import patch

from game_script_dev.adapters.live import (
    LiveAdaptersUnavailable,
    LiveInputAdapter,
    Win32KeyboardSender,
)


class FakeKeyboardSender:
    def __init__(self) -> None:
        self.events: list[tuple[str, int]] = []

    def key_down(self, virtual_key: int) -> None:
        self.events.append(("down", virtual_key))

    def key_up(self, virtual_key: int) -> None:
        self.events.append(("up", virtual_key))


class LiveInputAdapterTests(unittest.TestCase):
    def test_press_key_sends_down_then_up_for_allowed_key(self) -> None:
        sender = FakeKeyboardSender()
        adapter = LiveInputAdapter(sender=sender)

        adapter.press_key("enter")

        self.assertEqual(sender.events, [("down", 0x0D), ("up", 0x0D)])

    def test_press_key_normalizes_single_letter_keys(self) -> None:
        sender = FakeKeyboardSender()
        adapter = LiveInputAdapter(sender=sender)

        adapter.press_key(" w ")

        self.assertEqual(sender.events, [("down", ord("W")), ("up", ord("W"))])

    def test_press_key_rejects_unsupported_keys(self) -> None:
        sender = FakeKeyboardSender()
        adapter = LiveInputAdapter(sender=sender)

        with self.assertRaises(ValueError):
            adapter.press_key("volume_up")

        self.assertEqual(sender.events, [])

    def test_press_key_without_sender_fails_closed_when_win32_unavailable(self) -> None:
        adapter = LiveInputAdapter()

        with patch.object(
            Win32KeyboardSender,
            "create",
            side_effect=LiveAdaptersUnavailable("unavailable"),
        ):
            with self.assertRaises(LiveAdaptersUnavailable):
                adapter.press_key("enter")

    def test_hold_key_sends_up_after_sleep(self) -> None:
        sender = FakeKeyboardSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(sender=sender, sleeper=slept.append)

        adapter.hold_key("space", 1.25)

        self.assertEqual(slept, [1.25])
        self.assertEqual(sender.events, [("down", 0x20), ("up", 0x20)])

    def test_hold_key_attempts_key_up_when_sleep_fails(self) -> None:
        sender = FakeKeyboardSender()

        def failing_sleep(seconds: float) -> None:
            raise RuntimeError(f"sleep failed at {seconds}")

        adapter = LiveInputAdapter(sender=sender, sleeper=failing_sleep)

        with self.assertRaises(RuntimeError):
            adapter.hold_key("left", 0.5)

        self.assertEqual(sender.events, [("down", 0x25), ("up", 0x25)])

    def test_hold_key_rejects_unsafe_durations_before_sending_input(self) -> None:
        sender = FakeKeyboardSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            sender=sender,
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
