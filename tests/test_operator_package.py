from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from game_script_dev.operator_package import run_startup_checks


class OperatorPackageTests(unittest.TestCase):
    def test_startup_checks_report_core_keys(self) -> None:
        report = run_startup_checks(Path.cwd(), Path(tempfile.mkdtemp()))

        self.assertIn("python_version", report.checks)
        self.assertIn("runtime_dependencies", report.checks)
        self.assertIn("writable_logs", report.checks)
        self.assertIn("profile_discovery", report.checks)
        self.assertIn("profile_validation", report.checks)
        self.assertIn("demo_profile", report.checks)
        self.assertIn("live_adapter_boundary", report.checks)
        self.assertTrue(report.ok, report.messages)


if __name__ == "__main__":
    unittest.main()
