from __future__ import annotations

from pathlib import Path
import re

from .config import PROJECT_ROOT

SUPPORTED_MODEL_SUFFIXES = {".pt", ".onnx", ".engine", ".mlmodel", ".torchscript"}
SUPPORTED_MODEL_DIR_SUFFIXES = {".mlpackage"}
MAX_MODEL_FILES = 500
MAX_MODEL_SCAN_DEPTH = 8
ADVANCED_MODEL_HINT = "高级列表可能包含实验权重、last.pt 或预训练模型，普通使用请保持关闭。"


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


def _resolved_path_text(path: str | Path) -> str | None:
    try:
        return str(Path(path).expanduser().resolve()).casefold()
    except (OSError, RuntimeError, ValueError):
        return None


def _recommended_path_set(recommended_paths: set[str] | list[str] | tuple[str, ...] | None) -> set[str]:
    paths: set[str] = set()
    for item in recommended_paths or []:
        resolved = _resolved_path_text(item)
        if resolved:
            paths.add(resolved)
    return paths


def is_recommended_model_path(path: str | Path, recommended_paths: set[str] | list[str] | tuple[str, ...] | None = None) -> bool:
    resolved = _resolved_path_text(path)
    if not resolved:
        return False
    if resolved in _recommended_path_set(recommended_paths):
        return True

    model_path = Path(path)
    parts = {part.casefold() for part in model_path.parts}
    return model_path.name.casefold() == "best.pt" and "final_candidates" in parts


def is_advanced_model_path(path: str | Path, recommended_paths: set[str] | list[str] | tuple[str, ...] | None = None) -> bool:
    if is_recommended_model_path(path, recommended_paths):
        return False

    model_path = Path(path)
    name = model_path.name.casefold()
    stem = model_path.stem.casefold()
    parts = {part.casefold() for part in model_path.parts}

    if name == "last.pt" or re.fullmatch(r"epoch\d+\.pt", name):
        return True
    if stem in {"yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x", "yolo26n", "yolo26s", "yolo26m"}:
        return True
    if {"pretrained", "runs", "experiments", "train", "weights"} & parts:
        return True
    return True


def _model_choice(path: Path, recommended_paths: set[str] | None = None) -> tuple[str, str] | None:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    tier = "推荐模型" if is_recommended_model_path(resolved, recommended_paths) else "高级模型"
    return (f"{tier} - {model_label_from_path(path)}  |  {path}", str(resolved))


def scan_model_files(
    model_dir: str | Path,
    *,
    include_advanced: bool = True,
    recommended_paths: set[str] | list[str] | tuple[str, ...] | None = None,
) -> list[tuple[str, str]]:
    recommended = _recommended_path_set(recommended_paths)
    try:
        root = Path(model_dir or PROJECT_ROOT / "models").expanduser()
        if not root.exists():
            return []
        if _is_supported_model_file(root) or _is_supported_model_dir(root):
            if not include_advanced and is_advanced_model_path(root, recommended):
                return []
            choice = _model_choice(root, recommended)
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
        if not include_advanced and is_advanced_model_path(path, recommended):
            continue
        choice = _model_choice(path, recommended)
        if choice:
            choices.append(choice)
    return choices
