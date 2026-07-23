from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from game_script_dev.engine import Engine
from game_script_dev.logging_setup import RunPaths, create_run_logger
from game_script_dev.profile_loader import load_profile
from game_script_dev.schema import validate_profile


TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}


class ActiveRunConflictError(Exception):
    """Raised when a new Run is requested while another Run is active."""

    def __init__(self, active_run: "RunRecord") -> None:
        super().__init__(f"run {active_run.id} is already active")
        self.active_run = active_run


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class RunRecord:
    id: str
    profile_id: str
    profile_path: Path
    mode: str
    status: str = "queued"
    current_state: str | None = None
    final_result: str | None = None
    failure_reason: str | None = None
    started_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    run_paths: RunPaths | None = None
    timeline: list[dict[str, object]] = field(default_factory=list)
    stop_requested: bool = False

    def to_dict(self, *, include_timeline: bool = True) -> dict[str, object]:
        payload = {
            "id": self.id,
            "profile_id": self.profile_id,
            "profile_path": str(self.profile_path),
            "mode": self.mode,
            "status": self.status,
            "current_state": self.current_state,
            "final_result": self.final_result,
            "failure_reason": self.failure_reason,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "log_path": str(self.run_paths.run_log) if self.run_paths else None,
            "artifact_dir": str(self.run_paths.artifact_dir)
            if self.run_paths
            else None,
            "stop_requested": self.stop_requested,
        }
        if include_timeline:
            payload["timeline"] = self.timeline
        return payload

    def to_list_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "mode": self.mode,
            "status": self.status,
            "current_state": self.current_state,
            "final_result": self.final_result,
            "failure_reason": self.failure_reason,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stop_requested": self.stop_requested,
        }


class RunRegistry:
    def __init__(self, log_root: Path) -> None:
        self.log_root = log_root
        self._lock = threading.Lock()
        self._records: dict[str, RunRecord] = {}
        self._run_order: list[str] = []
        self._last_dry_run_success: dict[str, bool] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._artifact_cache: dict[
            str, tuple[tuple[str, int] | None, list[dict[str, object]]]
        ] = {}

    def last_dry_run_success(self, profile_id: str) -> bool:
        with self._lock:
            return self._last_dry_run_success.get(profile_id, False)

    def list_runs(self, *, limit: int | None = None) -> list[RunRecord]:
        with self._lock:
            run_ids = list(self._run_order)
            runs = [self._records[run_id] for run_id in run_ids]
        if limit is None:
            return runs
        return runs[: max(0, limit)]

    def run_count(self) -> int:
        with self._lock:
            return len(self._records)

    def active_run(self) -> RunRecord | None:
        with self._lock:
            return self._active_run_locked()

    def get_run(self, run_id: str) -> RunRecord:
        with self._lock:
            return self._records[run_id]

    def start_run(
        self,
        profile_id: str,
        profile_path: Path,
        mode: str,
    ) -> RunRecord:
        run_id = uuid.uuid4().hex[:12]
        record = RunRecord(
            id=run_id,
            profile_id=profile_id,
            profile_path=profile_path,
            mode=mode,
        )
        stop_event = threading.Event()
        with self._lock:
            active_run = self._active_run_locked()
            if active_run is not None:
                raise ActiveRunConflictError(active_run)
            self._records[run_id] = record
            self._run_order.insert(0, run_id)
            self._stop_events[run_id] = stop_event

        thread = threading.Thread(
            target=self._run_profile,
            args=(record, stop_event),
            name=f"game-script-dev-run-{run_id}",
            daemon=True,
        )
        thread.start()
        return record

    def stop_run(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._records[run_id]
            if record.status in TERMINAL_RUN_STATUSES:
                return record
            record.stop_requested = True
            stop_event = self._stop_events.get(run_id)
            if stop_event is not None:
                stop_event.set()
            return record

    def _active_run_locked(self) -> RunRecord | None:
        for run_id in self._run_order:
            record = self._records[run_id]
            if record.status not in TERMINAL_RUN_STATUSES:
                return record
        return None

    def read_log(self, run_id: str) -> str:
        record = self.get_run(run_id)
        if record.run_paths is None or not record.run_paths.run_log.exists():
            return ""
        return record.run_paths.run_log.read_text(encoding="utf-8")

    def read_log_tail(
        self,
        run_id: str,
        *,
        offset: int = 0,
    ) -> dict[str, object]:
        record = self.get_run(run_id)
        if record.run_paths is None or not record.run_paths.run_log.exists():
            return {"text": "", "offset": 0, "next_offset": 0, "reset": False}

        path = record.run_paths.run_log
        size = path.stat().st_size
        safe_offset = max(0, int(offset))
        reset = False
        if safe_offset > size:
            safe_offset = 0
            reset = True

        with path.open("rb") as handle:
            handle.seek(safe_offset)
            chunk = handle.read()
        return {
            "text": chunk.decode("utf-8"),
            "offset": safe_offset,
            "next_offset": size,
            "reset": reset,
        }

    def list_artifacts(
        self,
        run_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        record = self.get_run(run_id)
        artifacts = self._artifact_entries(record)
        if limit is None:
            return list(artifacts)
        return list(artifacts[: max(0, limit)])

    def artifact_snapshot(
        self,
        run_id: str,
        *,
        limit: int | None = None,
    ) -> dict[str, object]:
        record = self.get_run(run_id)
        artifacts = self._artifact_entries(record)
        visible = (
            artifacts
            if limit is None
            else artifacts[: max(0, limit)]
        )
        return {
            "artifacts": list(visible),
            "total_count": len(artifacts),
            "latest_artifact": artifacts[0] if artifacts else None,
        }

    def run_summary(self, run_id: str) -> dict[str, object]:
        record = self.get_run(run_id)
        log_size = 0
        if record.run_paths is not None and record.run_paths.run_log.exists():
            log_size = record.run_paths.run_log.stat().st_size
        return {
            "id": record.id,
            "profile_id": record.profile_id,
            "mode": record.mode,
            "status": record.status,
            "current_state": record.current_state,
            "final_result": record.final_result,
            "failure_reason": record.failure_reason,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "stop_requested": record.stop_requested,
            "log_size": log_size,
            "timeline_count": len(record.timeline),
            "artifact_stamp": self._artifact_stamp(record),
        }

    def review(
        self,
        run_id: str,
        *,
        after_index: int = 0,
        limit: int | None = None,
        include_artifacts: bool = True,
    ) -> dict[str, object]:
        record = self.get_run(run_id)
        start_index = max(0, int(after_index))
        timeline = record.timeline[start_index:]
        if limit is not None:
            timeline = timeline[: max(0, limit)]
        next_index = start_index + len(timeline)
        payload = {
            "run": record.to_dict(include_timeline=False),
            "timeline": timeline,
            "next_index": next_index,
            "total_count": len(record.timeline),
        }
        if include_artifacts:
            payload["artifacts"] = self.list_artifacts(run_id)
        return payload

    def _artifact_entries(self, record: RunRecord) -> list[dict[str, object]]:
        if record.run_paths is None or not record.run_paths.artifact_dir.exists():
            return []
        signature = self._artifact_signature(record.run_paths.artifact_dir)
        cached = self._artifact_cache.get(record.id)
        if cached is not None and cached[0] == signature:
            return cached[1]

        artifacts: list[dict[str, object]] = []
        for path in record.run_paths.artifact_dir.rglob("*"):
            if path.is_file():
                stat = path.stat()
                artifacts.append(
                    {
                        "name": path.name,
                        "relative_path": path.relative_to(
                            record.run_paths.artifact_dir
                        ).as_posix(),
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(timespec="seconds"),
                    }
                )
        artifacts.sort(
            key=lambda artifact: (
                str(artifact["modified_at"]),
                str(artifact["relative_path"]),
            ),
            reverse=True,
        )
        self._artifact_cache[record.id] = (signature, artifacts)
        return artifacts

    def _artifact_stamp(self, record: RunRecord) -> str | None:
        if record.run_paths is None or not record.run_paths.artifact_dir.exists():
            return None
        signature = self._artifact_signature(record.run_paths.artifact_dir)
        if signature is None:
            return None
        modified_at, child_count = signature
        return f"{modified_at}:{child_count}"

    def _artifact_signature(self, artifact_dir: Path) -> tuple[str, int] | None:
        if not artifact_dir.exists():
            return None
        stat = artifact_dir.stat()
        return (str(stat.st_mtime_ns), stat.st_nlink)

    def artifact_path(self, run_id: str, relative_path: str) -> Path:
        record = self.get_run(run_id)
        if record.run_paths is None:
            raise FileNotFoundError(relative_path)
        root = record.run_paths.artifact_dir.resolve()
        path = (root / relative_path).resolve()
        if root != path and root not in path.parents:
            raise PermissionError("artifact path escapes run artifact directory")
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path

    def _run_profile(self, record: RunRecord, stop_event: threading.Event) -> None:
        logger = None
        try:
            profile = load_profile(record.profile_path)
            validate_profile(profile, record.profile_path.parent)
            logger, run_paths = create_run_logger(
                self.log_root, profile.name, record.mode
            )
            self._update(record.id, status="running", run_paths=run_paths)
            self._append_timeline(
                record.id,
                {"event": "run_started", "mode": record.mode, "at": _now_iso()},
            )

            result = Engine(
                profile=profile,
                mode=record.mode,
                logger=logger,
                artifact_dir=run_paths.artifact_dir,
                profile_dir=record.profile_path.parent,
                sleeper=lambda seconds: self._interruptible_sleep(stop_event, seconds),
                event_handler=lambda event: self._handle_event(record.id, event),
                stop_requested=stop_event.is_set,
            ).run()
            logger.info("Profile finished with result: %s", result)
            self._update(
                record.id,
                status="completed",
                final_result=result,
                finished_at=_now_iso(),
            )
            self._append_timeline(
                record.id,
                {"event": "run_completed", "result": result, "at": _now_iso()},
            )
            if record.mode == "dry-run" and (
                result == "success"
                or (
                    result == "operator_stopped"
                    and profile.manual_stop_is_dry_run_success
                )
            ):
                with self._lock:
                    self._last_dry_run_success[record.profile_id] = True
        except Exception as error:
            self._update(
                record.id,
                status="failed",
                failure_reason=str(error),
                finished_at=_now_iso(),
            )
            self._append_timeline(
                record.id,
                {"event": "run_failed", "failure_reason": str(error), "at": _now_iso()},
            )
        finally:
            if logger is not None:
                for handler in list(logger.handlers):
                    logger.removeHandler(handler)
                    handler.close()
            with self._lock:
                self._stop_events.pop(record.id, None)

    def _handle_event(self, run_id: str, event: dict[str, object]) -> None:
        self._append_timeline(run_id, {"at": _now_iso(), **event})
        updates: dict[str, object] = {}
        if event.get("event") == "state_started":
            updates["current_state"] = event.get("state")
        if event.get("event") == "finished":
            updates["final_result"] = event.get("result")
            updates["failure_reason"] = event.get("failure_reason")
        if updates:
            self._update(run_id, **updates)

    def _append_timeline(self, run_id: str, event: dict[str, object]) -> None:
        with self._lock:
            self._records[run_id].timeline.append(event)

    def _update(self, run_id: str, **updates: object) -> None:
        with self._lock:
            record = self._records[run_id]
            for key, value in updates.items():
                setattr(record, key, value)

    def _interruptible_sleep(
        self,
        stop_event: threading.Event,
        seconds: float,
    ) -> None:
        deadline = time.monotonic() + max(0.0, float(seconds))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            if stop_event.wait(min(remaining, 0.05)):
                return
