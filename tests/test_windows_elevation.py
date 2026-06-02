from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from game_script_dev import windows_elevation


class WindowsElevationTests(unittest.TestCase):
    def test_elevated_command_includes_workspace_src_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()

            with patch.object(windows_elevation.sys, "executable", "python.exe"):
                command = windows_elevation._powershell_command(
                    "game_script_dev",
                    ["--profile", "profiles\\demo\\profile.yaml"],
                    root,
                )

        self.assertIn("$env:PYTHONPATH", command)
        self.assertIn("src", command)
        self.assertIn("'python.exe' '-m' 'game_script_dev'", command)


if __name__ == "__main__":
    unittest.main()
