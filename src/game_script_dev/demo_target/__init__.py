from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass

WINDOW_TITLE = "Demo Automation Window"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

STATE_HOME = "home"
STATE_DAILY_MENU = "daily_menu"
STATE_COMPLETION = "completion"
STATE_KNOWN_FAILURE = "known_failure"
STATE_INTERRUPTION = "interruption"

HOME_SIGNAL = "Home"
DAILY_SIGNAL = "Daily Tasks"
COMPLETION_SIGNAL = "All Tasks Completed"
KNOWN_FAILURE_SIGNAL = "Known Failure"
INTERRUPTION_SIGNAL = "Network disconnected"

MARKERS = {
    STATE_HOME: "#ff2aa1",
    STATE_DAILY_MENU: "#20d6ff",
    STATE_COMPLETION: "#54f26a",
    STATE_KNOWN_FAILURE: "#ffcb3d",
    STATE_INTERRUPTION: "#b45cff",
}

DAILY_BUTTON_REGION = (510, 360, 770, 500)
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
GWL_WNDPROC = -4


@dataclass
class DemoTargetModel:
    state: str = STATE_HOME
    _daily_action_started: bool = False

    @property
    def signal(self) -> str:
        signals = {
            STATE_HOME: HOME_SIGNAL,
            STATE_DAILY_MENU: DAILY_SIGNAL,
            STATE_COMPLETION: COMPLETION_SIGNAL,
            STATE_KNOWN_FAILURE: KNOWN_FAILURE_SIGNAL,
            STATE_INTERRUPTION: INTERRUPTION_SIGNAL,
        }
        return signals[self.state]

    @property
    def marker_color(self) -> str:
        return MARKERS[self.state]

    def click(self, x: int, y: int) -> None:
        if self.state != STATE_HOME:
            return

        left, top, right, bottom = DAILY_BUTTON_REGION
        if left <= x <= right and top <= y <= bottom:
            self.state = STATE_DAILY_MENU
            self._daily_action_started = False

    def key(self, value: str) -> None:
        normalized = value.lower()
        if normalized == "k":
            self.state = STATE_KNOWN_FAILURE
            return
        if normalized == "i":
            self.state = STATE_INTERRUPTION
            return
        if normalized == "r":
            self.state = STATE_HOME
            self._daily_action_started = False
            return

        if self.state != STATE_DAILY_MENU:
            return
        if normalized == "f":
            self._daily_action_started = True
        elif normalized == "w" and self._daily_action_started:
            self.state = STATE_COMPLETION


class DemoTargetApp:
    def __init__(self, model: DemoTargetModel | None = None) -> None:
        import tkinter as tk

        self.tk = tk
        self.model = model or DemoTargetModel()
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg="#10151f",
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        self.root.bind("<KeyPress>", self._on_key)
        self._message_bridge_handles: list[object] = []
        self.render()

    def run(self) -> int:
        self.root.after(100, self._focus)
        self.root.mainloop()
        return 0

    def render(self) -> None:
        self.canvas.delete("all")
        self._draw_marker()

        if self.model.state == STATE_HOME:
            self._draw_home()
        elif self.model.state == STATE_DAILY_MENU:
            self._draw_daily_menu()
        elif self.model.state == STATE_COMPLETION:
            self._draw_completion()
        elif self.model.state == STATE_INTERRUPTION:
            self._draw_interruption()
        else:
            self._draw_known_failure()

    def _draw_marker(self) -> None:
        self.canvas.create_rectangle(
            40,
            40,
            72,
            72,
            fill=self.model.marker_color,
            outline=self.model.marker_color,
        )

    def _draw_home(self) -> None:
        self._title(HOME_SIGNAL)
        self.canvas.create_text(
            640,
            235,
            text="Local demo target for safe live verification",
            fill="#d8e1eb",
            font=("Segoe UI", 22),
        )
        left, top, right, bottom = DAILY_BUTTON_REGION
        self.canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill="#245f9c",
            outline="#7dc5ff",
            width=4,
        )
        self.canvas.create_text(
            (left + right) // 2,
            (top + bottom) // 2,
            text="Daily Tasks",
            fill="#ffffff",
            font=("Segoe UI", 28, "bold"),
        )

    def _draw_daily_menu(self) -> None:
        self._title(DAILY_SIGNAL)
        self.canvas.create_text(
            640,
            315,
            text="Press F, then hold W to complete the demo flow.",
            fill="#d8e1eb",
            font=("Segoe UI", 24),
        )

    def _draw_completion(self) -> None:
        self._title(COMPLETION_SIGNAL)
        self.canvas.create_text(
            640,
            360,
            text="The local live verification path completed.",
            fill="#d8e1eb",
            font=("Segoe UI", 24),
        )

    def _draw_known_failure(self) -> None:
        self._title(KNOWN_FAILURE_SIGNAL)
        self.canvas.create_text(
            640,
            360,
            text="Controlled failure screen for future validation.",
            fill="#ffe6a3",
            font=("Segoe UI", 24),
        )

    def _draw_interruption(self) -> None:
        self._title(INTERRUPTION_SIGNAL)
        self.canvas.create_text(
            640,
            360,
            text="Controlled interruption screen for future recovery tests.",
            fill="#e8d7ff",
            font=("Segoe UI", 24),
        )

    def _title(self, text: str) -> None:
        self.canvas.create_text(
            640,
            150,
            text=text,
            fill="#ffffff",
            font=("Segoe UI", 42, "bold"),
        )

    def _focus(self) -> None:
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
        self.canvas.focus_set()

    def _on_click(self, event: object) -> None:
        self._apply_click(int(event.x), int(event.y))

    def _on_key(self, event: object) -> None:
        self._apply_key(str(event.keysym))

    def _apply_click(self, x: int, y: int) -> None:
        self.model.click(x, y)
        self.render()

    def _apply_key(self, key: str) -> None:
        self.model.key(key)
        self.render()

    def _install_windows_message_bridge(self) -> None:
        if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
            return

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        call_window_proc = user32.CallWindowProcW
        call_window_proc.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        call_window_proc.restype = ctypes.c_ssize_t

        get_window_long_ptr = user32.GetWindowLongPtrW
        get_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_window_long_ptr.restype = ctypes.c_void_p

        set_window_long_ptr = user32.SetWindowLongPtrW
        set_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        set_window_long_ptr.restype = ctypes.c_void_p

        wndproc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )

        def install(widget: object, *, keyboard: bool, mouse: bool) -> None:
            handle = int(widget.winfo_id())
            previous = get_window_long_ptr(handle, GWL_WNDPROC)

            @wndproc_type
            def bridge(hwnd: int, message: int, w_param: int, l_param: int) -> int:
                if mouse and message in {WM_LBUTTONDOWN, WM_LBUTTONUP}:
                    x, y = _point_from_lparam(l_param)
                    self.root.after_idle(self._apply_click, x, y)
                if keyboard and message in {WM_KEYUP, WM_CHAR}:
                    key = (
                        _char_message_to_demo_key(int(w_param))
                        if message == WM_CHAR
                        else _virtual_key_to_demo_key(int(w_param))
                    )
                    if key is not None:
                        self.root.after_idle(self._apply_key, key)
                return int(call_window_proc(previous, hwnd, message, w_param, l_param))

            set_window_long_ptr(handle, GWL_WNDPROC, bridge)
            self._message_bridge_handles.append((handle, previous, bridge))

        install(self.root, keyboard=True, mouse=False)
        install(self.canvas, keyboard=True, mouse=True)


def _point_from_lparam(l_param: int) -> tuple[int, int]:
    x = ctypes.c_short(l_param & 0xFFFF).value
    y = ctypes.c_short((l_param >> 16) & 0xFFFF).value
    return x, y


def _virtual_key_to_demo_key(virtual_key: int) -> str | None:
    if ord("A") <= virtual_key <= ord("Z"):
        return chr(virtual_key).lower()
    if ord("0") <= virtual_key <= ord("9"):
        return chr(virtual_key)
    return None


def _char_message_to_demo_key(code_point: int) -> str | None:
    if ord("A") <= code_point <= ord("Z"):
        return chr(code_point).lower()
    if ord("a") <= code_point <= ord("z"):
        return chr(code_point).lower()
    if ord("0") <= code_point <= ord("9"):
        return chr(code_point)
    return None


def main() -> int:
    return DemoTargetApp().run()
