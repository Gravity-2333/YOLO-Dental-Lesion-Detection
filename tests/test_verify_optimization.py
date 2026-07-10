from __future__ import annotations

from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

import verify_optimization


class VerifyOptimizationTests(unittest.TestCase):
    def test_main_returns_nonzero_when_a_check_fails(self) -> None:
        with (
            patch.object(verify_optimization, "_check_css", return_value=["模拟失败"]),
            patch.object(verify_optimization, "_check_python_modules", return_value=[]),
            patch.object(verify_optimization, "_check_project_files", return_value=[]),
            patch.object(verify_optimization, "_check_models", return_value=[]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(verify_optimization.main(), 1)

    def test_main_returns_zero_when_all_checks_pass(self) -> None:
        with (
            patch.object(verify_optimization, "_check_css", return_value=[]),
            patch.object(verify_optimization, "_check_python_modules", return_value=[]),
            patch.object(verify_optimization, "_check_project_files", return_value=[]),
            patch.object(verify_optimization, "_check_models", return_value=[]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(verify_optimization.main(), 0)


if __name__ == "__main__":
    unittest.main()
