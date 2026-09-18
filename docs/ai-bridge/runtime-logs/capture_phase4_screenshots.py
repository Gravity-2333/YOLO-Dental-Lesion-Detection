from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.capture_ui_screenshots import main


if __name__ == "__main__":
    main(["--output", str(ROOT / "docs" / "ai-bridge" / "screenshots" / "phase-4"), "--suffix", "-after"])
