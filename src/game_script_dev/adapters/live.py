from __future__ import annotations

import ctypes
import logging
import math
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from PIL import Image
from PIL import ImageGrab

from game_script_dev.adapters.base import OCRAdapter, Screenshot, TargetWindow
from game_script_dev.adapters.pillow_vision import PillowVisionAdapter
from game_script_dev.schema import Anchor, ClickRegion, Profile, Resolution


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32

KEY_CODES: dict[str, int] = {
    **{chr(code).lower(): code for code in range(ord("A"), ord("Z") + 1)},
    **{str(number): ord(str(number)) for number in range(10)},
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}


class LiveAdaptersUnavailable(Exception):
    """Raised when a live desktop capability is not implemented yet."""


class TargetWindowNotReady(Exception):
    """Raised when the target window cannot be safely prepared."""


@dataclass(frozen=True)
class WindowCandidate:
    handle: int
    title: str
    process_id: int
    process_name: str | None
    left: int
    top: int
    width: int
    height: int
    minimized: bool = False


class WindowsWindowAdapter:
    def __init__(
        self,
        logger: logging.Logger,
        candidates_provider: Callable[[], list[WindowCandidate]] | None = None,
        window_controller: WindowController | None = None,
    ) -> None:
        self.logger = logger
        self.candidates_provider = candidates_provider or enumerate_windows
        self.window_controller = window_controller

    def find_target(self, profile: Profile) -> TargetWindow | None:
        candidates = self.candidates_provider()
        match = find_matching_window(
            candidates=candidates,
            process_name=profile.target.process_name,
            window_title_contains=profile.target.window_title_contains,
        )
        if match is None:
            self.logger.error(
                "No target window matched process=%s title_contains=%s",
                profile.target.process_name,
                profile.target.window_title_contains,
            )
            return None

        self.logger.info(
            "Matched target window: handle=%s process=%s title=%s size=%sx%s",
            match.handle,
            match.process_name,
            match.title,
            match.width,
            match.height,
        )
        return TargetWindow(
            title=match.title,
            process_name=match.process_name,
            left=match.left,
            top=match.top,
            width=match.width,
            height=match.height,
            handle=match.handle,
            process_id=match.process_id,
        )

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        current = self._require_live_candidate(window)
        if resolution.policy == "ignore":
            self.logger.info("Skipping resolution check for '%s'", window.title)
        elif current.width == resolution.width and current.height == resolution.height:
            self.logger.info(
                "Target window resolution verified: %sx%s",
                current.width,
                current.height,
            )
        elif resolution.policy == "attempt_resize":
            raise LiveAdaptersUnavailable(
                "attempt_resize is declared but window resizing is not implemented yet"
            )
        else:
            raise TargetWindowNotReady(
                "target window resolution mismatch: "
                f"actual={current.width}x{current.height} "
                f"expected={resolution.width}x{resolution.height}"
            )

        controller = self._controller()
        refreshed = _target_window_from_candidate(current)
        if not controller.is_foreground(refreshed):
            controller.focus(refreshed)

        if not controller.is_foreground(refreshed):
            raise TargetWindowNotReady(
                "target window could not be confirmed as foreground after focusing"
            )

        self.logger.info("Target window foreground verified: %s", refreshed.title)

    def verify_window(self, window: TargetWindow, profile: Profile) -> TargetWindow:
        current = self._require_live_candidate(window)
        if profile.target.process_name and not _same_process_name(
            current.process_name,
            profile.target.process_name,
        ):
            raise TargetWindowNotReady(
                "target window process changed: "
                f"actual={current.process_name} expected={profile.target.process_name}"
            )
        if profile.target.window_title_contains and (
            profile.target.window_title_contains.lower() not in current.title.lower()
        ):
            raise TargetWindowNotReady(
                "target window title changed: "
                f"actual={current.title} "
                f"expected_contains={profile.target.window_title_contains}"
            )
        return _target_window_from_candidate(current)

    def _require_live_candidate(self, window: TargetWindow) -> WindowCandidate:
        if window.handle is None:
            raise TargetWindowNotReady("target window handle is missing")

        for candidate in self.candidates_provider():
            if int(candidate.handle) != int(window.handle):
                continue
            if candidate.minimized:
                raise TargetWindowNotReady("target window is minimized")
            if (
                window.process_id is not None
                and candidate.process_id != window.process_id
            ):
                raise TargetWindowNotReady(
                    "target window process id changed: "
                    f"actual={candidate.process_id} expected={window.process_id}"
                )
            return candidate

        raise TargetWindowNotReady("target window is no longer visible or available")

    def _controller(self) -> WindowController:
        if self.window_controller is not None:
            return self.window_controller
        self.window_controller = Win32WindowController.create()
        return self.window_controller


class ImageGrabber(Protocol):
    def __call__(self, bbox: tuple[int, int, int, int]) -> Image.Image:
        """Capture an image for the given screen bounding box."""


class KeyboardSender(Protocol):
    def key_down(self, virtual_key: int) -> None:
        """Send a key-down event."""

    def key_up(self, virtual_key: int) -> None:
        """Send a key-up event."""


class MouseSender(Protocol):
    def click(self, x: int, y: int) -> None:
        """Send one left-click at an absolute screen coordinate."""


class FocusVerifier(Protocol):
    def is_foreground(self, window: TargetWindow) -> bool:
        """Return whether the target window is currently foreground."""


class WindowController(Protocol):
    def focus(self, window: TargetWindow) -> None:
        """Ask the OS to bring the target window to foreground."""

    def is_foreground(self, window: TargetWindow) -> bool:
        """Return whether the target window is currently foreground."""


class LiveScreenAdapter:
    def __init__(
        self,
        capture_dir: Path,
        grabber: ImageGrabber = ImageGrab.grab,
        window_adapter: WindowsWindowAdapter | None = None,
        profile: Profile | None = None,
    ) -> None:
        self.capture_dir = capture_dir
        self.grabber = grabber
        self.window_adapter = window_adapter
        self.profile = profile

    def capture(
        self,
        window: TargetWindow,
        context: str | None = None,
    ) -> Screenshot:
        if window.handle is None:
            raise LiveAdaptersUnavailable(
                "live screen capture requires a window handle"
            )
        if self.window_adapter is not None and self.profile is not None:
            window = self.window_adapter.verify_window(window, self.profile)

        self.capture_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S_%f")
        context_part = f"_{_safe_name(context)}" if context else ""
        path = self.capture_dir / f"capture_{timestamp}{context_part}.png"
        bbox = (
            window.left,
            window.top,
            window.left + window.width,
            window.top + window.height,
        )
        image = self.grabber(bbox)
        image.save(path)
        return Screenshot(source=window.title, path=path)


class LiveVisionAdapter:
    def __init__(
        self,
        profile_dir: Path,
        logger: logging.Logger,
        default_threshold: float = 0.98,
        ocr_adapter: OCRAdapter | None = None,
    ) -> None:
        self.delegate = PillowVisionAdapter(
            profile_dir=profile_dir,
            logger=logger,
            default_threshold=default_threshold,
            ocr_adapter=ocr_adapter,
        )

    def anchor_present(self, anchor: Anchor, screenshot: Screenshot) -> bool:
        return self.delegate.anchor_present(anchor, screenshot)

    def find_template_center(
        self,
        asset: str,
        screenshot: Screenshot,
    ) -> tuple[int, int] | None:
        return self.delegate.find_template_center(asset, screenshot)


class LiveInputAdapter:
    def __init__(
        self,
        target_window: TargetWindow | None = None,
        profile: Profile | None = None,
        regions: dict[str, ClickRegion] | None = None,
        window_adapter: WindowsWindowAdapter | None = None,
        sender: KeyboardSender | None = None,
        mouse_sender: MouseSender | None = None,
        focus_verifier: FocusVerifier | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        max_wait_seconds: float = 60.0,
    ) -> None:
        self.target_window = target_window
        self.profile = profile
        self.regions = regions or {}
        self.window_adapter = window_adapter
        self.sender = sender
        self.mouse_sender = mouse_sender
        self.focus_verifier = focus_verifier
        self.sleeper = sleeper
        self.max_wait_seconds = max_wait_seconds

    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        raise LiveAdaptersUnavailable(
            "live template clicks require a resolved template target"
        )

    def click_region(self, region_name: str) -> None:
        region = self.regions.get(region_name)
        if region is None:
            raise LiveAdaptersUnavailable(
                f"live click requires a known profile region: {region_name}"
            )
        x = region.x + region.width // 2
        y = region.y + region.height // 2
        self.click_coordinates(x, y, f"region:{region_name}")

    def click_coordinates(self, x: int, y: int, label: str) -> None:
        window = self._verify_live_target()
        absolute_x = window.left + int(x)
        absolute_y = window.top + int(y)
        sender = self._mouse_sender()
        sender.click(absolute_x, absolute_y)

    def press_key(self, key: str) -> None:
        virtual_key = _normalize_key(key)
        self._verify_live_target()
        sender = self._keyboard_sender()
        sender.key_down(virtual_key)
        sender.key_up(virtual_key)

    def hold_key(self, key: str, seconds: float) -> None:
        virtual_key = _normalize_key(key)
        self._validate_duration(seconds, "live key hold")
        self._verify_live_target()
        sender = self._keyboard_sender()
        sender.key_down(virtual_key)
        try:
            self.sleeper(seconds)
        finally:
            sender.key_up(virtual_key)

    def wait(self, seconds: float) -> None:
        self._validate_duration(seconds, "live wait")
        self.sleeper(seconds)

    def _validate_duration(self, seconds: float, label: str) -> None:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError(f"{label} duration must be a finite non-negative number")
        if seconds > self.max_wait_seconds:
            raise ValueError(
                f"{label} duration exceeds maximum of {self.max_wait_seconds} seconds"
            )

    def _keyboard_sender(self) -> KeyboardSender:
        if self.sender is not None:
            return self.sender
        self.sender = Win32KeyboardSender.create()
        return self.sender

    def _mouse_sender(self) -> MouseSender:
        if self.mouse_sender is not None:
            return self.mouse_sender
        self.mouse_sender = Win32MouseSender.create()
        return self.mouse_sender

    def _verify_live_target(self) -> TargetWindow:
        if self.target_window is None:
            raise LiveAdaptersUnavailable("live input requires target window context")
        if self.target_window.handle is None:
            raise LiveAdaptersUnavailable("live input requires a target window handle")

        window = self.target_window
        if self.window_adapter is not None and self.profile is not None:
            window = self.window_adapter.verify_window(window, self.profile)

        verifier = self._focus_verifier()
        if not verifier.is_foreground(window):
            raise LiveAdaptersUnavailable(
                "target window is not foreground; refusing live input"
            )
        return window

    def _focus_verifier(self) -> FocusVerifier:
        if self.focus_verifier is not None:
            return self.focus_verifier
        self.focus_verifier = Win32FocusVerifier.create()
        return self.focus_verifier


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [
        ("ki", _KeyboardInput),
        ("mi", _MouseInput),
        ("hi", _HardwareInput),
    ]


class _Input(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _InputUnion),
    ]


class Win32KeyboardSender:
    def __init__(self, user32: ctypes.WinDLL) -> None:
        self.user32 = user32

    @classmethod
    def create(cls) -> Win32KeyboardSender:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("live keyboard input requires Windows")

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            send_input = user32.SendInput
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "live keyboard input requires Win32 SendInput"
            ) from error

        send_input.argtypes = [
            wintypes.UINT,
            ctypes.POINTER(_Input),
            ctypes.c_int,
        ]
        send_input.restype = wintypes.UINT
        return cls(user32)

    def key_down(self, virtual_key: int) -> None:
        self._send_key(virtual_key, flags=0)

    def key_up(self, virtual_key: int) -> None:
        self._send_key(virtual_key, flags=KEYEVENTF_KEYUP)

    def _send_key(self, virtual_key: int, flags: int) -> None:
        event = _Input(
            type=INPUT_KEYBOARD,
            union=_InputUnion(
                ki=_KeyboardInput(
                    wVk=virtual_key,
                    wScan=0,
                    dwFlags=flags,
                    time=0,
                    dwExtraInfo=0,
                )
            ),
        )
        ctypes.set_last_error(0)
        sent = self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))
        if sent != 1:
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            raise LiveAdaptersUnavailable("Win32 SendInput did not send keyboard input")


class Win32MouseSender:
    def __init__(self, user32: ctypes.WinDLL) -> None:
        self.user32 = user32

    @classmethod
    def create(cls) -> Win32MouseSender:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("live mouse input requires Windows")

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            set_cursor_pos = user32.SetCursorPos
            mouse_event = user32.mouse_event
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "live mouse input requires Win32 pointer APIs"
            ) from error

        set_cursor_pos.argtypes = [ctypes.c_int, ctypes.c_int]
        set_cursor_pos.restype = wintypes.BOOL
        mouse_event.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ULONG_PTR,
        ]
        mouse_event.restype = None
        return cls(user32)

    def click(self, x: int, y: int) -> None:
        ctypes.set_last_error(0)
        if not self.user32.SetCursorPos(int(x), int(y)):
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            raise LiveAdaptersUnavailable("Win32 SetCursorPos failed")
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


class Win32WindowController:
    def __init__(self, user32: ctypes.WinDLL) -> None:
        self.user32 = user32

    @classmethod
    def create(cls) -> Win32WindowController:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("live window focusing requires Windows")

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            get_foreground_window = user32.GetForegroundWindow
            set_foreground_window = user32.SetForegroundWindow
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "live window focusing requires Win32 foreground APIs"
            ) from error

        get_foreground_window.argtypes = []
        get_foreground_window.restype = wintypes.HWND
        set_foreground_window.argtypes = [wintypes.HWND]
        set_foreground_window.restype = wintypes.BOOL
        return cls(user32)

    def focus(self, window: TargetWindow) -> None:
        if window.handle is None:
            raise TargetWindowNotReady("target window handle is missing")
        ctypes.set_last_error(0)
        if not self.user32.SetForegroundWindow(int(window.handle)):
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)

    def is_foreground(self, window: TargetWindow) -> bool:
        if window.handle is None:
            return False
        return int(self.user32.GetForegroundWindow()) == int(window.handle)


class Win32FocusVerifier:
    def __init__(self, user32: ctypes.WinDLL) -> None:
        self.user32 = user32

    @classmethod
    def create(cls) -> Win32FocusVerifier:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("live focus verification requires Windows")

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            get_foreground_window = user32.GetForegroundWindow
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "live focus verification requires Win32 foreground APIs"
            ) from error

        get_foreground_window.argtypes = []
        get_foreground_window.restype = wintypes.HWND
        return cls(user32)

    def is_foreground(self, window: TargetWindow) -> bool:
        if window.handle is None:
            return False
        return int(self.user32.GetForegroundWindow()) == int(window.handle)


def _normalize_key(key: str) -> int:
    normalized = key.strip().lower()
    if normalized not in KEY_CODES:
        allowed = ", ".join(sorted(KEY_CODES))
        raise ValueError(f"unsupported live key '{key}'; allowed keys: {allowed}")
    return KEY_CODES[normalized]


def _target_window_from_candidate(candidate: WindowCandidate) -> TargetWindow:
    return TargetWindow(
        title=candidate.title,
        process_name=candidate.process_name,
        left=candidate.left,
        top=candidate.top,
        width=candidate.width,
        height=candidate.height,
        handle=candidate.handle,
        process_id=candidate.process_id,
    )


def _safe_name(value: str | None) -> str:
    if not value:
        return "capture"
    safe = "".join(
        character.lower() if character.isalnum() else "-" for character in str(value)
    ).strip("-")
    return safe[:80] or "capture"


def find_matching_window(
    candidates: list[WindowCandidate],
    process_name: str | None,
    window_title_contains: str | None,
) -> WindowCandidate | None:
    for candidate in candidates:
        if process_name and not _same_process_name(
            candidate.process_name,
            process_name,
        ):
            continue
        if window_title_contains and (
            window_title_contains.lower() not in candidate.title.lower()
        ):
            continue
        return candidate
    return None


def enumerate_windows() -> list[WindowCandidate]:
    if not hasattr(ctypes, "WinDLL"):
        raise LiveAdaptersUnavailable("Windows window enumeration requires Windows")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    candidates: list[WindowCandidate] = []

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    def callback(hwnd: int, lparam: int) -> bool:
        try:
            if not user32.IsWindowVisible(hwnd):
                return True

            title = _get_window_title(user32, hwnd)
            if not title:
                return True

            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True

            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            process_name = _get_process_name(process_id.value)

            candidates.append(
                WindowCandidate(
                    handle=int(hwnd),
                    title=title,
                    process_id=int(process_id.value),
                    process_name=process_name,
                    left=int(rect.left),
                    top=int(rect.top),
                    width=int(rect.right - rect.left),
                    height=int(rect.bottom - rect.top),
                    minimized=bool(user32.IsIconic(hwnd)),
                )
            )
        except OSError:
            return True
        return True

    ctypes.set_last_error(0)
    if not user32.EnumWindows(enum_proc(callback), 0):
        error_code = ctypes.get_last_error()
        if error_code:
            raise ctypes.WinError(error_code)

    return candidates


def _get_window_title(user32: ctypes.WinDLL, hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""

    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _get_process_name(process_id: int) -> str | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    query_limited_information = 0x1000
    handle = kernel32.OpenProcess(query_limited_information, False, process_id)
    if not handle:
        return None

    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            return None
        return Path(buffer.value).name
    finally:
        kernel32.CloseHandle(handle)


def _same_process_name(actual: str | None, expected: str) -> bool:
    if actual is None:
        return False
    return actual.lower() == expected.lower()
