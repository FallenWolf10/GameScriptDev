from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen

from game_script_dev.dashboard.server import create_server
from game_script_dev.operator_app import run_operator_app


class FakeEvent:
    def __init__(self) -> None:
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self):
        return [handler() for handler in self.handlers]


class FakeWindow:
    def __init__(self, title: str, url: str, options: dict[str, object]) -> None:
        self.title = title
        self.url = url
        self.options = options
        self.events = SimpleNamespace(closing=FakeEvent())
        self.dialogs: list[tuple[str, str]] = []

    def create_confirmation_dialog(self, title: str, message: str) -> bool:
        self.dialogs.append((title, message))
        return True


class FakeWebview:
    def __init__(
        self,
        *,
        probe_url: bool = True,
        start_error: Exception | None = None,
    ) -> None:
        self.probe_url = probe_url
        self.start_error = start_error
        self.window: FakeWindow | None = None
        self.start_options: dict[str, object] | None = None
        self.close_results: list[bool] | None = None
        self.fire_closing = False

    def create_window(self, title: str, url: str, **options: object) -> FakeWindow:
        self.window = FakeWindow(title, url, options)
        return self.window

    def start(self, **options: object) -> None:
        self.start_options = options
        assert self.window is not None
        if self.probe_url:
            with urlopen(self.window.url, timeout=2.0) as response:
                if response.status != 200:
                    raise AssertionError(f"unexpected dashboard status {response.status}")
        if self.fire_closing:
            self.close_results = self.window.events.closing.fire()
        if self.start_error is not None:
            raise self.start_error


class FakeServer:
    def __init__(self, statuses: list[str]) -> None:
        self.server_address = ("127.0.0.1", 43123)
        self.dashboard_state = SimpleNamespace(
            port=0,
            runs=SimpleNamespace(
                active_run=lambda: (
                    SimpleNamespace(status=statuses[0]) if statuses else None
                ),
                list_runs=lambda: [SimpleNamespace(status=status) for status in statuses]
            ),
        )
        self._stop = threading.Event()
        self.shutdown_called = False
        self.server_close_called = False

    def serve_forever(self, *, poll_interval: float) -> None:
        self._stop.wait(max(poll_interval, 1.0))

    def shutdown(self) -> None:
        self.shutdown_called = True
        self._stop.set()

    def server_close(self) -> None:
        self.server_close_called = True


class OperatorAppTests(unittest.TestCase):
    def test_uses_ephemeral_loopback_url_and_cleans_up_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            created_servers = []

            def server_factory(*args, **kwargs):
                server = create_server(*args, **kwargs)
                created_servers.append(server)
                return server

            webview = FakeWebview()
            result = run_operator_app(
                root,
                root / "logs",
                webview_module=webview,
                server_factory=server_factory,
            )

            self.assertEqual(result, 0)
            assert webview.window is not None
            port = int(webview.window.url.removeprefix("http://127.0.0.1:").rstrip("/"))
            self.assertGreater(port, 0)
            self.assertEqual(created_servers[0].dashboard_state.port, port)
            self.assertEqual(created_servers[0].fileno(), -1)
            self.assertEqual(
                webview.start_options,
                {"gui": "edgechromium", "private_mode": True},
            )

    def test_cleans_up_server_when_webview_start_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            created_servers = []

            def server_factory(*args, **kwargs):
                server = create_server(*args, **kwargs)
                created_servers.append(server)
                return server

            webview = FakeWebview(start_error=RuntimeError("renderer failed"))

            with self.assertRaisesRegex(RuntimeError, "renderer failed"):
                run_operator_app(
                    root,
                    root / "logs",
                    webview_module=webview,
                    server_factory=server_factory,
                )

            self.assertEqual(created_servers[0].fileno(), -1)

    def test_active_run_cancels_close_and_shows_warning(self) -> None:
        server = FakeServer(["running"])
        webview = FakeWebview(probe_url=False)
        webview.fire_closing = True

        result = run_operator_app(
            Path("workspace"),
            Path("logs"),
            webview_module=webview,
            server_factory=lambda *_args, **_kwargs: server,
        )

        self.assertEqual(result, 0)
        self.assertEqual(webview.close_results, [False])
        assert webview.window is not None
        self.assertEqual(
            webview.window.dialogs,
            [("Run still active", "Stop the active run before closing GameScriptDev.")],
        )
        self.assertTrue(server.shutdown_called)
        self.assertTrue(server.server_close_called)


if __name__ == "__main__":
    unittest.main()
