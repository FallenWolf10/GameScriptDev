from __future__ import annotations

import runpy
import unittest
from unittest.mock import patch


class CliEntrypointTests(unittest.TestCase):
    def test_module_entrypoint_uses_main_exit_code(self) -> None:
        with patch("game_script_dev.cli.main", return_value=7):
            with self.assertRaises(SystemExit) as captured:
                runpy.run_module("game_script_dev", run_name="__main__")

        self.assertEqual(captured.exception.code, 7)


if __name__ == "__main__":
    unittest.main()
