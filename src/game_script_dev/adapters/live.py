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

from game_script_dev.adapters.base import Screenshot, TargetWindow
from game_script_dev.adapters.pillow_vision import PillowVisionAdapter
from game_script_dev.schema import Anchor, Profile, Resolution


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
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


class WindowsWindowAdapter:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def find_target(self, profile: Profile) -> TargetWindow | None:
        candidates = enumerate_windows()
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
        )

    def prepare_window(self, window: TargetWindow, resolution: Resolution) -> None:
        if resolution.policy == "ignore":
            self.logger.info("Skipping resolution check for '%s'", window.title)
            return

        if window.width == resolution.width and window.height == resolution.height:
            self.logger.info(
                "Target window resolution verified: %sx%s",
                window.width,
                window.height,
            )
            return

        if resolution.policy == "attempt_resize":
            raise LiveAdaptersUnavailable(
                "attempt_resize is declared but window resizing is not implemented yet"
            )

        raise TargetWindowNotReady(
            "target window resolution mismatch: "
            f"actual={window.width}x{window.height} "
            f"expected={resolution.width}x{resolution.height}"
        )


class ImageGrabber(Protocol):
    def __call__(self, bbox: tuple[int, int, int, int]) -> Image.Image:
        """Capture an image for the given screen bounding box."""


class KeyboardSender(Protocol):
    def key_down(self, virtual_key: int) -> None:
        """Send a key-down event."""

    def key_up(self, virtual_key: int) -> None:
        """Send a key-up event."""


class FocusVerifier(Protocol):
    def is_foreground(self, window: TargetWindow) -> bool:
        """Return whether the target window is currently foreground."""


class LiveScreenAdapter:
    def __init__(
        self,
        capture_dir: Path,
        grabber: ImageGrabber = ImageGrab.grab,
    ) -> None:
        self.capture_dir = capture_dir
        self.grabber = grabber

    def capture(self, window: TargetWindow) -> Screenshot:
        if window.handle is None:
            raise LiveAdaptersUnavailable(
                "live screen capture requires a window handle"
            )

        self.capture_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S_%f")
        path = self.capture_dir / f"capture_{timestamp}.png"
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
    ) -> None:
        self.delegate = PillowVisionAdapter(
            profile_dir=profile_dir,
            logger=logger,
            default_threshold=default_threshold,
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
        sender: KeyboardSender | None = None,
        focus_verifier: FocusVerifier | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        max_wait_seconds: float = 60.0,
    ) -> None:
        self.target_window = target_window
        self.sender = sender
        self.focus_verifier = focus_verifier
        self.sleeper = sleeper
        self.max_wait_seconds = max_wait_seconds

    def click_template(self, asset: str, screenshot: Screenshot) -> None:
        raise LiveAdaptersUnavailable("live mouse input is not implemented yet")

    def click_region(self, region_name: str) -> None:
        raise LiveAdaptersUnavailable("live mouse input is not implemented yet")

    def press_key(self, key: str) -> None:
        virtual_key = _normalize_key(key)
        self._verify_foreground()
        sender = self._keyboard_sender()
        sender.key_down(virtual_key)
        sender.key_up(virtual_key)

    def hold_key(self, key: str, seconds: float) -> None:
        virtual_key = _normalize_key(key)
        self._validate_duration(seconds, "live key hold")
        self._verify_foreground()
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

    def _verify_foreground(self) -> None:
        if self.target_window is None:
            raise LiveAdaptersUnavailable(
                "live keyboard input requires target window context"
            )
        if self.target_window.handle is None:
            raise LiveAdaptersUnavailable(
                "live keyboard input requires a target window handle"
            )

        verifier = self._focus_verifier()
        if not verifier.is_foreground(self.target_window):
            raise LiveAdaptersUnavailable(
                "target window is not foreground; refusing live keyboard input"
            )

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
