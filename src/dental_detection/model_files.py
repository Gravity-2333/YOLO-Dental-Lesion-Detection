from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT

SUPPORTED_MODEL_SUFFIXES = {".pt", ".onnx", ".engine", ".mlmodel", ".mlpackage", ".torchscript"}
MAX_MODEL_FILES = 500
MAX_MODEL_SCAN_DEPTH = 8


def model_label_from_path(path: str | Path) -> str:
    model_path = Path(path)
    parent = model_path.parent.parent.name if model_path.parent.name == "weights" else model_path.parent.name
    return f"{parent} / {model_path.name}"


def supported_suffix_text() -> str:
    return "、".join(sorted(SUPPORTED_MODEL_SUFFIXES))


def scan_model_files(model_dir: str | Path) -> list[tuple[str, str]]:
    try:
        root = Path(model_dir or PROJECT_ROOT / "models").expanduser()
        if not root.exists():
            return []
        if root.is_file():
            if root.suffix.lower() not in SUPPORTED_MODEL_SUFFIXES:
                return []
            try:
                resolved = root.resolve()
            except (OSError, RuntimeError, ValueError):
                return []
            return [(f"{model_label_from_path(root)}  |  {root}", str(resolved))]
        if not root.is_dir():
            return []
    except (OSError, RuntimeError, ValueError):
        return []

    files: list[Path] = []
    pending: list[tuple[Path, int]] = [(root, 0)]
    while pending and len(files) < MAX_MODEL_FILES:
        current, depth = pending.pop(0)
        if depth > MAX_MODEL_SCAN_DEPTH:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda item: str(item).lower())
        except OSError:
            continue
        for child in children:
            try:
                if child.is_dir():
                    pending.append((child, depth + 1))
                elif child.is_file() and child.suffix.lower() in SUPPORTED_MODEL_SUFFIXES:
                    files.append(child)
                    if len(files) >= MAX_MODEL_FILES:
                        break
            except OSError:
                continue

    choices: list[tuple[str, str]] = []
    for path in files:
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        choices.append((f"{model_label_from_path(path)}  |  {path}", str(resolved)))
    return choices
