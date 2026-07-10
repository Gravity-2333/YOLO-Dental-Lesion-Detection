from __future__ import annotations

from pathlib import Path
from typing import Any


SYSTEM_BROWSER_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)


def launch_chromium_with_fallback(playwright: Any, *, headless: bool = True) -> Any:
    """Launch Playwright Chromium, falling back to installed Chrome or Edge."""
    first_error: Exception | None = None
    try:
        return playwright.chromium.launch(headless=headless)
    except Exception as exc:  # Playwright raises a generic Error subclass.
        first_error = exc

    tried: list[str] = []
    for browser_path in SYSTEM_BROWSER_PATHS:
        if not browser_path.exists():
            continue
        tried.append(str(browser_path))
        try:
            return playwright.chromium.launch(headless=headless, executable_path=str(browser_path))
        except Exception:
            continue

    message = (
        "Playwright Chromium is not installed and no working system Chrome/Edge "
        "browser was found. Run `python -m playwright install chromium`, or install "
        "Chrome/Edge and retry."
    )
    if tried:
        message += f" Tried: {', '.join(tried)}."
    raise RuntimeError(message) from first_error
