from __future__ import annotations

import csv
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .text_utils import csv_safe_row, json_safe_value


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def safe_export_stem(name: str | Path | None, *, fallback: str = "image", max_chars: int = 120) -> str:
    stem = Path(str(name or fallback)).stem or fallback
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip(" ._")
    if safe.upper() in WINDOWS_RESERVED_NAMES:
        safe = f"{safe}_file"
    safe = safe or fallback
    return safe[:max_chars].rstrip(" ._") or fallback


def ensure_export_dir(path: str | Path) -> Path:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def unique_export_root(base_dir: str | Path, prefix: str, stamp: str, stem: str | None = None) -> Path:
    base = ensure_export_dir(base_dir)
    name = f"{prefix}_{stamp}" if not stem else f"{prefix}_{stamp}_{safe_export_stem(stem)}"
    root = base / name
    counter = 1
    while True:
        try:
            root.mkdir()
            return root
        except FileExistsError:
            root = base / f"{name}_{counter:02d}"
            counter += 1


def zip_path_for_root(root: str | Path) -> Path:
    path = Path(root)
    return path / f"{path.name}.zip"


def write_text_file(path: str | Path, content: str, *, encoding: str = "utf-8") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f".{target.name}.tmp")
    tmp_path.write_text(str(content), encoding=encoding)
    tmp_path.replace(target)
    return target


def write_html_file(path: str | Path, content: str) -> Path:
    return write_text_file(path, content, encoding="utf-8")


def write_json_file(path: str | Path, payload: Any) -> Path:
    return write_text_file(
        path,
        json.dumps(json_safe_value(payload), ensure_ascii=False, indent=2, allow_nan=False),
    )


def write_csv_file(path: str | Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_safe_row(row) for row in rows)
    return target


def build_export_manifest(root: str | Path) -> list[dict[str, str]]:
    payload_root = Path(root)
    entries: list[dict[str, str]] = []
    if not payload_root.exists():
        return entries
    for path in sorted(payload_root.rglob("*")):
        if path.is_file():
            entries.append({"source_path": str(path), "archive_name": path.relative_to(payload_root).as_posix()})
    return entries


def add_existing_file_to_zip(archive: zipfile.ZipFile, source_path: str | Path, archive_name: str | None = None) -> bool:
    source = Path(source_path)
    if not source.is_file():
        return False
    archive.write(source, archive_name or source.name)
    return True


def create_zip_from_manifest(zip_path: str | Path, manifest: list[dict[str, str]]) -> tuple[Path, list[str]]:
    target = Path(zip_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    skipped: list[str] = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in manifest:
            source = entry.get("source_path", "")
            archive_name = entry.get("archive_name") or Path(source).name
            if not add_existing_file_to_zip(archive, source, archive_name):
                skipped.append(str(source))
    return target, skipped


def create_zip_from_directory(zip_path: str | Path, payload_dir: str | Path) -> tuple[Path, list[str]]:
    return create_zip_from_manifest(zip_path, build_export_manifest(payload_dir))


def cleanup_payload_dir(path: str | Path) -> None:
    target = Path(path)
    if target.exists():
        shutil.rmtree(target)


def remove_empty_export_root(root: str | Path, zip_path: str | Path) -> None:
    target = Path(root)
    if not Path(zip_path).exists() and target.exists() and not any(target.iterdir()):
        target.rmdir()
