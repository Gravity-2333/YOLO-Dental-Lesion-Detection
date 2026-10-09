from __future__ import annotations

import copy
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from src.dental_detection.case_snapshot import (
    LEGACY_CASE_MESSAGE,
    case_snapshot_detail_data,
    load_case_snapshot,
    reusable_case_snapshot,
    save_case_snapshot,
)
from src.dental_detection.case_store import export_case_report, load_case_record, move_case_to_trash
from src.dental_detection.personal_workspace import (
    PERSONAL_PATIENT_ID,
    create_personal_patient,
    ensure_personal_workspace,
    record_completed_detection,
)
from src.dental_detection.record_formatters import case_record_detail_html
from src.dental_detection.workspace_store import SCHEMA_VERSION, WorkspaceStore


def snapshot_fixture(root: str, *, compare: bool = False, clahe: bool = False):
    task = record_completed_detection(
        root, PERSONAL_PATIENT_ID, "model-a",
        parameters={"conf": 0.34, "iou": 0.65, "device": "cpu", "use_clahe": clahe},
        result_summary={"detection_count": 1},
    )
    original = Image.new("RGB", (160, 80), "#777777")
    original.info["patient_name"] = "private metadata"
    input_image = Image.new("RGB", (160, 80), "#bbbbbb") if clahe else original
    detections = [{"class": "Caries", "中文名称": "龋齿", "confidence": 0.8,
                   "x1": 20, "y1": 30, "x2": 35, "y2": 50, "图像区域": "图像左侧下方区域", "关注等级": "重点关注"}]
    results = [{"model": "model-a", "model_path": "", "detections": detections,
                "class_names": {0: "Caries"}, "original": original, "model_input": input_image,
                "annotated": Image.new("RGB", (160, 80), "#ffaaaa")}]
    if compare:
        results.append({**results[0], "model": "model-b", "annotated": Image.new("RGB", (160, 80), "#aaffaa")})
    payload = {
        "case_id": "CASE-001", "note": "复查记录", "created_at": "2026-10-09T16:00:00",
        "patient_id": PERSONAL_PATIENT_ID, "task_id": task.id,
        "image_name": "fixture.png", "display_name": "病例影像",
        "quality_text": "图像质量正常", "quality_level": "一般",
        "summary": {"推理尺寸": 1280}, "suggestion": "请由口腔科医生复核。", "suggestion_type": "default",
        "model_results": [{"model": r["model"], "model_path": "", "detections": copy.deepcopy(detections)} for r in results],
    }
    return payload, {"patient_id": PERSONAL_PATIENT_ID, "task_id": task.id}, results


class CaseSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def save(self, **options):
        payload, item, results = snapshot_fixture(self.root, **options)
        saved = save_case_snapshot(self.root, "case_fixture.json", payload, item, results)
        return saved, results

    def asset_count(self):
        store = ensure_personal_workspace(self.root).store
        with sqlite3.connect(store.database_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM image_assets").fetchone()[0]

    def test_save_restart_restore_preserves_pixels_results_and_parameters(self):
        saved, results = self.save(compare=True, clahe=True)
        disk = load_case_record(self.root, "case_fixture.json", PERSONAL_PATIENT_ID)
        restored = load_case_snapshot(self.root, disk, PERSONAL_PATIENT_ID)
        self.assertEqual(saved, disk)
        self.assertEqual(len(restored["all_results"]), 2)
        self.assertEqual(restored["parameters"]["conf"], 0.34)
        self.assertEqual(restored["advice"], saved["suggestion"])
        for actual, expected in zip(restored["all_results"], results):
            for role in ("original", "model_input", "annotated"):
                self.assertEqual(actual[role].tobytes(), expected[role].tobytes())
                self.assertNotIn("patient_name", actual[role].info)
            self.assertEqual(actual["detections"], expected["detections"])
            self.assertEqual(actual["raw_detections"], expected["detections"])
            self.assertEqual(actual["review_status"], "unreviewed")
        self.assertEqual(self.asset_count(), 4)

    def test_original_and_unenhanced_input_explicitly_reuse_one_asset(self):
        saved, _ = self.save()
        self.assertEqual(saved["image_assets"]["model_input"], {"role": "model_input", "reuse_of": "original"})
        self.assertEqual(self.asset_count(), 2)
        for asset in saved["image_assets"].values():
            if "storage_key" in asset:
                self.assertFalse(Path(asset["storage_key"]).is_absolute())

    def test_data_root_move_keeps_images_and_existing_report_links_working(self):
        payload, item, results = snapshot_fixture(self.root)
        report = Path(self.root) / "reports" / "prior.docx"
        report.parent.mkdir(exist_ok=True)
        report.write_bytes(b"prior report")
        item["word_report_path"] = str(report)
        saved = save_case_snapshot(self.root, "case_fixture.json", payload, item, results)
        self.assertEqual(saved["word_report_path"], "reports/prior.docx")
        with TemporaryDirectory() as parent:
            moved = Path(parent) / "moved"
            shutil.copytree(self.root, moved)
            restored = load_case_snapshot(str(moved), saved, PERSONAL_PATIENT_ID)
            self.assertEqual(restored["word_report_path"], str(moved / "reports" / "prior.docx"))
            self.assertEqual(restored["result"]["original"].tobytes(), results[0]["original"].tobytes())

    def test_manifest_write_failure_rolls_back_database_and_files(self):
        payload, item, results = snapshot_fixture(self.root)
        real_write = Path.write_text

        def fail_manifest(path, *args, **kwargs):
            if path.suffix == ".pending":
                raise OSError("simulated disk full")
            return real_write(path, *args, **kwargs)

        with patch.object(Path, "write_text", fail_manifest):
            with self.assertRaisesRegex(OSError, "disk full"):
                save_case_snapshot(self.root, "case_fixture.json", payload, item, results)
        self.assertEqual(self.asset_count(), 0)
        self.assertEqual(list((Path(self.root) / "cases").glob("case_*.json")), [])
        self.assertEqual(list((Path(self.root) / "cases" / "assets").iterdir()), [])

    def test_publish_failure_rolls_back_already_moved_image_directory(self):
        payload, item, results = snapshot_fixture(self.root)
        real_rename = Path.rename

        def fail_publish(path, target):
            if path.suffix == ".pending":
                raise OSError("simulated publication failure")
            return real_rename(path, target)

        with patch.object(Path, "rename", fail_publish):
            with self.assertRaises(OSError):
                save_case_snapshot(self.root, "case_fixture.json", payload, item, results)
        self.assertEqual(self.asset_count(), 0)
        self.assertEqual(list((Path(self.root) / "cases" / "assets").iterdir()), [])

    def test_database_failure_leaves_no_case_or_assets(self):
        payload, item, results = snapshot_fixture(self.root)
        with patch.object(WorkspaceStore, "image_asset_transaction", side_effect=sqlite3.OperationalError("locked")):
            with self.assertRaises(sqlite3.Error):
                save_case_snapshot(self.root, "case_fixture.json", payload, item, results)
        self.assertEqual(self.asset_count(), 0)
        self.assertEqual(list((Path(self.root) / "cases" / "assets").iterdir()), [])

    def test_commit_failure_removes_published_manifest_and_rolls_back_assets(self):
        payload, item, results = snapshot_fixture(self.root)
        real_connection = WorkspaceStore._connection

        @contextmanager
        def fail_commit(store):
            with real_connection(store) as connection:
                yield connection
                if connection.execute("SELECT COUNT(*) FROM image_assets").fetchone()[0]:
                    raise sqlite3.OperationalError("simulated commit failure")

        with patch.object(WorkspaceStore, "_connection", fail_commit):
            with self.assertRaisesRegex(sqlite3.Error, "commit failure"):
                save_case_snapshot(self.root, "case_fixture.json", payload, item, results)
        self.assertEqual(self.asset_count(), 0)
        self.assertEqual(list((Path(self.root) / "cases").glob("case_*.json")), [])
        self.assertEqual(list((Path(self.root) / "cases" / "assets").iterdir()), [])

    def test_missing_corrupted_or_mismatched_assets_cannot_restore(self):
        saved, _ = self.save()
        asset = saved["image_assets"]["original"]
        path = Path(self.root) / asset["storage_key"]
        original = path.read_bytes()
        path.write_bytes(original + b"tampered")
        with self.assertRaisesRegex(ValueError, "完整性校验失败"):
            load_case_snapshot(self.root, saved, PERSONAL_PATIENT_ID)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            load_case_snapshot(self.root, saved, PERSONAL_PATIENT_ID)
        path.write_bytes(original)
        tampered = copy.deepcopy(saved)
        tampered["image_assets"]["original"]["storage_key"] = "../secret.png"
        with self.assertRaisesRegex(ValueError, "登记信息不一致"):
            load_case_snapshot(self.root, tampered, PERSONAL_PATIENT_ID)

    def test_patient_scope_and_asset_role_are_checked(self):
        saved, _ = self.save()
        other = create_personal_patient(self.root, "其他患者")
        with self.assertRaisesRegex(ValueError, "不属于当前患者"):
            load_case_snapshot(self.root, saved, other.id)
        saved["image_assets"]["model_input"]["role"] = "annotated"
        with self.assertRaisesRegex(ValueError, "角色不匹配"):
            load_case_snapshot(self.root, saved, PERSONAL_PATIENT_ID)

    def test_relabeling_annotation_as_original_cannot_bypass_asset_registration(self):
        saved, _ = self.save()
        saved["image_assets"]["annotated_0"]["role"] = "original"
        saved["model_results"][0]["original_asset"] = "annotated_0"
        with self.assertRaisesRegex(ValueError, "角色与数据库登记不一致"):
            load_case_snapshot(self.root, saved, PERSONAL_PATIENT_ID)

    def test_legacy_case_stays_readable_and_does_not_claim_recoverability(self):
        legacy = {"case_id": "旧病例", "detections": [], "note": "仍可阅读"}
        self.assertIn(LEGACY_CASE_MESSAGE, case_record_detail_html(legacy))
        with self.assertRaisesRegex(ValueError, LEGACY_CASE_MESSAGE):
            load_case_snapshot(self.root, legacy, PERSONAL_PATIENT_ID)

    def test_detail_preview_is_safe_and_reports_include_saved_images(self):
        saved, _ = self.save()
        detail = case_record_detail_html(case_snapshot_detail_data(self.root, saved))
        self.assertIn('class="case-image-review"', detail)
        self.assertIn("完整性校验通过", detail)
        self.assertIn('<dl class="record-meta-grid">', detail)
        self.assertIn("未经人工复核", detail)
        self.assertNotIn(self.root, detail)
        report = export_case_report(self.root, "case_fixture.json", PERSONAL_PATIENT_ID)
        with ZipFile(report) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("留存影像", xml)
            self.assertTrue(any(name.startswith("word/media/") for name in archive.namelist()))
            self.assertNotIn("不包含原始牙片图片", xml)

    def test_trashing_case_retains_recoverable_assets_and_hides_active_manifest(self):
        saved, _ = self.save()
        target = move_case_to_trash(self.root, "case_fixture.json", PERSONAL_PATIENT_ID)
        self.assertTrue(target.is_file())
        restored = load_case_snapshot(self.root, json.loads(target.read_text(encoding="utf-8")), PERSONAL_PATIENT_ID)
        self.assertIsNotNone(restored["result"]["annotated"])
        self.assertFalse((Path(self.root) / "cases" / "case_fixture.json").exists())

    def test_old_database_migrates_without_changing_existing_image_records(self):
        store = WorkspaceStore(self.root)
        store.workspace_dir.mkdir(parents=True)
        with sqlite3.connect(store.database_path) as connection:
            store._apply_schema_v1(connection)
            connection.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            connection.execute("INSERT INTO schema_migrations VALUES (1, 'old')")
            connection.execute("INSERT INTO users VALUES ('old-owner', 'old-owner', '旧用户', 'owner', 'old', 1)")
            connection.execute("INSERT INTO patients VALUES ('old-patient', 'old-owner', '旧患者', '', '', 'old', 'old', 0)")
            connection.execute("INSERT INTO detection_tasks VALUES ('old-task', 'old-owner', 'old-patient', 'succeeded', 'old-model', '{}', '{}', '', 'old', 'old', 'old')")
            connection.execute("INSERT INTO image_assets VALUES ('old-image', 'old-owner', 'old-patient', 'old-task', 'old.png', 'images/old.png', 'image/png', ?, 123, 160, 80, 1, 'old')", ("a" * 64,))
        store.initialize()
        self.assertEqual(store.schema_version(), SCHEMA_VERSION)
        with sqlite3.connect(store.database_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(image_assets)")}
        self.assertIn("asset_role", columns)
        image = store.get_image_asset("old-owner", "old-image")
        self.assertEqual(image.storage_key, "images/old.png")
        self.assertEqual(image.sha256, "a" * 64)
        self.assertEqual(image.asset_role, "original")

    def test_ui_reopen_restores_without_calling_inference(self):
        import app

        saved, results = self.save(compare=True, clahe=True)
        with patch.object(app, "run_inference", side_effect=AssertionError("must not run")):
            output = app.reopen_case_to_workbench("case_fixture.json", self.root, PERSONAL_PATIENT_ID, PERSONAL_PATIENT_ID, True)
        values = dict(zip(app.COMMON_OUTPUT_KEYS, output[1:1 + len(app.COMMON_OUTPUT_KEYS)]))
        self.assertEqual(values["result"].tobytes(), results[0]["annotated"].tobytes())
        self.assertEqual(values["quality"], saved["quality_text"])
        self.assertEqual(values["advice"], saved["suggestion"])
        self.assertEqual(len(values["batch_state"][0]["all_results"]), 2)
        self.assertTrue(app.case_reopen_button_state("case_fixture.json", self.root, PERSONAL_PATIENT_ID)["interactive"])
        self.assertEqual(output[4 + len(app.COMMON_OUTPUT_KEYS):6 + len(app.COMMON_OUTPUT_KEYS)], ("", ""))
        with self.assertRaises(app.gr.Error):
            app.reopen_case_to_workbench("case_fixture.json", self.root, PERSONAL_PATIENT_ID, "different", True)

    def test_ui_save_rejects_missing_task_and_different_selected_patient(self):
        import app

        payload, item, results = snapshot_fixture(self.root)
        state = [{**item, "name": "fixture.png", "result": results[0], "quality_text": payload["quality_text"]}]
        with self.assertRaises(app.gr.Error):
            app.save_case_record(state, "fixture.png", "case", "", self.root, "different")
        state[0]["task_id"] = ""
        with self.assertRaises(app.gr.Error):
            app.save_case_record(state, "fixture.png", "case", "", self.root)
        self.assertEqual(list((Path(self.root) / "cases").glob("case_*.json")), [])

    def test_resaving_after_report_creation_preserves_the_new_relationship(self):
        import app

        payload, item, results = snapshot_fixture(self.root)
        state = [{**item, "name": "fixture.png", "result": results[0], "quality_text": payload["quality_text"]}]
        first = app.save_case_record(state, "fixture.png", "case", "", self.root)
        report = Path(self.root) / "reports" / "new.docx"
        report.write_bytes(b"new report")
        state[0]["word_report_path"] = str(report)
        second = app.save_case_record(state, "fixture.png", "case", "", self.root)
        self.assertNotEqual(first[1]["value"], second[1]["value"])
        data = load_case_record(self.root, second[1]["value"], PERSONAL_PATIENT_ID)
        self.assertEqual(data["reports"]["word_report_path"]["storage_key"], "reports/new.docx")

    def test_resaving_cached_result_can_recover_from_missing_saved_image(self):
        import app

        payload, item, results = snapshot_fixture(self.root)
        state = [{**item, "name": "fixture.png", "result": results[0], "quality_text": payload["quality_text"]}]
        first = app.save_case_record(state, "fixture.png", "case", "", self.root)
        data = load_case_record(self.root, first[1]["value"], PERSONAL_PATIENT_ID)
        (Path(self.root) / data["image_assets"]["original"]["storage_key"]).unlink()
        second = app.save_case_record(state, "fixture.png", "case", "", self.root)
        self.assertNotEqual(first[1]["value"], second[1]["value"])
        self.assertTrue(app.case_reopen_button_state(second[1]["value"], self.root, PERSONAL_PATIENT_ID)["interactive"])

    def test_duplicate_check_rejects_malformed_model_results_without_crashing(self):
        payload, item, results = snapshot_fixture(self.root)
        saved = save_case_snapshot(self.root, "case_fixture.json", payload, item, results)
        self.assertTrue(reusable_case_snapshot(self.root, saved, payload, item))
        for value in (None, "damaged", {}, [], [None], ["damaged"]):
            with self.subTest(value=value):
                damaged = {**saved, "model_results": value}
                self.assertFalse(reusable_case_snapshot(self.root, damaged, payload, item))


if __name__ == "__main__":
    unittest.main()
