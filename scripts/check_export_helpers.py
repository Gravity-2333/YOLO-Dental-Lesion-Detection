from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dental_detection.exporters import (
    build_export_manifest,
    cleanup_payload_dir,
    create_zip_from_manifest,
    ensure_export_dir,
    safe_export_stem,
    write_csv_file,
    write_html_file,
    write_json_file,
)


def run_checks() -> None:
    if safe_export_stem("") != "image":
        raise AssertionError("空文件名应回退为 image")
    if safe_export_stem("病例:测试?.png") != "病例_测试":
        raise AssertionError("中文文件名应保留，并过滤 Windows 禁用字符")
    if safe_export_stem("CON.png") != "CON_file":
        raise AssertionError("Windows 保留名应追加后缀")

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        payload_dir = ensure_export_dir(root / "payload")

        csv_path = write_csv_file(
            payload_dir / "detections.csv",
            ["name", "value"],
            [{"name": '=HYPERLINK("http://bad")', "value": "+SUM(1,2)"}],
        )
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        if "'=HYPERLINK" not in csv_text or "'+SUM" not in csv_text:
            raise AssertionError("CSV 写入未保留公式注入防护")

        json_path = write_json_file(payload_dir / "数据.json", {"中文": "正常", "列表": [1, 2]})
        if '"中文": "正常"' not in json_path.read_text(encoding="utf-8"):
            raise AssertionError("JSON 写入未正确保留中文")

        html_path = write_html_file(payload_dir / "report.html", "<html><body>牙齿报告</body></html>")
        if "牙齿报告" not in html_path.read_text(encoding="utf-8"):
            raise AssertionError("HTML 未使用 UTF-8 写入")

        manifest = build_export_manifest(payload_dir)
        archive_names = {item["archive_name"] for item in manifest}
        expected = {"detections.csv", "数据.json", "report.html"}
        if not expected.issubset(archive_names):
            raise AssertionError(f"ZIP manifest 缺少预期文件：{sorted(expected - archive_names)}")

        missing = payload_dir / "missing.txt"
        zip_path, skipped = create_zip_from_manifest(
            root / "bundle.zip",
            [*manifest, {"source_path": str(missing), "archive_name": "missing.txt"}],
        )
        if str(missing) not in skipped:
            raise AssertionError("缺失文件加入 ZIP 时未记录 skipped")
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
        if "detections.csv" not in names or "missing.txt" in names:
            raise AssertionError("ZIP 未正确包含现有文件或未跳过缺失文件")

        cleanup_payload_dir(payload_dir)
        if payload_dir.exists():
            raise AssertionError("临时 payload 目录清理失败")


def main() -> None:
    run_checks()
    print("PASS check_export_helpers")


if __name__ == "__main__":
    main()
