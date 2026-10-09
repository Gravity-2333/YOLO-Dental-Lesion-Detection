"""Mirror backend stdout/stderr to the inherited console and separate log files."""

from __future__ import annotations

import codecs
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import BinaryIO, Callable, TextIO


def mirror_output(source: BinaryIO, console: TextIO, log: BinaryIO) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    with source:
        while chunk := source.read1(8192):
            log.write(chunk)
            log.flush()
            console.write(decoder.decode(chunk))
            console.flush()
        console.write(decoder.decode(b"", final=True))
        console.flush()


def stop_backend(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def console_close_probe() -> Callable[[], bool] | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel.GetConsoleWindow.restype = wintypes.HWND
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    window = kernel.GetConsoleWindow()
    if not window or not user.IsWindowVisible(window):
        return None
    return lambda: not user.IsWindowVisible(window)


def watch_console(
    process: subprocess.Popen, finished: threading.Event, has_closed: Callable[[], bool],
) -> None:
    # Some console hosts hide their window before terminating attached clients.
    # Explicitly stop the backend rather than leaving an invisible service alive.
    while not finished.wait(0.25):
        if has_closed():
            stop_backend(process)
            return


def main() -> int:
    # Child bytes already contain platform newlines; do not translate CRLF twice.
    sys.stdout.reconfigure(encoding="utf-8", newline="")
    sys.stderr.reconfigure(encoding="utf-8", newline="")
    if not sys.argv[1:]:
        print("Usage: run_backend_console.py <script> [arguments]", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parents[1]
    log_directory = project_root / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    stdout_path = log_directory / "gradio.stdout.log"
    stderr_path = log_directory / "gradio.stderr.log"
    environment = os.environ.copy()
    environment.update(
        PYTHONUNBUFFERED="1", PYTHONFAULTHANDLER="1", PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
    )
    command = [sys.executable, "-u", *sys.argv[1:]]
    has_console_closed = console_close_probe()

    with stdout_path.open("wb") as stdout_log, stderr_path.open("wb") as stderr_log:
        header = (
            f"[INFO] Backend command: {subprocess.list2cmdline(command)}\n"
            f"[INFO] Standard output log: {stdout_path}\n"
            f"[INFO] Error log: {stderr_path}\n"
        )
        sys.stdout.write(header)
        sys.stdout.flush()
        stdout_log.write(header.encode("utf-8"))
        stdout_log.flush()
        try:
            # Keep the child in this console so closing the window stops both
            # the log forwarder and the backend, including native libraries.
            process = subprocess.Popen(
                command, cwd=project_root, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except OSError as error:
            message = f"[ERROR] Cannot start backend: {error}\n"
            sys.stderr.write(message)
            sys.stderr.flush()
            stderr_log.write(message.encode("utf-8"))
            return 1

        threads = [
            threading.Thread(
                target=mirror_output, args=(process.stdout, sys.stdout, stdout_log),
                daemon=True,
            ),
            threading.Thread(
                target=mirror_output, args=(process.stderr, sys.stderr, stderr_log),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()
        finished = threading.Event()
        console_monitor = None
        if has_console_closed is not None:
            console_monitor = threading.Thread(
                target=watch_console, args=(process, finished, has_console_closed), daemon=True,
            )
            console_monitor.start()
        try:
            return process.wait()
        except KeyboardInterrupt:
            stop_backend(process)
            return 130
        finally:
            finished.set()
            stop_backend(process)
            for thread in threads:
                thread.join()
            if console_monitor is not None:
                console_monitor.join()


if __name__ == "__main__":
    raise SystemExit(main())
