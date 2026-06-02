from __future__ import annotations

import unittest
from math import inf
from unittest.mock import patch

from game_script_dev.adapters import live as live_module
from game_script_dev.adapters.live import (
    LiveAdaptersUnavailable,
    LiveInputAdapter,
    Win32BackgroundKeyboardSender,
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
        self.events: list[tuple[str, int, int, int]] = []

    def click(self, window: TargetWindow, x: int, y: int) -> None:
        assert window.handle is not None
        self.events.append(("click", window.handle, x, y))

    def button_down(self, window: TargetWindow, x: int, y: int) -> None:
        assert window.handle is not None
        self.events.append(("down", window.handle, x, y))

    def button_up(self, window: TargetWindow, x: int, y: int) -> None:
        assert window.handle is not None
        self.events.append(("up", window.handle, x, y))


class FakeMouseSender:
    def __init__(self) -> None:
        self.events: list[tuple[str, int, int]] = []

    def click(self, x: int, y: int) -> None:
        self.events.append(("click", x, y))

    def button_down(self, x: int, y: int) -> None:
        self.events.append(("down", x, y))

    def button_up(self, x: int, y: int) -> None:
        self.events.append(("up", x, y))


class FakePhysicalKeyMapper:
    def __init__(self, mapped: str | None) -> None:
        self.mapped = mapped
        self.keys: list[str] = []

    def map_key_name(self, key: str) -> str | None:
        self.keys.append(key)
        return self.mapped


class FakeUser32:
    def __init__(self) -> None:
        self.post_calls: list[tuple[int, int, int, int]] = []
        self.send_calls: list[tuple[int, int, int, int, int, int]] = []
        self.map_calls: list[tuple[int, int]] = []
        self.sendinput_events: list[tuple[int, int, int, int]] = []
        self.keybd_events: list[tuple[int, int, int, int]] = []

    def PostMessageW(self, handle: int, message: int, w_param: int, l_param: int) -> int:
        self.post_calls.append((handle, message, w_param, l_param))
        return 1

    def SendMessageTimeoutW(
        self,
        handle: int,
        message: int,
        w_param: int,
        l_param: int,
        flags: int,
        timeout_ms: int,
        result_ptr: object,
    ) -> int:
        self.send_calls.append((handle, message, w_param, l_param, flags, timeout_ms))
        return 1

    def MapVirtualKeyW(self, virtual_key: int, map_type: int) -> int:
        self.map_calls.append((virtual_key, map_type))
        return virtual_key + 10

    def SendInput(self, count: int, event_ptr: object, size: int) -> int:
        event = event_ptr._obj
        keyboard = event.union.ki
        self.sendinput_events.append(
            (
                int(keyboard.wVk),
                int(keyboard.wScan),
                int(keyboard.dwFlags),
                int(keyboard.time),
            )
        )
        return 1

    def keybd_event(
        self,
        virtual_key: int,
        scan_code: int,
        flags: int,
        extra_info: int,
    ) -> None:
        self.keybd_events.append((virtual_key, scan_code, flags, extra_info))


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
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=focus,
            sleeper=slept.append,
        )

        adapter.press_key("enter")

        self.assertEqual(sender.events, [("down", 0x0D), ("up", 0x0D)])
        self.assertEqual(slept, [0.1])
        self.assertEqual(focus.checked_windows, [TARGET_WINDOW])

    def test_press_key_normalizes_single_letter_keys(self) -> None:
        sender = FakeKeyboardSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            sleeper=slept.append,
        )

        adapter.press_key(" w ")

        self.assertEqual(sender.events, [("down", ord("W")), ("up", ord("W"))])
        self.assertEqual(slept, [0.1])

    def test_press_key_supports_function_keys(self) -> None:
        sender = FakeKeyboardSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            sleeper=slept.append,
        )

        adapter.press_key("f1")

        self.assertEqual(sender.events, [("down", 0x70), ("up", 0x70)])
        self.assertEqual(slept, [0.1])

    def test_press_key_can_map_qwerty_physical_key_before_normalization(self) -> None:
        sender = FakeKeyboardSender()
        mapper = FakePhysicalKeyMapper("m")
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            use_qwerty_physical_keys=True,
            sleeper=slept.append,
        )
        adapter.key_mapper = mapper  # type: ignore[assignment]

        adapter.press_key("l")

        self.assertEqual(mapper.keys, ["l"])
        self.assertEqual(sender.events, [("down", ord("M")), ("up", ord("M"))])
        self.assertEqual(slept, [0.1])

    def test_press_key_keeps_original_key_when_mapping_returns_none(self) -> None:
        sender = FakeKeyboardSender()
        mapper = FakePhysicalKeyMapper(None)
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            use_qwerty_physical_keys=True,
            sleeper=slept.append,
        )
        adapter.key_mapper = mapper  # type: ignore[assignment]

        adapter.press_key("l")

        self.assertEqual(sender.events, [("down", ord("L")), ("up", ord("L"))])
        self.assertEqual(slept, [0.1])

    def test_press_key_allows_custom_tap_duration(self) -> None:
        sender = FakeKeyboardSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            sender=sender,
            focus_verifier=FakeFocusVerifier(),
            sleeper=slept.append,
        )

        adapter.press_key("l", 0.25)

        self.assertEqual(sender.events, [("down", ord("L")), ("up", ord("L"))])
        self.assertEqual(slept, [0.25])

    def test_press_key_attempts_release_when_sleep_fails(self) -> None:
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
            adapter.press_key("l")

        self.assertEqual(sender.events, [("down", ord("L")), ("up", ord("L"))])

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
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            background_sender=sender,
            focus_verifier=focus,
            input_mode="background_window_messages",
            sleeper=slept.append,
        )

        adapter.press_key("enter")

        self.assertEqual(
            sender.events,
            [("down", 100, 0x0D), ("up", 100, 0x0D)],
        )
        self.assertEqual(slept, [0.1])
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

        self.assertEqual(sender.events, [("click", 100, 25, 40)])
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

        self.assertEqual(sender.events, [("click", 25, 40)])
        self.assertEqual(window_adapter.controllers_requested, 1)
        self.assertEqual(window_adapter.confirm_calls, [TARGET_WINDOW])

    def test_hold_click_background_mode_holds_then_releases(self) -> None:
        sender = FakeBackgroundMouseSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            background_mouse_sender=sender,
            focus_verifier=FakeFocusVerifier(is_foreground=False),
            regions={"start": type("Region", (), {"x": 10, "y": 20, "width": 30, "height": 40})()},
            input_mode="background_window_messages",
            sleeper=slept.append,
        )

        adapter.hold_click("start", 1.5)

        self.assertEqual(
            sender.events,
            [("down", 100, 25, 40), ("up", 100, 25, 40)],
        )
        self.assertEqual(slept, [1.5])

    def test_hold_click_foreground_mode_holds_then_releases(self) -> None:
        sender = FakeMouseSender()
        slept: list[float] = []
        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            mouse_sender=sender,
            focus_verifier=FakeFocusVerifier(),
            regions={"start": type("Region", (), {"x": 10, "y": 20, "width": 30, "height": 40})()},
            sleeper=slept.append,
        )

        adapter.hold_click("start", 0.75)

        self.assertEqual(sender.events, [("down", 25, 40), ("up", 25, 40)])
        self.assertEqual(slept, [0.75])

    def test_hold_click_attempts_release_when_sleep_fails(self) -> None:
        sender = FakeMouseSender()

        def failing_sleep(seconds: float) -> None:
            raise RuntimeError(f"sleep failed at {seconds}")

        adapter = LiveInputAdapter(
            target_window=TARGET_WINDOW,
            mouse_sender=sender,
            focus_verifier=FakeFocusVerifier(),
            regions={"start": type("Region", (), {"x": 10, "y": 20, "width": 30, "height": 40})()},
            sleeper=failing_sleep,
        )

        with self.assertRaises(RuntimeError):
            adapter.hold_click("start", 0.5)

        self.assertEqual(sender.events, [("down", 25, 40), ("up", 25, 40)])

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

    def test_background_keyboard_sender_scancode_root_posts_root_only(self) -> None:
        user32 = FakeUser32()
        sender = Win32BackgroundKeyboardSender(user32, "post_message_scancode_root")

        with patch.object(live_module, "_window_message_handles", return_value=[100, 101]):
            sender.key_down(TARGET_WINDOW, ord("L"))
            sender.key_up(TARGET_WINDOW, ord("L"))

        self.assertEqual(
            user32.post_calls,
            [
                (100, live_module.WM_ACTIVATE, live_module.WA_ACTIVE, 0),
                (100, live_module.WM_SETFOCUS, 0, 0),
                (100, live_module.WM_KEYDOWN, ord("L"), 1 | ((ord("L") + 10) << 16)),
                (100, live_module.WM_CHAR, ord("L"), 1 | ((ord("L") + 10) << 16)),
                (
                    100,
                    live_module.WM_KEYUP,
                    ord("L"),
                    1 | ((ord("L") + 10) << 16) | (1 << 30) | (1 << 31),
                ),
            ],
        )
        self.assertEqual(user32.map_calls, [(ord("L"), 0), (ord("L"), 0), (ord("L"), 0)])

    def test_background_keyboard_sender_send_message_timeout_uses_send_calls(self) -> None:
        user32 = FakeUser32()
        sender = Win32BackgroundKeyboardSender(
            user32,
            "send_message_timeout_scancode_all",
        )

        with patch.object(live_module, "_window_message_handles", return_value=[100, 101]):
            sender.key_down(TARGET_WINDOW, ord("B"))

        self.assertEqual(
            user32.post_calls,
            [
                (100, live_module.WM_ACTIVATE, live_module.WA_ACTIVE, 0),
                (100, live_module.WM_SETFOCUS, 0, 0),
                (101, live_module.WM_ACTIVATE, live_module.WA_ACTIVE, 0),
                (101, live_module.WM_SETFOCUS, 0, 0),
            ],
        )
        self.assertEqual(
            [call[:4] for call in user32.send_calls],
            [
                (100, live_module.WM_KEYDOWN, ord("B"), 1 | ((ord("B") + 10) << 16)),
                (100, live_module.WM_CHAR, ord("B"), 1 | ((ord("B") + 10) << 16)),
                (101, live_module.WM_KEYDOWN, ord("B"), 1 | ((ord("B") + 10) << 16)),
                (101, live_module.WM_CHAR, ord("B"), 1 | ((ord("B") + 10) << 16)),
            ],
        )

    def test_foreground_keyboard_sender_sendinput_vk_uses_virtual_key_only(self) -> None:
        user32 = FakeUser32()
        sender = Win32KeyboardSender(user32, "sendinput_vk")

        sender.key_down(ord("L"))
        sender.key_up(ord("L"))

        self.assertEqual(
            user32.sendinput_events,
            [
                (ord("L"), 0, 0, 0),
                (ord("L"), 0, live_module.KEYEVENTF_KEYUP, 0),
            ],
        )

    def test_foreground_keyboard_sender_sendinput_scancode_uses_scan_code(self) -> None:
        user32 = FakeUser32()
        sender = Win32KeyboardSender(user32, "sendinput_scancode")

        sender.key_down(ord("L"))
        sender.key_up(ord("L"))

        self.assertEqual(
            user32.sendinput_events,
            [
                (0, ord("L") + 10, live_module.KEYEVENTF_SCANCODE, 0),
                (
                    0,
                    ord("L") + 10,
                    live_module.KEYEVENTF_SCANCODE | live_module.KEYEVENTF_KEYUP,
                    0,
                ),
            ],
        )
        self.assertEqual(user32.map_calls, [(ord("L"), 0), (ord("L"), 0)])

    def test_foreground_keyboard_sender_sendinput_vk_scancode_sets_both_fields(self) -> None:
        user32 = FakeUser32()
        sender = Win32KeyboardSender(user32, "sendinput_vk_scancode")

        sender.key_down(ord("L"))

        self.assertEqual(
            user32.sendinput_events,
            [(ord("L"), ord("L") + 10, 0, 0)],
        )
        self.assertEqual(user32.map_calls, [(ord("L"), 0)])

    def test_foreground_keyboard_sender_sendinput_unicode_uses_unicode_scan(self) -> None:
        user32 = FakeUser32()
        sender = Win32KeyboardSender(user32, "sendinput_unicode")

        sender.key_down(ord("L"))
        sender.key_up(ord("L"))

        self.assertEqual(
            user32.sendinput_events,
            [
                (0, ord("l"), live_module.KEYEVENTF_UNICODE, 0),
                (0, ord("l"), live_module.KEYEVENTF_UNICODE | live_module.KEYEVENTF_KEYUP, 0),
            ],
        )

    def test_foreground_keyboard_sender_keybd_event_scancode_uses_legacy_api(self) -> None:
        user32 = FakeUser32()
        sender = Win32KeyboardSender(user32, "keybd_event_scancode")

        sender.key_down(ord("L"))
        sender.key_up(ord("L"))

        self.assertEqual(
            user32.keybd_events,
            [
                (ord("L"), ord("L") + 10, live_module.KEYEVENTF_SCANCODE, 0),
                (
                    ord("L"),
                    ord("L") + 10,
                    live_module.KEYEVENTF_SCANCODE | live_module.KEYEVENTF_KEYUP,
                    0,
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
