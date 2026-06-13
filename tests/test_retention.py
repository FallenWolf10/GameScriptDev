from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from game_script_dev.dashboard.server import DashboardState
from game_script_dev.logging_setup import create_run_logger
from game_script_dev.retention import apply_workspace_retention


def _write_file(path: Path, text: str, *, modified_at: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))


class RetentionTests(unittest.TestCase):
    def test_workspace_retention_deletes_only_records_older_than_24_hours(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 6, 12, 12, 0, 0)

            old_log = root / "logs" / "2026-06-10" / "run_old" / "run.log"
            new_log = root / "logs" / "2026-06-12" / "run_new" / "run.log"
            old_artifact = root / "artifacts" / "analysis_old" / "sheet.png"
            new_artifact = root / "artifacts" / "analysis_new" / "sheet.png"

            _write_file(old_log, "old log", modified_at=now - timedelta(hours=30))
            _write_file(new_log, "new log", modified_at=now - timedelta(hours=2))
            _write_file(old_artifact, "old artifact", modified_at=now - timedelta(hours=26))
            _write_file(new_artifact, "new artifact", modified_at=now - timedelta(hours=1))

            summary = apply_workspace_retention(root, now=now)

            self.assertEqual(summary.deleted_files, 2)
            self.assertFalse(old_log.exists())
            self.assertFalse(old_artifact.exists())
            self.assertTrue(new_log.exists())
            self.assertTrue(new_artifact.exists())
            self.assertFalse((root / "logs" / "2026-06-10" / "run_old").exists())
            self.assertFalse((root / "artifacts" / "analysis_old").exists())

    def test_create_run_logger_applies_workspace_retention_before_creating_new_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_root = root / "logs"
            old_artifact = root / "artifacts" / "analysis_old" / "sheet.png"
            _write_file(
                old_artifact,
                "old artifact",
                modified_at=datetime.now() - timedelta(hours=30),
            )

            logger, run_paths = create_run_logger(log_root, "Retention Demo", "dry-run")
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()

            self.assertFalse(old_artifact.exists())
            self.assertTrue(run_paths.run_log.parent.exists())
            self.assertTrue(run_paths.artifact_dir.exists())

    def test_dashboard_state_applies_workspace_retention_on_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "profiles").mkdir()

            with patch(
                "game_script_dev.dashboard.server.apply_workspace_retention"
            ) as retention:
                DashboardState("127.0.0.1", 8765, root, root / "logs")

            retention.assert_called_once_with(root, log_root=root / "logs")


if __name__ == "__main__":
    unittest.main()
