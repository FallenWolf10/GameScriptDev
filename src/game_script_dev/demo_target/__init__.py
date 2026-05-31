from __future__ import annotations

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
        self.root.focus_force()
        self.canvas.focus_set()

    def _on_click(self, event: object) -> None:
        self.model.click(int(event.x), int(event.y))
        self.render()

    def _on_key(self, event: object) -> None:
        self.model.key(str(event.keysym))
        self.render()


def main() -> int:
    return DemoTargetApp().run()
