from __future__ import annotations

import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from game_script_dev.cli import main


class CliEntrypointTests(unittest.TestCase):
    def test_module_entrypoint_uses_main_exit_code(self) -> None:
        with patch("game_script_dev.cli.main", return_value=7):
            with self.assertRaises(SystemExit) as captured:
                runpy.run_module("game_script_dev", run_name="__main__")

        self.assertEqual(captured.exception.code, 7)

    def test_scaffold_pack_cli_creates_pack_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_dir = Path(temp_dir) / "pack"

            result = main(
                [
                    "scaffold-pack",
                    "--output",
                    str(pack_dir),
                    "--game",
                    "Example",
                    "--mode",
                    "Daily",
                ]
            )

            self.assertEqual(result, 0)
            self.assertTrue((pack_dir / "profile.yaml").is_file())
            self.assertTrue((pack_dir / "notes.md").is_file())

    def test_doctor_cli_runs_startup_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = main(
                [
                    "doctor",
                    "--workspace",
                    ".",
                    "--logs",
                    str(Path(temp_dir) / "logs"),
                ]
            )

            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
