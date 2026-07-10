from __future__ import annotations

from pathlib import Path
from typing import Any

import gradio as gr

from .config import PROJECT_ROOT
from .error_messages import friendly_error_message
from .settings_store import APP_HOME, ensure_app_dirs, load_settings


STARTUP_STORAGE_ROOT = Path(load_settings().storage_dir).expanduser()
_EXTRA_ALLOWED_FILE_ROOTS: set[Path] = set()


def safe_existing_root(path: str | Path | None) -> Path | None:
    if not path:
        return None
    try:
        root = Path(path).expanduser().resolve()
    except (OSError, TypeError, ValueError, RuntimeError):
        return None
    try:
        if not root.exists():
            return None
        return root.parent if root.is_file() else root
    except OSError:
        return None


def allowed_file_roots() -> list[Path]:
    try:
        current_storage = safe_existing_root(load_settings().storage_dir)
    except Exception:
        current_storage = None
    roots = [
        APP_HOME,
        STARTUP_STORAGE_ROOT,
        PROJECT_ROOT / "outputs",
        *_EXTRA_ALLOWED_FILE_ROOTS,
    ]
    if current_storage:
        roots.append(current_storage)
    resolved: list[Path] = []
    for root in roots:
        path = safe_existing_root(root)
        if path and path not in resolved:
            resolved.append(path)
    return resolved


def sync_gradio_allowed_paths() -> None:
    try:
        from gradio.context import LocalContext
    except Exception:
        return
    blocks = LocalContext.blocks.get(None)
    if blocks is None:
        return
    try:
        blocks.allowed_paths = [str(root) for root in allowed_file_roots()]
    except Exception:
        return


def remember_allowed_file_root(path: str | Path | None) -> None:
    root = safe_existing_root(path)
    if root is not None:
        _EXTRA_ALLOWED_FILE_ROOTS.add(root)
        sync_gradio_allowed_paths()


def ensure_storage_root(storage_dir: str | None, context: str = "存储目录不可用") -> Path:
    try:
        root = ensure_app_dirs(storage_dir)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise gr.Error(friendly_error_message(exc, context)) from exc
    remember_allowed_file_root(root)
    return root


def can_return_file(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        target = Path(path).expanduser().resolve()
    except (OSError, TypeError, ValueError, RuntimeError):
        return False
    if not target.is_file():
        return False
    return any(target == root or root in target.parents for root in allowed_file_roots())


def file_output(path: str | Path | None) -> str | None:
    return str(path) if can_return_file(path) else None


def file_component_output(path: str | Path | None):
    file_path = file_output(path)
    return gr.update(value=file_path, visible=bool(file_path))


def path_text(path: Any) -> str:
    return str(path or "") if path else ""


def clear_file_output():
    return gr.update(value=None, visible=False)
