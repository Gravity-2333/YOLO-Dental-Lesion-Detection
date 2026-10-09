from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import re
from tempfile import TemporaryDirectory
import time
import unittest


class BackendConsoleTests(unittest.TestCase):
    def prepare_runner(self, root: Path) -> Path:
        script_directory = root / "scripts"
        script_directory.mkdir()
        runner = script_directory / "run_backend_console.py"
        shutil.copy2(
            Path(__file__).resolve().parents[1] / "scripts" / runner.name, runner,
        )
        return runner

    def test_native_output_is_visible_and_logged_before_backend_exits(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self.prepare_runner(root)
            stdout_marker = "live stdout \u4e2d\u6587"
            stderr_marker = "live stderr \u9519\u8bef"
            child_code = (
                "import os, sys; "
                f"os.write(1, {stdout_marker!r}.encode('utf-8')); "
                f"os.write(2, {stderr_marker!r}.encode('utf-8')); "
                "sys.stdin.readline(); print('backend finished')"
            )
            environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            process = subprocess.Popen(
                [sys.executable, "-u", str(runner), "-c", child_code],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", env=environment,
            )
            try:
                stdout_path = root / "logs" / "gradio.stdout.log"
                stderr_path = root / "logs" / "gradio.stderr.log"
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if (
                        stdout_path.exists() and stderr_path.exists()
                        and stdout_marker in stdout_path.read_text(encoding="utf-8")
                        and stderr_marker in stderr_path.read_text(encoding="utf-8")
                    ):
                        break
                    time.sleep(0.05)
                self.assertIsNone(process.poll())
                self.assertIn(stdout_marker, stdout_path.read_text(encoding="utf-8"))
                self.assertIn(stderr_marker, stderr_path.read_text(encoding="utf-8"))
                stdout, stderr = process.communicate(input="\n", timeout=10)
                self.assertEqual(process.returncode, 0)
                self.assertIn(stdout_marker, stdout)
                self.assertIn(stderr_marker, stderr)
                self.assertIn("backend finished", stdout)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)

    def test_backend_traceback_and_exit_code_are_preserved(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self.prepare_runner(root)
            completed = subprocess.run(
                [
                    sys.executable, "-u", str(runner), "-c",
                    "raise RuntimeError('backend console test failure')",
                ],
                capture_output=True, text=True, encoding="utf-8", timeout=10,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("RuntimeError: backend console test failure", completed.stderr)
            error_log = (root / "logs" / "gradio.stderr.log").read_text(encoding="utf-8")
            self.assertEqual(completed.stderr, error_log)

    def test_previous_logs_are_replaced_on_restart(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self.prepare_runner(root)
            log_directory = root / "logs"
            log_directory.mkdir()
            for name in ("gradio.stdout.log", "gradio.stderr.log"):
                (log_directory / name).write_text("stale output", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-u", str(runner), "-c", "print('fresh output')"],
                capture_output=True, text=True, encoding="utf-8", timeout=10,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(completed.returncode, 0)
            self.assertIn(
                "fresh output", (log_directory / "gradio.stdout.log").read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "stale output", (log_directory / "gradio.stdout.log").read_text(encoding="utf-8"),
            )
            self.assertEqual((log_directory / "gradio.stderr.log").read_bytes(), b"")

    @unittest.skipUnless(os.name == "nt", "Windows console lifecycle")
    def test_closing_test_owned_console_stops_the_backend(self) -> None:
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        user = ctypes.WinDLL("user32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runner = self.prepare_runner(root)
            child_code = (
                "import ctypes, os, time; "
                "kernel = ctypes.WinDLL('kernel32'); "
                "kernel.GetConsoleWindow.restype = ctypes.c_void_p; "
                "print('BACKEND_PID=' + str(os.getpid())); "
                "print('CONSOLE_WINDOW=' + str(kernel.GetConsoleWindow())); "
                "time.sleep(60)"
            )
            process = subprocess.Popen(
                [sys.executable, "-u", str(runner), "-c", child_code],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            child_handle = None
            try:
                stdout_path = root / "logs" / "gradio.stdout.log"
                deadline = time.monotonic() + 10
                contents = ""
                while time.monotonic() < deadline:
                    if stdout_path.exists():
                        contents = stdout_path.read_text(encoding="utf-8")
                        if re.search(r"\nCONSOLE_WINDOW=\d+", contents):
                            break
                    time.sleep(0.05)
                backend_pid = re.search(r"\nBACKEND_PID=(\d+)", contents)
                window = re.search(r"\nCONSOLE_WINDOW=(\d+)", contents)
                self.assertIsNotNone(backend_pid, contents)
                self.assertIsNotNone(window, contents)
                child_handle = kernel.OpenProcess(0x100001, False, int(backend_pid.group(1)))
                self.assertTrue(child_handle)
                self.assertTrue(user.PostMessageW(int(window.group(1)), 0x0112, 0xF060, 0))
                process.wait(timeout=10)
                self.assertEqual(kernel.WaitForSingleObject(child_handle, 1000), 0)
            finally:
                if child_handle:
                    if kernel.WaitForSingleObject(child_handle, 0) != 0:
                        kernel.TerminateProcess(child_handle, 1)
                    kernel.CloseHandle(child_handle)
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
