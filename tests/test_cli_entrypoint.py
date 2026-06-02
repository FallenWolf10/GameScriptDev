from __future__ import annotations

import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from game_script_dev.cli import main

PROFILE_YAML = """
version: 1
name: Admin Relaunch Demo
target:
  process_name: demo.exe
window:
  resolution:
    width: 1280
    height: 720
execution:
  max_retries: 1
initial_state: done
states:
  done:
    terminal: true
    result: success
"""


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

    def test_live_cli_can_relaunch_as_admin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.yaml"
            profile_path.write_text(PROFILE_YAML, encoding="utf-8")

            with patch("game_script_dev.cli.is_running_as_admin", return_value=False):
                with patch("game_script_dev.cli.relaunch_module_as_admin") as relaunch:
                    result = main(
                        [
                            "--profile",
                            str(profile_path),
                            "--mode",
                            "live",
                            "--yes",
                            "--run-as-admin",
                        ]
                    )

            self.assertEqual(result, 0)
            relaunch.assert_called_once()
            module, args = relaunch.call_args.args[:2]
            self.assertEqual(module, "game_script_dev")
            self.assertNotIn("--run-as-admin", args)


if __name__ == "__main__":
    unittest.main()
