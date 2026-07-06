from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT

SUPPORTED_MODEL_SUFFIXES = {".pt", ".onnx", ".engine", ".mlmodel", ".torchscript"}
SUPPORTED_MODEL_DIR_SUFFIXES = {".mlpackage"}
MAX_MODEL_FILES = 500
MAX_MODEL_SCAN_DEPTH = 8


def model_label_from_path(path: str | Path) -> str:
    model_path = Path(path)
    parent = model_path.parent.parent.name if model_path.parent.name == "weights" else model_path.parent.name
    return f"{parent} / {model_path.name}"


def supported_suffix_text() -> str:
    return "、".join(sorted(SUPPORTED_MODEL_SUFFIXES | SUPPORTED_MODEL_DIR_SUFFIXES))


def _is_supported_model_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_MODEL_SUFFIXES


def _is_supported_model_dir(path: Path) -> bool:
    return path.is_dir() and path.suffix.lower() in SUPPORTED_MODEL_DIR_SUFFIXES


def is_supported_model_artifact(path: str | Path) -> bool:
    model_path = Path(path)
    return _is_supported_model_file(model_path) or _is_supported_model_dir(model_path)


def _model_choice(path: Path) -> tuple[str, str] | None:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    return (f"{model_label_from_path(path)}  |  {path}", str(resolved))


def scan_model_files(model_dir: str | Path) -> list[tuple[str, str]]:
    try:
        root = Path(model_dir or PROJECT_ROOT / "models").expanduser()
        if not root.exists():
            return []
        if _is_supported_model_file(root) or _is_supported_model_dir(root):
            choice = _model_choice(root)
            return [choice] if choice else []
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
                if _is_supported_model_file(child) or _is_supported_model_dir(child):
                    files.append(child)
                    if len(files) >= MAX_MODEL_FILES:
                        break
                elif child.is_dir():
                    pending.append((child, depth + 1))
            except OSError:
                continue

    choices: list[tuple[str, str]] = []
    for path in files:
        choice = _model_choice(path)
        if choice:
            choices.append(choice)
    return choices
