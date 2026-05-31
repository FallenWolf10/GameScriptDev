from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from game_script_dev.engine import Engine
from game_script_dev.logging_setup import RunPaths, create_run_logger
from game_script_dev.profile_loader import load_profile
from game_script_dev.schema import validate_profile


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

    def to_dict(self) -> dict[str, object]:
        return {
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
        }


class RunRegistry:
    def __init__(self, log_root: Path) -> None:
        self.log_root = log_root
        self._lock = threading.Lock()
        self._records: dict[str, RunRecord] = {}
        self._last_dry_run_success: dict[str, bool] = {}

    def last_dry_run_success(self, profile_id: str) -> bool:
        with self._lock:
            return self._last_dry_run_success.get(profile_id, False)

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            return sorted(
                self._records.values(),
                key=lambda record: record.started_at,
                reverse=True,
            )

    def get_run(self, run_id: str) -> RunRecord:
        with self._lock:
            return self._records[run_id]

    def start_run(
        self,
        profile_id: str,
        profile_path: Path,
        mode: str,
        *,
        live_confirmation: str | None = None,
    ) -> RunRecord:
        if mode == "live" and live_confirmation != "RUN":
            raise ValueError("live dashboard runs require confirmation text RUN")

        run_id = uuid.uuid4().hex[:12]
        record = RunRecord(
            id=run_id,
            profile_id=profile_id,
            profile_path=profile_path,
            mode=mode,
        )
        with self._lock:
            self._records[run_id] = record

        thread = threading.Thread(
            target=self._run_profile,
            args=(record,),
            name=f"game-script-dev-run-{run_id}",
            daemon=True,
        )
        thread.start()
        return record

    def read_log(self, run_id: str) -> str:
        record = self.get_run(run_id)
        if record.run_paths is None or not record.run_paths.run_log.exists():
            return ""
        return record.run_paths.run_log.read_text(encoding="utf-8")

    def list_artifacts(self, run_id: str) -> list[dict[str, object]]:
        record = self.get_run(run_id)
        if record.run_paths is None or not record.run_paths.artifact_dir.exists():
            return []
        artifacts = []
        for path in sorted(record.run_paths.artifact_dir.rglob("*")):
            if path.is_file():
                artifacts.append(
                    {
                        "name": path.name,
                        "relative_path": path.relative_to(
                            record.run_paths.artifact_dir
                        ).as_posix(),
                        "size": path.stat().st_size,
                    }
                )
        return artifacts

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

    def _run_profile(self, record: RunRecord) -> None:
        logger = None
        try:
            profile = load_profile(record.profile_path)
            validate_profile(profile, record.profile_path.parent)
            logger, run_paths = create_run_logger(
                self.log_root, profile.name, record.mode
            )
            self._update(record.id, status="running", run_paths=run_paths)

            result = Engine(
                profile=profile,
                mode=record.mode,
                logger=logger,
                artifact_dir=run_paths.artifact_dir,
                profile_dir=record.profile_path.parent,
                event_handler=lambda event: self._handle_event(record.id, event),
            ).run()
            logger.info("Profile finished with result: %s", result)
            self._update(
                record.id,
                status="completed",
                final_result=result,
                finished_at=_now_iso(),
            )
            if record.mode == "dry-run" and result == "success":
                with self._lock:
                    self._last_dry_run_success[record.profile_id] = True
        except Exception as error:
            self._update(
                record.id,
                status="failed",
                failure_reason=str(error),
                finished_at=_now_iso(),
            )
        finally:
            if logger is not None:
                for handler in list(logger.handlers):
                    logger.removeHandler(handler)
                    handler.close()

    def _handle_event(self, run_id: str, event: dict[str, object]) -> None:
        updates: dict[str, object] = {}
        if event.get("event") == "state_started":
            updates["current_state"] = event.get("state")
        if event.get("event") == "finished":
            updates["final_result"] = event.get("result")
            updates["failure_reason"] = event.get("failure_reason")
        if updates:
            self._update(run_id, **updates)

    def _update(self, run_id: str, **updates: object) -> None:
        with self._lock:
            record = self._records[run_id]
            for key, value in updates.items():
                setattr(record, key, value)
