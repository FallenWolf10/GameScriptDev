from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_RETENTION = timedelta(hours=24)


@dataclass(frozen=True)
class RetentionSummary:
    deleted_files: int = 0
    deleted_dirs: int = 0
    freed_bytes: int = 0

    def merge(self, other: "RetentionSummary") -> "RetentionSummary":
        return RetentionSummary(
            deleted_files=self.deleted_files + other.deleted_files,
            deleted_dirs=self.deleted_dirs + other.deleted_dirs,
            freed_bytes=self.freed_bytes + other.freed_bytes,
        )


def apply_retention(
    root: Path,
    *,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_RETENTION,
) -> RetentionSummary:
    if not root.exists():
        return RetentionSummary()

    cutoff = (now or datetime.now()) - max_age
    summary = RetentionSummary()

    for file_path in sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)
        if modified_at >= cutoff:
            continue
        size = file_path.stat().st_size
        file_path.unlink()
        summary = summary.merge(
            RetentionSummary(deleted_files=1, freed_bytes=size)
        )

    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if any(directory.iterdir()):
            continue
        shutil.rmtree(directory)
        summary = summary.merge(RetentionSummary(deleted_dirs=1))

    if root.exists() and root.is_dir() and not any(root.iterdir()):
        return summary

    return summary


def apply_workspace_retention(
    workspace_root: Path,
    *,
    log_root: Path | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_RETENTION,
) -> RetentionSummary:
    summary = RetentionSummary()
    targets = [log_root or workspace_root / "logs", workspace_root / "artifacts"]
    seen: set[Path] = set()
    for target in targets:
        resolved = target.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        summary = summary.merge(
            apply_retention(target, now=now, max_age=max_age)
        )
    return summary
