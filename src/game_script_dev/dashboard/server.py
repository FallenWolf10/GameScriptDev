from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from game_script_dev.dashboard.profile_catalog import ProfileCatalog
from game_script_dev.dashboard.readiness import evaluate_readiness
from game_script_dev.dashboard.run_registry import RunRegistry
from game_script_dev.dashboard.target_preview import (
    TargetPreviewError,
    TargetPreviewService,
)
from game_script_dev.operator_package import run_startup_checks
from game_script_dev.retention import apply_workspace_retention
from game_script_dev.windows_elevation import (
    WindowsElevationError,
    is_running_as_admin,
    relaunch_module_as_admin,
)


class DashboardState:
    def __init__(
        self,
        host: str,
        port: int,
        workspace_root: Path,
        log_root: Path,
        target_preview: TargetPreviewService | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.workspace_root = workspace_root
        self.log_root = log_root
        apply_workspace_retention(workspace_root, log_root=log_root)
        self.catalog = ProfileCatalog(workspace_root / "profiles")
        self.runs = RunRegistry(log_root)
        self.target_preview = target_preview or TargetPreviewService()
        self._readiness_cache: dict[
            tuple[str, bool], tuple[float, object]
        ] = {}


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "GameScriptDevDashboard/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/profiles":
            self._send_json(
                {
                    "profiles": [
                        entry.to_dict() for entry in self.state.catalog.list_profiles()
                    ]
                }
            )
            return
        if path.startswith("/api/profiles/") and path.endswith("/readiness"):
            profile_id = unquote(path.split("/")[3])
            try:
                self._send_json(self._readiness(profile_id).to_dict())
            except KeyError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
            return
        if path.startswith("/api/profiles/") and path.endswith("/target-preview-meta"):
            profile_id = unquote(path.split("/")[3])
            try:
                profile_path = self.state.catalog.get_profile_path(profile_id)
                preview = self.state.target_preview.inspect(profile_path)
            except KeyError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
            except TargetPreviewError as error:
                self._send_error(HTTPStatus.CONFLICT, str(error))
            else:
                self._send_json(preview.to_dict())
            return
        if path.startswith("/api/profiles/") and path.endswith("/target-preview"):
            profile_id = unquote(path.split("/")[3])
            try:
                profile_path = self.state.catalog.get_profile_path(profile_id)
                preview = self.state.target_preview.capture(profile_path)
            except KeyError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
            except TargetPreviewError as error:
                self._send_error(HTTPStatus.CONFLICT, str(error))
            else:
                self._send_json(preview.to_dict())
            return
        if path.startswith("/api/profiles/") and path.endswith("/target-preview-stream"):
            profile_id = unquote(path.split("/")[3])
            try:
                profile_path = self.state.catalog.get_profile_path(profile_id)
            except KeyError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
                return
            self._stream_target_preview(profile_path, query)
            return
        if path == "/api/runs":
            limit = _query_int(query, "limit", None)
            runs = self.state.runs.list_runs(limit=limit)
            self._send_json(
                {
                    "runs": [run.to_list_dict() for run in runs],
                    "total_count": self.state.runs.run_count(),
                }
            )
            return
        if path == "/api/startup-checks":
            report = run_startup_checks(self.state.workspace_root, self.state.runs.log_root)
            self._send_json(
                {
                    "ok": report.ok,
                    "checks": report.checks,
                    "messages": report.messages,
                }
            )
            return
        if path == "/api/runtime":
            self._send_json(self._runtime_status())
            return
        if path.startswith("/api/runs/"):
            self._handle_run_get(path, query)
            return
        self._serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/profiles/") and path.endswith("/validate"):
            profile_id = unquote(path.split("/")[3])
            try:
                entry = self.state.catalog.validate_profile(profile_id)
            except KeyError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
                return
            self._send_json(entry.to_dict())
            return
        if path == "/api/runs":
            self._start_run()
            return
        if path.startswith("/api/runs/") and path.endswith("/stop"):
            self._stop_run(path)
            return
        if path == "/api/runtime/relaunch-admin":
            self._relaunch_admin()
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not found")

    @property
    def state(self) -> DashboardState:
        return self.server.dashboard_state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle_run_get(self, path: str, query: dict[str, list[str]]) -> None:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 3:
            self._send_error(HTTPStatus.NOT_FOUND, "missing run id")
            return
        run_id = unquote(parts[2])
        try:
            if len(parts) == 3:
                self._send_json(self.state.runs.get_run(run_id).to_dict())
                return
            if parts[3] == "summary" and len(parts) == 4:
                self._send_json(self.state.runs.run_summary(run_id))
                return
            if parts[3] == "readiness" and len(parts) == 4:
                run = self.state.runs.get_run(run_id)
                report = self._readiness(run.profile_id).to_dict()
                report["run_id"] = run.id
                self._send_json(report)
                return
            if parts[3] == "review" and len(parts) == 4:
                after_index = _query_int(query, "after", 0)
                limit = _query_int(query, "limit", None)
                include_artifacts = _query_bool(query, "include_artifacts", True)
                self._send_json(
                    self.state.runs.review(
                        run_id,
                        after_index=after_index,
                        limit=limit,
                        include_artifacts=include_artifacts,
                    )
                )
                return
            if parts[3] == "log":
                self._send_text(self.state.runs.read_log(run_id), "text/plain")
                return
            if parts[3] == "log-tail" and len(parts) == 4:
                offset = _query_int(query, "offset", 0)
                payload = self.state.runs.read_log_tail(run_id, offset=offset)
                self._send_text(
                    str(payload["text"]),
                    "text/plain",
                    headers={
                        "X-Log-Offset": str(payload["offset"]),
                        "X-Log-Next-Offset": str(payload["next_offset"]),
                        "X-Log-Reset": "1" if payload["reset"] else "0",
                    },
                )
                return
            if parts[3] == "artifacts" and len(parts) == 4:
                limit = _query_int(query, "limit", None)
                self._send_json(self.state.runs.artifact_snapshot(run_id, limit=limit))
                return
            if parts[3] == "artifacts" and len(parts) > 4:
                relative_path = unquote("/".join(parts[4:]))
                self._send_file(self.state.runs.artifact_path(run_id, relative_path))
                return
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "unknown run id")
            return
        except (FileNotFoundError, PermissionError) as error:
            self._send_error(HTTPStatus.NOT_FOUND, str(error))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not found")

    def _start_run(self) -> None:
        body = self._read_json_body()
        profile_id = str(body.get("profile_id", ""))
        mode = str(body.get("mode", "dry-run"))
        if mode not in {"dry-run", "live"}:
            self._send_error(HTTPStatus.BAD_REQUEST, "mode must be dry-run or live")
            return
        try:
            profile_path = self.state.catalog.get_profile_path(profile_id)
        except KeyError as error:
            self._send_error(HTTPStatus.NOT_FOUND, str(error))
            return
        if mode == "live":
            readiness = self._readiness(profile_id)
            if not readiness.live_available:
                self._send_error(
                    HTTPStatus.CONFLICT,
                    "profile is not ready for live mode",
                    {"readiness": readiness.to_dict()},
                )
                return
        try:
            record = self.state.runs.start_run(
                profile_id,
                profile_path,
                mode,
            )
        except ValueError as error:
            self._send_error(HTTPStatus.BAD_REQUEST, str(error))
            return
        self._send_json(record.to_dict(), status=HTTPStatus.ACCEPTED)

    def _stop_run(self, path: str) -> None:
        run_id = unquote(path.split("/")[3])
        try:
            record = self.state.runs.stop_run(run_id)
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "unknown run id")
            return
        self._send_json(record.to_dict(), status=HTTPStatus.ACCEPTED)

    def _readiness(self, profile_id: str):
        cache_key = (
            profile_id,
            self.state.runs.last_dry_run_success(profile_id),
        )
        cached = self.state._readiness_cache.get(cache_key)
        now = time.monotonic()
        if cached is not None and now - cached[0] <= 1.0:
            return cached[1]
        profile_path = self.state.catalog.get_profile_path(profile_id)
        report = evaluate_readiness(
            profile_id,
            profile_path,
            last_dry_run_success=self.state.runs.last_dry_run_success(profile_id),
            check_target=True,
        )
        self.state._readiness_cache[cache_key] = (now, report)
        stale_keys = [
            key for key in self.state._readiness_cache
            if key[0] == profile_id and key != cache_key
        ]
        for key in stale_keys:
            self.state._readiness_cache.pop(key, None)
        return report

    def _runtime_status(self) -> dict[str, object]:
        return {
            "is_admin": is_running_as_admin(),
            "host": self.state.host,
            "port": self.state.port,
            "workspace": str(self.state.workspace_root),
            "logs": str(self.state.log_root),
        }

    def _stream_target_preview(
        self,
        profile_path: Path,
        query: dict[str, list[str]],
    ) -> None:
        fps = min(max(_query_int(query, "fps", 5) or 5, 1), 12)
        max_width = min(max(_query_int(query, "max_width", 960) or 960, 160), 1920)
        quality = min(max(_query_int(query, "quality", 70) or 70, 30), 95)
        boundary = "game-script-dev-preview"
        interval_seconds = 1.0 / fps

        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            f"multipart/x-mixed-replace; boundary={boundary}",
        )
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        while True:
            frame_started_at = time.monotonic()
            try:
                metadata, jpeg_bytes = self.state.target_preview.capture_jpeg(
                    profile_path,
                    max_width=max_width,
                    quality=quality,
                )
                part_header = (
                    f"--{boundary}\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg_bytes)}\r\n"
                    f"X-Preview-Title: {_header_value(metadata.title)}\r\n"
                    f"X-Preview-Process: {_header_value(metadata.process_name or '')}\r\n"
                    f"X-Preview-Width: {metadata.width}\r\n"
                    f"X-Preview-Height: {metadata.height}\r\n"
                    "\r\n"
                ).encode("utf-8")
                self.wfile.write(part_header)
                self.wfile.write(jpeg_bytes)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            except TargetPreviewError as error:
                self._write_preview_error_part(boundary, str(error))
                break
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                break

            remaining = interval_seconds - (time.monotonic() - frame_started_at)
            if remaining > 0:
                time.sleep(remaining)

    def _write_preview_error_part(self, boundary: str, message: str) -> None:
        try:
            message_bytes = message.encode("utf-8")
            payload = (
                f"--{boundary}\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n"
                f"Content-Length: {len(message_bytes)}\r\n"
                "\r\n"
            ).encode("utf-8") + message_bytes + b"\r\n"
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            return

    def _relaunch_admin(self) -> None:
        if is_running_as_admin():
            self._send_json(
                {"status": "already_admin", **self._runtime_status()},
                status=HTTPStatus.OK,
            )
            return

        args = _dashboard_launch_args(
            host=self.state.host,
            port=self.state.port,
            workspace_root=self.state.workspace_root,
            log_root=self.state.log_root,
            include_run_as_admin=True,
        )
        try:
            relaunch_module_as_admin(
                "game_script_dev.dashboard",
                args,
                cwd=self.state.workspace_root,
            )
        except WindowsElevationError as error:
            self._send_error(HTTPStatus.CONFLICT, str(error))
            return

        self._send_json(
            {
                "status": "relaunching",
                "message": "Approve the Windows prompt, then refresh this page in a moment.",
                **self._runtime_status(),
            },
            status=HTTPStatus.ACCEPTED,
        )
        threading.Thread(
            target=self._shutdown_server_after_delay,
            name="game-script-dev-dashboard-relaunch",
            daemon=True,
        ).start()

    def _shutdown_server_after_delay(self) -> None:
        time.sleep(0.5)
        self.server.shutdown()

    def _serve_static(self, path: str) -> None:
        static_root = Path(__file__).parent / "static"
        if path == "/":
            relative_path = "index.html"
        else:
            relative_path = path.lstrip("/")
        target = (static_root / relative_path).resolve()
        if (
            static_root.resolve() != target
            and static_root.resolve() not in target.parents
        ):
            self._send_error(HTTPStatus.NOT_FOUND, "not found")
            return
        if not target.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "not found")
            return
        self._send_file(target)

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(
        self,
        payload: dict[str, object],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(
        self,
        text: str,
        content_type: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        data = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path) -> None:
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(
        self,
        status: HTTPStatus,
        message: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {"error": message}
        if extra:
            payload.update(extra)
        self._send_json(payload, status=status)


def create_server(
    host: str,
    port: int,
    workspace_root: Path,
    log_root: Path,
    target_preview: TargetPreviewService | None = None,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    server.dashboard_state = DashboardState(  # type: ignore[attr-defined]
        host,
        port,
        workspace_root,
        log_root,
        target_preview,
    )
    return server


def _query_int(
    query: dict[str, list[str]],
    key: str,
    default: int | None,
) -> int | None:
    values = query.get(key)
    if not values:
        return default
    try:
        return int(values[0])
    except ValueError:
        return default


def _query_bool(
    query: dict[str, list[str]],
    key: str,
    default: bool,
) -> bool:
    values = query.get(key)
    if not values:
        return default
    value = values[0].strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _header_value(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ")


def _dashboard_launch_args(
    *,
    host: str,
    port: int,
    workspace_root: Path,
    log_root: Path,
    include_run_as_admin: bool,
) -> list[str]:
    args = [
        "--host",
        host,
        "--port",
        str(port),
        "--workspace",
        str(workspace_root),
        "--logs",
        str(log_root),
    ]
    if include_run_as_admin:
        args.append("--run-as-admin")
    return args


def _serve_dashboard_with_retry(
    host: str,
    port: int,
    workspace_root: Path,
    log_root: Path,
) -> int:
    deadline = time.monotonic() + 8.0
    while True:
        try:
            server = create_server(host, port, workspace_root, log_root)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)
    print(f"Dashboard listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="game-script-dev-dashboard",
        description="Serve the local GameScriptDev dashboard.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--logs", type=Path, default=Path("logs"))
    parser.add_argument(
        "--run-as-admin",
        action="store_true",
        help="On Windows, relaunch the dashboard as administrator.",
    )
    args = parser.parse_args(argv)

    if args.run_as_admin and not is_running_as_admin():
        relaunch_args = _dashboard_launch_args(
            host=args.host,
            port=args.port,
            workspace_root=args.workspace,
            log_root=args.logs,
            include_run_as_admin=False,
        )
        try:
            relaunch_module_as_admin(
                "game_script_dev.dashboard",
                relaunch_args,
                cwd=args.workspace,
            )
        except WindowsElevationError as error:
            print(str(error))
            return 4
        print("Started administrator dashboard in a new Windows process.")
        return 0

    return _serve_dashboard_with_retry(
        args.host,
        args.port,
        args.workspace,
        args.logs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
