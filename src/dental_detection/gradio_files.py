from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
from threading import RLock
from time import time
from typing import Any

import gradio as gr

from .error_messages import friendly_error_message
from .settings_store import APP_HOME, ensure_app_dirs


DOWNLOAD_CACHE_ROOT = APP_HOME / "download_cache"
MAX_CACHED_DOWNLOADS = 100
DOWNLOAD_CACHE_TTL_SECONDS = 60 * 60
_TRUSTED_FILE_ROOTS: set[Path] = set()
_DOWNLOAD_CACHE_LOCK = RLock()


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
        with _DOWNLOAD_CACHE_LOCK:
            DOWNLOAD_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
            _prune_download_cache()
            return [DOWNLOAD_CACHE_ROOT.resolve()]
    except (OSError, RuntimeError, ValueError):
        return []


def remember_allowed_file_root(path: str | Path | None) -> None:
    root = safe_existing_root(path)
    if root is not None:
        with _DOWNLOAD_CACHE_LOCK:
            if any(trusted == root or trusted in root.parents for trusted in _TRUSTED_FILE_ROOTS):
                return
            covered = {
                trusted
                for trusted in _TRUSTED_FILE_ROOTS
                if root in trusted.parents
            }
            _TRUSTED_FILE_ROOTS.difference_update(covered)
            _TRUSTED_FILE_ROOTS.add(root)


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
    with _DOWNLOAD_CACHE_LOCK:
        trusted_roots = list(_TRUSTED_FILE_ROOTS)
    roots = [*allowed_file_roots(), *trusted_roots]
    return any(target == root or root in target.parents for root in roots)


def _prune_download_cache(keep: Path | None = None) -> None:
    try:
        directories = []
        for path in DOWNLOAD_CACHE_ROOT.iterdir():
            if path.is_dir():
                directories.append((path, path.stat().st_mtime))
    except OSError:
        return
    directories.sort(key=lambda item: item[1], reverse=True)
    cutoff = time() - DOWNLOAD_CACHE_TTL_SECONDS
    removable = {path for path, modified_at in directories if modified_at < cutoff}
    removable.update(path for path, _ in directories[MAX_CACHED_DOWNLOADS:])
    for directory in removable:
        if directory == keep:
            continue
        try:
            shutil.rmtree(directory)
        except OSError:
            continue


def _stage_download_file(target: Path) -> Path | None:
    try:
        stat = target.stat()
        fingerprint = sha256(
            f"{target}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8", errors="surrogatepass")
        ).hexdigest()[:20]
        cache_dir = DOWNLOAD_CACHE_ROOT / fingerprint
        cached = cache_dir / target.name
    except (OSError, RuntimeError, ValueError):
        return None

    with _DOWNLOAD_CACHE_LOCK:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            if not cached.is_file() or cached.stat().st_size != stat.st_size:
                temporary = cached.with_name(f".{cached.name}.tmp")
                shutil.copy2(target, temporary)
                temporary.replace(cached)
            _prune_download_cache(cache_dir)
            return cached
        except OSError:
            return None


def file_output(path: str | Path | None) -> str | None:
    if not can_return_file(path):
        return None
    try:
        target = Path(path).expanduser().resolve()
    except (OSError, TypeError, ValueError, RuntimeError):
        return None
    if any(target == root or root in target.parents for root in allowed_file_roots()):
        return str(target)
    staged = _stage_download_file(target)
    return str(staged) if staged is not None else None


def file_component_output(path: str | Path | None):
    file_path = file_output(path)
    return gr.update(value=file_path, visible=bool(file_path))


def path_text(path: Any) -> str:
    return str(path or "") if path else ""


def clear_file_output():
    return gr.update(value=None, visible=False)
