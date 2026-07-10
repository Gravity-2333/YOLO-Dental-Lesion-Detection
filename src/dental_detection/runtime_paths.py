from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent
CUSTOM_ULTRALYTICS_PATH = WORKSPACE_ROOT / "yolov8-train"


def ensure_project_ultralytics_path() -> Path | None:
    """Make the sibling yolov8-train source tree importable when present."""
    candidate = CUSTOM_ULTRALYTICS_PATH
    if not (candidate.exists() and (candidate / "ultralytics").is_dir()):
        return None

    resolved = candidate.resolve()
    resolved_text = str(resolved)
    for entry in sys.path:
        try:
            if Path(entry).resolve() == resolved:
                return resolved
        except (OSError, RuntimeError, ValueError):
            if entry == resolved_text:
                return resolved

    sys.path.insert(0, resolved_text)
    return resolved
