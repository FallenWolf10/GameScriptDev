from __future__ import annotations

import argparse
import importlib
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from game_script_dev.dashboard.server import create_server


LOOPBACK_HOST = "127.0.0.1"
TERMINAL_RUN_STATUSES = {"cancelled", "completed", "failed", "interrupted"}


class DesktopDependencyUnavailable(RuntimeError):
    """Raised when the optional desktop shell dependencies are unavailable."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="game-script-dev-app",
        description="Open the local GameScriptDev dashboard in a Windows desktop shell.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Existing source or user workspace. Defaults to the current directory.",
    )
    parser.add_argument(
        "--logs",
        type=Path,
        default=Path("logs"),
        help="Run log directory. Defaults to ./logs for source-tree parity.",
    )
    return parser


def run_operator_app(
    workspace_root: Path,
    log_root: Path,
    *,
    webview_module: Any | None = None,
    server_factory: Callable[..., Any] = create_server,
) -> int:
    """Run the dashboard server and its pywebview host until the window closes."""

    webview = webview_module or _load_webview()
    server = server_factory(
        LOOPBACK_HOST,
        0,
        workspace_root,
        log_root,
    )
    port = int(server.server_address[1])
    dashboard_state = getattr(server, "dashboard_state", None)
    if dashboard_state is not None:
        dashboard_state.port = port

    server_thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.1},
        name="game-script-dev-operator-http",
        daemon=True,
    )
    server_thread_started = False
    try:
        server_thread.start()
        server_thread_started = True
        url = f"http://{LOOPBACK_HOST}:{port}/"
        window = webview.create_window(
            "GameScriptDev",
            url,
            width=1280,
            height=800,
            min_size=(960, 640),
        )

        def on_closing(*_args: object) -> bool:
            try:
                if not _has_active_run(server):
                    return True
            except Exception:
                _show_close_warning(
                    window,
                    "Run status unavailable",
                    "Run status could not be verified. Keep GameScriptDev open and try again.",
                )
                return False

            _show_close_warning(
                window,
                "Run still active",
                "Stop the active run before closing GameScriptDev.",
            )
            return False

        window.events.closing += on_closing
        webview.start(gui="edgechromium", private_mode=True)
        return 0
    finally:
        if server_thread_started:
            _stop_server(server, server_thread)
        else:
            server.server_close()


def _load_webview() -> Any:
    try:
        return importlib.import_module("webview")
    except ImportError as error:
        raise DesktopDependencyUnavailable(
            "The desktop shell is not installed. Install the project with "
            "the 'desktop' extra."
        ) from error


def _has_active_run(server: Any) -> bool:
    state = getattr(server, "dashboard_state", None)
    registry = getattr(state, "runs", None)
    if registry is None:
        return False
    active_run = getattr(registry, "active_run", None)
    if callable(active_run):
        return active_run() is not None
    return any(
        str(getattr(run, "status", "")).lower() not in TERMINAL_RUN_STATUSES
        for run in registry.list_runs()
    )


def _show_close_warning(window: Any, title: str, message: str) -> None:
    show_dialog = getattr(window, "create_confirmation_dialog", None)
    if not callable(show_dialog):
        return
    try:
        show_dialog(title, message)
    except Exception:
        # Closing remains cancelled even if the renderer cannot display a dialog.
        return


def _stop_server(server: Any, server_thread: threading.Thread) -> None:
    try:
        server.shutdown()
    finally:
        server.server_close()
        server_thread.join(timeout=5.0)
    if server_thread.is_alive():
        raise RuntimeError("dashboard server did not stop within five seconds")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_operator_app(args.workspace, args.logs)
    except DesktopDependencyUnavailable as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception as error:
        print(f"GameScriptDev desktop shell failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
