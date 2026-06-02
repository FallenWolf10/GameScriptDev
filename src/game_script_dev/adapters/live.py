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
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_EXTENDEDKEY = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MK_LBUTTON = 0x0001
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_ACTIVATE = 0x0006
WM_SETFOCUS = 0x0007
WA_ACTIVE = 0x0001
SMTO_ABORTIFHUNG = 0x0002
SMTO_NORMAL = 0x0000
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32
FOREGROUND_CONFIRM_TIMEOUT_SECONDS = 1.0
FOREGROUND_CONFIRM_POLL_SECONDS = 0.05
PRINT_WINDOW_RENDER_FULL_CONTENT = 0x00000002
PRINT_WINDOW_CLIENT_ONLY = 0x00000001
PRINT_WINDOW_CAPTURE_FLAGS = (
    PRINT_WINDOW_RENDER_FULL_CONTENT | PRINT_WINDOW_CLIENT_ONLY,
    PRINT_WINDOW_CLIENT_ONLY,
)
KLF_NOTELLSHELL = 0x00000080
MAPVK_VK_TO_VSC = 0
MAPVK_VSC_TO_VK_EX = 3
US_QWERTY_LAYOUT_ID = "00000409"
TOKEN_QUERY = 0x0008
TOKEN_INTEGRITY_LEVEL = 25
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DEFAULT_PRESS_KEY_SECONDS = 0.1

KEY_CODES: dict[str, int] = {
    **{chr(code).lower(): code for code in range(ord("A"), ord("Z") + 1)},
    **{str(number): ord(str(number)) for number in range(10)},
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "f1": 0x70,
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


def current_process_integrity_rid() -> int:
    if not hasattr(ctypes, "WinDLL"):
        raise LiveAdaptersUnavailable("process integrity checks require Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return process_integrity_rid(int(kernel32.GetCurrentProcessId()))


def process_integrity_rid(process_id: int) -> int:
    if not hasattr(ctypes, "WinDLL"):
        raise LiveAdaptersUnavailable("process integrity checks require Windows")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    process = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        int(process_id),
    )
    if not process:
        error_code = ctypes.get_last_error()
        if error_code:
            raise ctypes.WinError(error_code)
        raise LiveAdaptersUnavailable("Win32 OpenProcess failed")

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
        error_code = ctypes.get_last_error()
        close_handle(process)
        if error_code:
            raise ctypes.WinError(error_code)
        raise LiveAdaptersUnavailable("Win32 OpenProcessToken failed")

    try:
        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(
            token,
            TOKEN_INTEGRITY_LEVEL,
            None,
            0,
            ctypes.byref(needed),
        )
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token,
            TOKEN_INTEGRITY_LEVEL,
            buffer,
            needed,
            ctypes.byref(needed),
        ):
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            raise LiveAdaptersUnavailable("Win32 GetTokenInformation failed")

        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
        advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
        advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
        count = advapi32.GetSidSubAuthorityCount(sid).contents.value
        return advapi32.GetSidSubAuthority(sid, count - 1).contents.value
    finally:
        close_handle(token)
        close_handle(process)


class WindowsWindowAdapter:
    def __init__(
        self,
        logger: logging.Logger,
        candidates_provider: Callable[[], list[WindowCandidate]] | None = None,
        window_controller: WindowController | None = None,
        require_foreground: bool = True,
    ) -> None:
        self.logger = logger
        self.candidates_provider = candidates_provider or enumerate_windows
        self.window_controller = window_controller
        self.require_foreground = require_foreground

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

        refreshed = _target_window_from_candidate(current)
        if not self.require_foreground:
            self.logger.info(
                "Skipping foreground requirement for '%s' input_mode=background_window_messages",
                refreshed.title,
            )
            return

        controller = self._controller()
        if not self._confirm_foreground(controller, refreshed):
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
        return self._require_live_candidate_after_restore(window, restore_attempted=False)

    def _require_live_candidate_after_restore(
        self,
        window: TargetWindow,
        *,
        restore_attempted: bool,
    ) -> WindowCandidate:
        if window.handle is None:
            raise TargetWindowNotReady("target window handle is missing")

        for candidate in self.candidates_provider():
            if int(candidate.handle) != int(window.handle):
                continue
            if candidate.minimized:
                if not self.require_foreground and not restore_attempted:
                    self._controller().restore(_target_window_from_candidate(candidate))
                    time.sleep(0.2)
                    return self._require_live_candidate_after_restore(
                        window,
                        restore_attempted=True,
                    )
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

    def _confirm_foreground(
        self,
        controller: WindowController,
        window: TargetWindow,
    ) -> bool:
        if controller.is_foreground(window):
            return True

        deadline = time.monotonic() + FOREGROUND_CONFIRM_TIMEOUT_SECONDS
        while True:
            controller.focus(window)
            if controller.is_foreground(window):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(FOREGROUND_CONFIRM_POLL_SECONDS)


class ImageGrabber(Protocol):
    def __call__(self, bbox: tuple[int, int, int, int]) -> Image.Image:
        """Capture an image for the given screen bounding box."""


class WindowCapture(Protocol):
    def capture_client(self, window: TargetWindow) -> Image.Image:
        """Capture the target window client area by handle."""


class KeyboardSender(Protocol):
    def key_down(self, virtual_key: int) -> None:
        """Send a key-down event."""

    def key_up(self, virtual_key: int) -> None:
        """Send a key-up event."""


class MouseSender(Protocol):
    def click(self, x: int, y: int) -> None:
        """Send one left-click at an absolute screen coordinate."""

    def button_down(self, x: int, y: int) -> None:
        """Press the left mouse button at an absolute screen coordinate."""

    def button_up(self, x: int, y: int) -> None:
        """Release the left mouse button at an absolute screen coordinate."""


class FocusVerifier(Protocol):
    def is_foreground(self, window: TargetWindow) -> bool:
        """Return whether the target window is currently foreground."""


class WindowController(Protocol):
    def focus(self, window: TargetWindow) -> None:
        """Ask the OS to bring the target window to foreground."""

    def restore(self, window: TargetWindow) -> None:
        """Ask the OS to restore the target window without requiring foreground."""

    def is_foreground(self, window: TargetWindow) -> bool:
        """Return whether the target window is currently foreground."""


class BackgroundKeyboardSender(Protocol):
    def key_down(self, window: TargetWindow, virtual_key: int) -> None:
        """Send a key-down event to the target window."""

    def key_up(self, window: TargetWindow, virtual_key: int) -> None:
        """Send a key-up event to the target window."""


class BackgroundMouseSender(Protocol):
    def click(self, window: TargetWindow, x: int, y: int) -> None:
        """Send one left-click at target-window client coordinates."""

    def button_down(self, window: TargetWindow, x: int, y: int) -> None:
        """Press the left mouse button at target-window client coordinates."""

    def button_up(self, window: TargetWindow, x: int, y: int) -> None:
        """Release the left mouse button at target-window client coordinates."""


class LiveScreenAdapter:
    def __init__(
        self,
        capture_dir: Path,
        grabber: ImageGrabber = ImageGrab.grab,
        window_adapter: WindowsWindowAdapter | None = None,
        profile: Profile | None = None,
        window_capture: WindowCapture | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.capture_dir = capture_dir
        self.grabber = grabber
        self.window_adapter = window_adapter
        self.profile = profile
        self.window_capture = window_capture
        self.logger = logger
        self._capture_counts: dict[str, int] = {}

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
        context_name = _safe_name(context)
        self._capture_counts[context_name] = self._capture_counts.get(context_name, 0) + 1
        sequence = self._capture_counts[context_name]
        path = self.capture_dir / (
            f"capture_{timestamp}_{context_name}_{sequence:02d}.png"
        )
        image = self._capture_image(window)
        image.save(path)
        return Screenshot(source=window.title, path=path)

    def _capture_image(self, window: TargetWindow) -> Image.Image:
        if (
            self.profile is not None
            and self.profile.target.input_mode == "background_window_messages"
        ):
            capture = self._window_capture()
            try:
                return capture.capture_client(window)
            except LiveAdaptersUnavailable as error:
                if self.logger is not None:
                    self.logger.warning(
                        "Background window capture failed (%s); "
                        "falling back to foreground window-bounds capture",
                        error,
                    )
                window = self._prepare_window_for_bounds_capture(window)
                return self._capture_window_bounds(window)
        return self._capture_window_bounds(window)

    def _capture_window_bounds(self, window: TargetWindow) -> Image.Image:
        bbox = (
            window.left,
            window.top,
            window.left + window.width,
            window.top + window.height,
        )
        return self.grabber(bbox)

    def _prepare_window_for_bounds_capture(self, window: TargetWindow) -> TargetWindow:
        if self.window_adapter is None:
            return window

        if self.profile is not None:
            try:
                window = self.window_adapter.verify_window(window, self.profile)
            except TargetWindowNotReady:
                return window

        controller_factory = getattr(self.window_adapter, "_controller", None)
        confirm_foreground = getattr(self.window_adapter, "_confirm_foreground", None)
        if controller_factory is None or confirm_foreground is None:
            return window

        try:
            confirm_foreground(controller_factory(), window)
        except (LiveAdaptersUnavailable, TargetWindowNotReady):
            return window
        return window

    def _window_capture(self) -> WindowCapture:
        if self.window_capture is not None:
            return self.window_capture
        self.window_capture = Win32WindowCapture.create()
        return self.window_capture


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
        background_sender: BackgroundKeyboardSender | None = None,
        background_mouse_sender: BackgroundMouseSender | None = None,
        focus_verifier: FocusVerifier | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        max_wait_seconds: float = 60.0,
        input_mode: str = "foreground",
        foreground_key_method: str = "sendinput_vk",
        background_key_method: str = "post_message_simple",
        use_qwerty_physical_keys: bool = False,
        press_key_duration: float = DEFAULT_PRESS_KEY_SECONDS,
    ) -> None:
        self.target_window = target_window
        self.profile = profile
        self.regions = regions or {}
        self.window_adapter = window_adapter
        self.sender = sender
        self.mouse_sender = mouse_sender
        self.background_sender = background_sender
        self.background_mouse_sender = background_mouse_sender
        self.focus_verifier = focus_verifier
        self.sleeper = sleeper
        self.max_wait_seconds = max_wait_seconds
        self.input_mode = input_mode
        self.foreground_key_method = foreground_key_method
        self.background_key_method = background_key_method
        self.use_qwerty_physical_keys = use_qwerty_physical_keys
        self.press_key_duration = press_key_duration
        self.key_mapper: QwertyPhysicalKeyMapper | None = None

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
        if self.input_mode == "background_window_messages":
            sender = self._background_mouse_sender()
            sender.click(window, int(x), int(y))
            return
        absolute_x = window.left + int(x)
        absolute_y = window.top + int(y)
        sender = self._mouse_sender()
        sender.click(absolute_x, absolute_y)

    def hold_click(self, region_name: str, seconds: float) -> None:
        region = self.regions.get(region_name)
        if region is None:
            raise LiveAdaptersUnavailable(
                f"live click requires a known profile region: {region_name}"
            )
        x = region.x + region.width // 2
        y = region.y + region.height // 2
        self._validate_duration(seconds, "live mouse hold")
        window = self._verify_live_target()
        if self.input_mode == "background_window_messages":
            sender = self._background_mouse_sender()
            sender.button_down(window, int(x), int(y))
            try:
                self.sleeper(seconds)
            finally:
                sender.button_up(window, int(x), int(y))
            return
        absolute_x = window.left + int(x)
        absolute_y = window.top + int(y)
        sender = self._mouse_sender()
        sender.button_down(absolute_x, absolute_y)
        try:
            self.sleeper(seconds)
        finally:
            sender.button_up(absolute_x, absolute_y)

    def press_key(self, key: str, seconds: float | None = None) -> None:
        key = self._map_key_name(key)
        virtual_key = _normalize_key(key)
        duration = self.press_key_duration if seconds is None else float(seconds)
        self._validate_duration(duration, "live key press")
        window = self._verify_live_target()
        if self.input_mode == "background_window_messages":
            sender = self._background_keyboard_sender()
            sender.key_down(window, virtual_key)
            try:
                self.sleeper(duration)
            finally:
                sender.key_up(window, virtual_key)
            return
        sender = self._keyboard_sender()
        sender.key_down(virtual_key)
        try:
            self.sleeper(duration)
        finally:
            sender.key_up(virtual_key)

    def hold_key(self, key: str, seconds: float) -> None:
        key = self._map_key_name(key)
        virtual_key = _normalize_key(key)
        self._validate_duration(seconds, "live key hold")
        window = self._verify_live_target()
        if self.input_mode == "background_window_messages":
            sender = self._background_keyboard_sender()
            sender.key_down(window, virtual_key)
            try:
                self.sleeper(seconds)
            finally:
                sender.key_up(window, virtual_key)
            return
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
        self.sender = Win32KeyboardSender.create(self.foreground_key_method)
        return self.sender

    def _mouse_sender(self) -> MouseSender:
        if self.mouse_sender is not None:
            return self.mouse_sender
        self.mouse_sender = Win32MouseSender.create()
        return self.mouse_sender

    def _background_keyboard_sender(self) -> BackgroundKeyboardSender:
        if self.background_sender is not None:
            return self.background_sender
        self.background_sender = Win32BackgroundKeyboardSender.create(
            self.background_key_method
        )
        return self.background_sender

    def _background_mouse_sender(self) -> BackgroundMouseSender:
        if self.background_mouse_sender is not None:
            return self.background_mouse_sender
        self.background_mouse_sender = Win32BackgroundMouseSender.create()
        return self.background_mouse_sender

    def _verify_live_target(self) -> TargetWindow:
        if self.target_window is None:
            raise LiveAdaptersUnavailable("live input requires target window context")
        if self.target_window.handle is None:
            raise LiveAdaptersUnavailable("live input requires a target window handle")

        window = self.target_window
        if self.window_adapter is not None and self.profile is not None:
            window = self.window_adapter.verify_window(window, self.profile)
            self.target_window = window

        if self.input_mode == "background_window_messages":
            return window

        verifier = self._focus_verifier()
        if verifier.is_foreground(window):
            return window
        if self._restore_foreground(window):
            return window
        raise LiveAdaptersUnavailable(
            "target window is not foreground; refusing live input"
        )

    def _restore_foreground(self, window: TargetWindow) -> bool:
        if self.window_adapter is None:
            return False

        controller_factory = getattr(self.window_adapter, "_controller", None)
        confirm_foreground = getattr(self.window_adapter, "_confirm_foreground", None)
        if controller_factory is None or confirm_foreground is None:
            return False

        controller = controller_factory()
        return bool(confirm_foreground(controller, window))

    def _focus_verifier(self) -> FocusVerifier:
        if self.focus_verifier is not None:
            return self.focus_verifier
        self.focus_verifier = Win32FocusVerifier.create()
        return self.focus_verifier

    def _map_key_name(self, key: str) -> str:
        if not self.use_qwerty_physical_keys:
            return key
        mapper = self._key_mapper()
        mapped = mapper.map_key_name(key)
        return mapped if mapped is not None else key

    def _key_mapper(self) -> QwertyPhysicalKeyMapper:
        if self.key_mapper is not None:
            return self.key_mapper
        self.key_mapper = QwertyPhysicalKeyMapper.create()
        return self.key_mapper


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
    def __init__(self, user32: ctypes.WinDLL, mode: str) -> None:
        self.user32 = user32
        self.mode = mode

    @classmethod
    def create(cls, mode: str = "sendinput_vk") -> Win32KeyboardSender:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("live keyboard input requires Windows")

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            send_input = user32.SendInput
            if mode.startswith("sendinput_") and mode != "sendinput_vk":
                user32.MapVirtualKeyW
            if mode.startswith("keybd_event_"):
                user32.keybd_event
                user32.MapVirtualKeyW
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
        if mode.startswith("sendinput_") and mode != "sendinput_vk":
            user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
            user32.MapVirtualKeyW.restype = wintypes.UINT
        if mode.startswith("keybd_event_"):
            user32.keybd_event.argtypes = [
                wintypes.BYTE,
                wintypes.BYTE,
                wintypes.DWORD,
                ULONG_PTR,
            ]
            user32.keybd_event.restype = None
            user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
            user32.MapVirtualKeyW.restype = wintypes.UINT
        return cls(user32, mode)

    def key_down(self, virtual_key: int) -> None:
        self._send_key(virtual_key, flags=0)

    def key_up(self, virtual_key: int) -> None:
        self._send_key(virtual_key, flags=KEYEVENTF_KEYUP)

    def _send_key(self, virtual_key: int, flags: int) -> None:
        if self.mode.startswith("keybd_event_"):
            self._send_keybd_event(virtual_key, flags)
            return

        event = self._sendinput_event(virtual_key, flags)
        ctypes.set_last_error(0)
        sent = self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event))
        if sent != 1:
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            raise LiveAdaptersUnavailable("Win32 SendInput did not send keyboard input")

    def _sendinput_event(self, virtual_key: int, flags: int) -> _Input:
        if self.mode == "sendinput_unicode":
            unicode_value = _unicode_key_value(virtual_key)
            input_flags = KEYEVENTF_UNICODE | (
                KEYEVENTF_KEYUP if flags & KEYEVENTF_KEYUP else 0
            )
            return _Input(
                type=INPUT_KEYBOARD,
                union=_InputUnion(
                    ki=_KeyboardInput(
                        wVk=0,
                        wScan=unicode_value,
                        dwFlags=input_flags,
                        time=0,
                        dwExtraInfo=0,
                    )
                ),
            )

        scan_code = self._scan_code(virtual_key)
        input_flags = flags
        w_vk = virtual_key
        w_scan = 0
        if self.mode == "sendinput_scancode":
            w_vk = 0
            w_scan = scan_code
            input_flags |= KEYEVENTF_SCANCODE
        elif self.mode == "sendinput_vk_scancode":
            w_scan = scan_code
        if _is_extended_key(virtual_key):
            input_flags |= KEYEVENTF_EXTENDEDKEY
        event = _Input(
            type=INPUT_KEYBOARD,
            union=_InputUnion(
                ki=_KeyboardInput(
                    wVk=w_vk,
                    wScan=w_scan,
                    dwFlags=input_flags,
                    time=0,
                    dwExtraInfo=0,
                )
            ),
        )
        return event

    def _send_keybd_event(self, virtual_key: int, flags: int) -> None:
        scan_code = self._scan_code(virtual_key)
        key_flags = KEYEVENTF_KEYUP if flags & KEYEVENTF_KEYUP else 0
        byte_scan_code = scan_code & 0xFF
        if self.mode == "keybd_event_scancode":
            key_flags |= KEYEVENTF_SCANCODE
            if _is_extended_key(virtual_key):
                key_flags |= KEYEVENTF_EXTENDEDKEY
        ctypes.set_last_error(0)
        self.user32.keybd_event(
            virtual_key & 0xFF,
            byte_scan_code,
            key_flags,
            0,
        )

    def _scan_code(self, virtual_key: int) -> int:
        return int(self.user32.MapVirtualKeyW(int(virtual_key), 0)) & 0xFF


class QwertyPhysicalKeyMapper:
    def __init__(self, user32: ctypes.WinDLL) -> None:
        self.user32 = user32
        self.qwerty_layout = self.user32.LoadKeyboardLayoutW(
            US_QWERTY_LAYOUT_ID,
            KLF_NOTELLSHELL,
        )

    @classmethod
    def create(cls) -> QwertyPhysicalKeyMapper:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable(
                "physical key mapping requires Windows keyboard layout APIs"
            )
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetKeyboardLayout
            user32.MapVirtualKeyExW
            user32.LoadKeyboardLayoutW
            user32.VkKeyScanExW
            user32.ToUnicodeEx
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "physical key mapping requires Win32 keyboard layout APIs"
            ) from error

        user32.GetKeyboardLayout.argtypes = [ctypes.c_uint]
        user32.GetKeyboardLayout.restype = ctypes.c_void_p
        user32.MapVirtualKeyExW.argtypes = [
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]
        user32.MapVirtualKeyExW.restype = ctypes.c_uint
        user32.LoadKeyboardLayoutW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        user32.LoadKeyboardLayoutW.restype = ctypes.c_void_p
        user32.VkKeyScanExW.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
        user32.VkKeyScanExW.restype = ctypes.c_short
        user32.ToUnicodeEx.argtypes = [
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]
        user32.ToUnicodeEx.restype = ctypes.c_int
        return cls(user32)

    def map_key_name(self, key: str) -> str | None:
        normalized = key.strip().lower()
        if len(normalized) != 1 or not normalized.isascii() or not normalized.isalnum():
            return None

        qwerty_vk = self.user32.VkKeyScanExW(normalized, self.qwerty_layout) & 0xFF
        if qwerty_vk == 0xFF:
            return None

        qwerty_scan_code = self.user32.MapVirtualKeyExW(
            qwerty_vk,
            MAPVK_VK_TO_VSC,
            self.qwerty_layout,
        )
        if qwerty_scan_code == 0:
            return None

        current_layout = self.user32.GetKeyboardLayout(0)
        current_vk = self.user32.MapVirtualKeyExW(
            qwerty_scan_code,
            MAPVK_VSC_TO_VK_EX,
            current_layout,
        )
        if current_vk == 0:
            return None

        keyboard_state = (ctypes.c_ubyte * 256)()
        buffer = ctypes.create_unicode_buffer(8)
        char_count = self.user32.ToUnicodeEx(
            current_vk,
            qwerty_scan_code,
            keyboard_state,
            buffer,
            len(buffer),
            0,
            current_layout,
        )
        if char_count <= 0 or not buffer.value:
            return None
        return buffer.value[0].lower()


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
        self.button_down(x, y)
        self.button_up(x, y)

    def button_down(self, x: int, y: int) -> None:
        self._set_cursor(x, y)
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

    def button_up(self, x: int, y: int) -> None:
        self._set_cursor(x, y)
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def _set_cursor(self, x: int, y: int) -> None:
        ctypes.set_last_error(0)
        if not self.user32.SetCursorPos(int(x), int(y)):
            error_code = ctypes.get_last_error()
            if error_code:
                raise ctypes.WinError(error_code)
            raise LiveAdaptersUnavailable("Win32 SetCursorPos failed")


class Win32WindowCapture:
    def __init__(self, user32: ctypes.WinDLL, gdi32: ctypes.WinDLL) -> None:
        self.user32 = user32
        self.gdi32 = gdi32

    @classmethod
    def create(cls) -> Win32WindowCapture:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("background window capture requires Windows")
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        except OSError as error:
            raise LiveAdaptersUnavailable(
                "background window capture requires Win32 window capture APIs"
            ) from error
        return cls(user32, gdi32)

    def capture_client(self, window: TargetWindow) -> Image.Image:
        if window.handle is None:
            raise LiveAdaptersUnavailable(
                "background window capture requires a target window handle"
            )

        user32 = self.user32
        gdi32 = self.gdi32
        hwnd = int(window.handle)

        get_dc = user32.GetDC
        release_dc = user32.ReleaseDC
        get_client_rect = user32.GetClientRect
        print_window = user32.PrintWindow
        create_compatible_dc = gdi32.CreateCompatibleDC
        create_compatible_bitmap = gdi32.CreateCompatibleBitmap
        select_object = gdi32.SelectObject
        delete_object = gdi32.DeleteObject
        delete_dc = gdi32.DeleteDC
        get_dibits = gdi32.GetDIBits

        get_dc.argtypes = [wintypes.HWND]
        get_dc.restype = wintypes.HDC
        release_dc.argtypes = [wintypes.HWND, wintypes.HDC]
        release_dc.restype = ctypes.c_int
        get_client_rect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        get_client_rect.restype = wintypes.BOOL
        print_window.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        print_window.restype = wintypes.BOOL
        create_compatible_dc.argtypes = [wintypes.HDC]
        create_compatible_dc.restype = wintypes.HDC
        create_compatible_bitmap.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
        ]
        create_compatible_bitmap.restype = wintypes.HBITMAP
        select_object.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        select_object.restype = wintypes.HGDIOBJ
        delete_object.argtypes = [wintypes.HGDIOBJ]
        delete_object.restype = wintypes.BOOL
        delete_dc.argtypes = [wintypes.HDC]
        delete_dc.restype = wintypes.BOOL

        rect = wintypes.RECT()
        if not get_client_rect(hwnd, ctypes.byref(rect)):
            raise LiveAdaptersUnavailable("Win32 GetClientRect failed")
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            raise LiveAdaptersUnavailable("target window client area is empty")

        hwnd_dc = get_dc(hwnd)
        if not hwnd_dc:
            raise LiveAdaptersUnavailable("Win32 GetDC failed")

        mem_dc = create_compatible_dc(hwnd_dc)
        if not mem_dc:
            release_dc(hwnd, hwnd_dc)
            raise LiveAdaptersUnavailable("Win32 CreateCompatibleDC failed")

        bitmap = create_compatible_bitmap(hwnd_dc, width, height)
        if not bitmap:
            delete_dc(mem_dc)
            release_dc(hwnd, hwnd_dc)
            raise LiveAdaptersUnavailable("Win32 CreateCompatibleBitmap failed")

        old_bitmap = select_object(mem_dc, bitmap)
        try:
            for flag in PRINT_WINDOW_CAPTURE_FLAGS:
                if print_window(hwnd, mem_dc, flag):
                    return _bitmap_to_image(
                        gdi32,
                        mem_dc,
                        bitmap,
                        width,
                        height,
                        get_dibits,
                    )
            raise LiveAdaptersUnavailable("Win32 PrintWindow failed")
        finally:
            select_object(mem_dc, old_bitmap)
            delete_object(bitmap)
            delete_dc(mem_dc)
            release_dc(hwnd, hwnd_dc)


class Win32BackgroundKeyboardSender:
    def __init__(self, user32: ctypes.WinDLL, mode: str) -> None:
        self.user32 = user32
        self.mode = mode

    @classmethod
    def create(cls, mode: str = "post_message_simple") -> Win32BackgroundKeyboardSender:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable(
                "background keyboard input requires Windows"
            )

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostMessageW
            if mode != "post_message_simple":
                user32.MapVirtualKeyW
            if mode.startswith("send_message_timeout"):
                user32.SendMessageTimeoutW
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "background keyboard input requires Win32 window messaging"
            ) from error

        user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.PostMessageW.restype = wintypes.BOOL
        if mode != "post_message_simple":
            user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
            user32.MapVirtualKeyW.restype = wintypes.UINT
        if mode.startswith("send_message_timeout"):
            user32.SendMessageTimeoutW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
                wintypes.UINT,
                wintypes.UINT,
                ctypes.POINTER(ULONG_PTR),
            ]
            user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        return cls(user32, mode)

    def key_down(self, window: TargetWindow, virtual_key: int) -> None:
        handles = self._handles(window)
        self._activate_handles(handles)
        l_param = self._key_lparam(virtual_key, key_up=False)
        char_l_param = self._char_lparam(virtual_key)
        for handle in handles:
            self._dispatch(handle, WM_KEYDOWN, virtual_key, l_param)
            character = _virtual_key_to_char(virtual_key)
            if character is not None:
                self._dispatch(handle, WM_CHAR, ord(character), char_l_param)

    def key_up(self, window: TargetWindow, virtual_key: int) -> None:
        l_param = self._key_lparam(virtual_key, key_up=True)
        for handle in self._handles(window):
            self._dispatch(handle, WM_KEYUP, virtual_key, l_param)

    def _post(
        self,
        window: TargetWindow,
        message: int,
        w_param: int,
        l_param: int,
    ) -> None:
        for handle in self._handles(window):
            self._dispatch(handle, message, w_param, l_param)

    def _handles(self, window: TargetWindow) -> list[int]:
        handles = _window_message_handles(self.user32, window)
        if self.mode.endswith("_root"):
            return handles[:1]
        return handles

    def _dispatch(
        self,
        handle: int,
        message: int,
        w_param: int,
        l_param: int,
    ) -> None:
        if self.mode.startswith("send_message_timeout"):
            self._send_handle(handle, message, w_param, l_param)
            return
        self._post_handle(handle, message, w_param, l_param)

    def _activate_handles(self, handles: list[int]) -> None:
        for handle in handles:
            self._post_handle(handle, WM_ACTIVATE, WA_ACTIVE, 0)
            self._post_handle(handle, WM_SETFOCUS, 0, 0)

    def _send_handle(
        self,
        handle: int,
        message: int,
        w_param: int,
        l_param: int,
    ) -> None:
        result_value = ULONG_PTR()
        ctypes.set_last_error(0)
        result = self.user32.SendMessageTimeoutW(
            int(handle),
            int(message),
            int(w_param),
            int(l_param),
            SMTO_NORMAL | SMTO_ABORTIFHUNG,
            200,
            ctypes.byref(result_value),
        )
        if result:
            return
        error_code = ctypes.get_last_error()
        if error_code == 5:
            raise LiveAdaptersUnavailable(
                "Win32 SendMessageTimeoutW access denied for background keyboard input; "
                "run the runner at the same privilege level as the target window"
            )
        if error_code:
            raise ctypes.WinError(error_code)
        raise LiveAdaptersUnavailable(
            "Win32 SendMessageTimeoutW did not deliver keyboard input"
        )

    def _key_lparam(self, virtual_key: int, *, key_up: bool) -> int:
        if self.mode == "post_message_simple":
            return 0xC0000001 if key_up else 1
        scan_code = int(self.user32.MapVirtualKeyW(int(virtual_key), 0)) & 0xFF
        l_param = 1 | (scan_code << 16)
        if _is_extended_key(virtual_key):
            l_param |= 1 << 24
        if key_up:
            l_param |= 1 << 30
            l_param |= 1 << 31
        return l_param

    def _char_lparam(self, virtual_key: int) -> int:
        if self.mode == "post_message_simple":
            return 1
        return self._key_lparam(virtual_key, key_up=False)

    def _post_handle(
        self,
        handle: int,
        message: int,
        w_param: int,
        l_param: int,
    ) -> None:
        ctypes.set_last_error(0)
        if not self.user32.PostMessageW(
            int(handle),
            int(message),
            int(w_param),
            int(l_param),
        ):
            error_code = ctypes.get_last_error()
            if error_code == 5:
                raise LiveAdaptersUnavailable(
                    "Win32 PostMessageW access denied for background keyboard input; "
                    "run the runner at the same privilege level as the target window"
                )
            if error_code:
                raise ctypes.WinError(error_code)
            raise LiveAdaptersUnavailable(
                "Win32 PostMessageW did not queue keyboard input"
            )


class Win32BackgroundMouseSender:
    def __init__(self, user32: ctypes.WinDLL) -> None:
        self.user32 = user32

    @classmethod
    def create(cls) -> Win32BackgroundMouseSender:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("background mouse input requires Windows")

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            post_message = user32.PostMessageW
            child_window_from_point_ex = user32.ChildWindowFromPointEx
            client_to_screen = user32.ClientToScreen
            screen_to_client = user32.ScreenToClient
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "background mouse input requires Win32 window messaging"
            ) from error

        post_message.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        post_message.restype = wintypes.BOOL
        child_window_from_point_ex.argtypes = [
            wintypes.HWND,
            wintypes.POINT,
            wintypes.UINT,
        ]
        child_window_from_point_ex.restype = wintypes.HWND
        client_to_screen.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.POINT),
        ]
        client_to_screen.restype = wintypes.BOOL
        screen_to_client.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.POINT),
        ]
        screen_to_client.restype = wintypes.BOOL
        return cls(user32)

    def click(self, window: TargetWindow, x: int, y: int) -> None:
        self.button_down(window, x, y)
        self.button_up(window, x, y)

    def button_down(self, window: TargetWindow, x: int, y: int) -> None:
        target_handle, target_x, target_y = self._target_at_client_point(window, x, y)
        l_param = _client_coordinates_lparam(target_x, target_y)
        self._activate_click_target(window, target_handle)
        self._post_handle(target_handle, WM_MOUSEMOVE, 0, l_param)
        self._post_handle(target_handle, WM_LBUTTONDOWN, MK_LBUTTON, l_param)

    def button_up(self, window: TargetWindow, x: int, y: int) -> None:
        target_handle, target_x, target_y = self._target_at_client_point(window, x, y)
        l_param = _client_coordinates_lparam(target_x, target_y)
        self._activate_click_target(window, target_handle)
        self._post_handle(target_handle, WM_MOUSEMOVE, 0, l_param)
        self._post_handle(target_handle, WM_LBUTTONUP, 0, l_param)

    def _activate_click_target(self, window: TargetWindow, target_handle: int) -> None:
        if window.handle is None:
            raise LiveAdaptersUnavailable(
                "background mouse input requires a target window handle"
            )
        handles = [int(window.handle)]
        if target_handle != int(window.handle):
            handles.append(int(target_handle))
        for handle in handles:
            self._post_handle(handle, WM_ACTIVATE, WA_ACTIVE, 0)
            self._post_handle(handle, WM_SETFOCUS, 0, 0)

    def _target_at_client_point(
        self,
        window: TargetWindow,
        x: int,
        y: int,
    ) -> tuple[int, int, int]:
        if window.handle is None:
            raise LiveAdaptersUnavailable(
                "background mouse input requires a target window handle"
            )

        root_handle = int(window.handle)
        point = wintypes.POINT(int(x), int(y))
        child_handle = self.user32.ChildWindowFromPointEx(root_handle, point, 0x0001)
        child_handle = int(child_handle or 0)
        if not child_handle:
            child_handle = root_handle
        if child_handle == root_handle:
            return root_handle, int(x), int(y)

        screen_point = wintypes.POINT(int(x), int(y))
        if not self.user32.ClientToScreen(root_handle, ctypes.byref(screen_point)):
            raise LiveAdaptersUnavailable("Win32 ClientToScreen failed")
        if not self.user32.ScreenToClient(child_handle, ctypes.byref(screen_point)):
            raise LiveAdaptersUnavailable("Win32 ScreenToClient failed")
        return child_handle, int(screen_point.x), int(screen_point.y)

    def _post(
        self,
        window: TargetWindow,
        message: int,
        w_param: int,
        l_param: int,
    ) -> None:
        if window.handle is None:
            raise LiveAdaptersUnavailable(
                "background mouse input requires a target window handle"
            )
        self._post_handle(int(window.handle), message, w_param, l_param)

    def _post_handle(
        self,
        handle: int,
        message: int,
        w_param: int,
        l_param: int,
    ) -> None:
        ctypes.set_last_error(0)
        if not self.user32.PostMessageW(
            int(handle),
            int(message),
            int(w_param),
            int(l_param),
        ):
            error_code = ctypes.get_last_error()
            if error_code == 5:
                raise LiveAdaptersUnavailable(
                    "Win32 PostMessageW access denied for background mouse input; "
                    "run the runner at the same privilege level as the target window"
                )
            if error_code:
                raise ctypes.WinError(error_code)
            raise LiveAdaptersUnavailable(
                "Win32 PostMessageW did not queue mouse input"
            )


class Win32WindowController:
    def __init__(self, user32: ctypes.WinDLL, kernel32: ctypes.WinDLL) -> None:
        self.user32 = user32
        self.kernel32 = kernel32

    @classmethod
    def create(cls) -> Win32WindowController:
        if not hasattr(ctypes, "WinDLL"):
            raise LiveAdaptersUnavailable("live window focusing requires Windows")

        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_foreground_window = user32.GetForegroundWindow
            set_foreground_window = user32.SetForegroundWindow
            bring_window_to_top = user32.BringWindowToTop
            set_active_window = user32.SetActiveWindow
            set_focus = user32.SetFocus
            show_window = user32.ShowWindow
            attach_thread_input = user32.AttachThreadInput
            get_window_thread_process_id = user32.GetWindowThreadProcessId
            get_current_thread_id = kernel32.GetCurrentThreadId
        except (AttributeError, OSError) as error:
            raise LiveAdaptersUnavailable(
                "live window focusing requires Win32 foreground APIs"
            ) from error

        get_foreground_window.argtypes = []
        get_foreground_window.restype = wintypes.HWND
        set_foreground_window.argtypes = [wintypes.HWND]
        set_foreground_window.restype = wintypes.BOOL
        bring_window_to_top.argtypes = [wintypes.HWND]
        bring_window_to_top.restype = wintypes.BOOL
        set_active_window.argtypes = [wintypes.HWND]
        set_active_window.restype = wintypes.HWND
        set_focus.argtypes = [wintypes.HWND]
        set_focus.restype = wintypes.HWND
        show_window.argtypes = [wintypes.HWND, ctypes.c_int]
        show_window.restype = wintypes.BOOL
        attach_thread_input.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.BOOL,
        ]
        attach_thread_input.restype = wintypes.BOOL
        get_window_thread_process_id.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_window_thread_process_id.restype = wintypes.DWORD
        get_current_thread_id.argtypes = []
        get_current_thread_id.restype = wintypes.DWORD
        return cls(user32, kernel32)

    def focus(self, window: TargetWindow) -> None:
        if window.handle is None:
            raise TargetWindowNotReady("target window handle is missing")
        hwnd = int(window.handle)
        foreground = int(self.user32.GetForegroundWindow() or 0)
        current_thread_id = int(self.kernel32.GetCurrentThreadId())
        target_thread_id = int(
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wintypes.DWORD()))
        )
        foreground_thread_id = (
            int(
                self.user32.GetWindowThreadProcessId(
                    foreground,
                    ctypes.byref(wintypes.DWORD()),
                )
            )
            if foreground
            else 0
        )

        attached_thread_ids: list[int] = []
        try:
            for thread_id in (target_thread_id, foreground_thread_id):
                if thread_id and thread_id != current_thread_id:
                    ctypes.set_last_error(0)
                    if self.user32.AttachThreadInput(
                        current_thread_id,
                        thread_id,
                        True,
                    ):
                        attached_thread_ids.append(thread_id)
                    else:
                        error_code = ctypes.get_last_error()
                        if error_code:
                            raise ctypes.WinError(error_code)

            self.user32.ShowWindow(hwnd, 9)
            ctypes.set_last_error(0)
            if not self.user32.BringWindowToTop(hwnd):
                error_code = ctypes.get_last_error()
                if error_code:
                    raise ctypes.WinError(error_code)
            self.user32.SetActiveWindow(hwnd)
            self.user32.SetFocus(hwnd)
            ctypes.set_last_error(0)
            if not self.user32.SetForegroundWindow(hwnd):
                error_code = ctypes.get_last_error()
                if error_code:
                    raise ctypes.WinError(error_code)
        finally:
            for thread_id in reversed(attached_thread_ids):
                self.user32.AttachThreadInput(current_thread_id, thread_id, False)

    def restore(self, window: TargetWindow) -> None:
        if window.handle is None:
            raise TargetWindowNotReady("target window handle is missing")
        self.user32.ShowWindow(int(window.handle), 9)

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


def _unicode_key_value(virtual_key: int) -> int:
    if ord("A") <= virtual_key <= ord("Z"):
        return ord(chr(virtual_key).lower())
    if ord("0") <= virtual_key <= ord("9"):
        return virtual_key
    if virtual_key == KEY_CODES["space"]:
        return ord(" ")
    if virtual_key == KEY_CODES["tab"]:
        return ord("\t")
    if virtual_key == KEY_CODES["enter"]:
        return ord("\r")
    raise LiveAdaptersUnavailable(
        "unicode foreground key method only supports printable alphanumeric keys, space, tab, and enter"
    )


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


def _client_coordinates_lparam(x: int, y: int) -> int:
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def _virtual_key_to_char(virtual_key: int) -> str | None:
    if ord("A") <= virtual_key <= ord("Z"):
        return chr(virtual_key)
    if ord("0") <= virtual_key <= ord("9"):
        return chr(virtual_key)
    if virtual_key == KEY_CODES["space"]:
        return " "
    return None


def _is_extended_key(virtual_key: int) -> bool:
    return virtual_key in {
        KEY_CODES["left"],
        KEY_CODES["up"],
        KEY_CODES["right"],
        KEY_CODES["down"],
    }


def _window_message_handles(
    user32: ctypes.WinDLL,
    window: TargetWindow,
) -> list[int]:
    if window.handle is None:
        raise LiveAdaptersUnavailable(
            "background input requires a target window handle"
        )

    root_handle = int(window.handle)
    handles = [root_handle]
    child_handles: list[int] = []

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, lparam: int) -> bool:
        child_handles.append(int(hwnd))
        return True

    user32.EnumChildWindows.argtypes = [wintypes.HWND, enum_proc, wintypes.LPARAM]
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.EnumChildWindows(root_handle, enum_proc(callback), 0)
    handles.extend(child_handles)
    return list(dict.fromkeys(handles))


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BitmapInfoHeader),
        ("bmiColors", wintypes.DWORD * 3),
    ]


def _bitmap_to_image(
    gdi32: ctypes.WinDLL,
    device_context: wintypes.HDC,
    bitmap: wintypes.HBITMAP,
    width: int,
    height: int,
    get_dibits: object,
) -> Image.Image:
    bitmap_info = _BitmapInfo()
    bitmap_info.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
    bitmap_info.bmiHeader.biWidth = width
    bitmap_info.bmiHeader.biHeight = -height
    bitmap_info.bmiHeader.biPlanes = 1
    bitmap_info.bmiHeader.biBitCount = 32
    bitmap_info.bmiHeader.biCompression = 0

    get_dibits.argtypes = [
        wintypes.HDC,
        wintypes.HBITMAP,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(_BitmapInfo),
        wintypes.UINT,
    ]
    get_dibits.restype = ctypes.c_int

    buffer = ctypes.create_string_buffer(width * height * 4)
    rows = get_dibits(
        device_context,
        bitmap,
        0,
        height,
        buffer,
        ctypes.byref(bitmap_info),
        0,
    )
    if rows != height:
        raise LiveAdaptersUnavailable("Win32 GetDIBits failed")
    return Image.frombuffer(
        "RGB",
        (width, height),
        buffer,
        "raw",
        "BGRX",
        0,
        1,
    )


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
