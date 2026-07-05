"""测试脚本 - 检查潜在的bug和边界条件"""
import sys
import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

# 测试1: 检查导入
print("测试1: 检查模块导入...")
try:
    from src.dental_detection.assistant import (
        load_settings, normalize_base_url, default_advice,
        _normalize_class_name, CLASS_ADVICE
    )
    from src.dental_detection.inference import Detection
    from src.dental_detection.config import MODEL_REGISTRY, DEFAULT_MODEL_PATH
    from src.dental_detection.assistant import case_dir, ensure_app_dirs
    from src.dental_detection.case_store import list_case_records, load_case_record
    from src.dental_detection.history_store import append_history_records, history_rows, load_history_record
    from src.dental_detection.reporting import SingleReportData, export_batch_docx_report, export_single_docx_report
    from src.dental_detection.batch_summary import build_batch_summary
    from src.dental_detection.record_formatters import format_case_record
    print("✓ 模块导入成功")
except Exception as e:
    print(f"✗ 模块导入失败: {e}")
    sys.exit(1)

# 测试2: 检查配置加载
print("\n测试2: 检查配置加载...")
try:
    settings = load_settings()
    print(f"✓ 配置加载成功")
    print(f"  - Storage dir: {settings.storage_dir}")
    print(f"  - AI enabled: {settings.enabled}")
except Exception as e:
    print(f"✗ 配置加载失败: {e}")

# 测试3: 检查URL规范化
print("\n测试3: 检查URL规范化...")
test_urls = [
    ("api.deepseek.com", "https://api.deepseek.com/v1"),
    ("https://api.openai.com/v1", "https://api.openai.com/v1"),
    ("http://localhost:8000", "http://localhost:8000/v1"),
    ("127.0.0.1:5000", "http://127.0.0.1:5000/v1"),
    ("https://api.example.com/v1/chat/completions", "https://api.example.com/v1"),
    ("https://api.example.com/openai/v1/chat/completions", "https://api.example.com/openai/v1"),
]
for url, expected in test_urls:
    try:
        normalized = normalize_base_url(url)
        assert normalized == expected, f"期望 {expected}，实际 {normalized}"
        print(f"✓ {url} -> {normalized}")
    except Exception as e:
        print(f"✗ {url} 规范化失败: {e}")
        sys.exit(1)

# 测试4: 检查默认建议生成
print("\n测试4: 检查默认建议生成...")
test_detections = [
    [],  # 空检测
    [{"class": "Caries", "confidence": 0.85}],  # 单个检测
    [{"class": "Caries", "confidence": 0.85}, {"class": "Periapical_Lesion", "confidence": 0.72}],  # 多个检测
    [{"class": "Unknown", "confidence": 0.50}],  # 未知类别
]
for i, dets in enumerate(test_detections):
    try:
        advice = default_advice(dets)
        print(f"✓ 测试 {i+1}: 生成建议成功 ({len(advice)} 字符)")
        if i == 0:
            assert "未检测到" in advice, "空检测应包含'未检测到'"
    except Exception as e:
        print(f"✗ 测试 {i+1} 失败: {e}")

# 测试5: 检查类别名称规范化
print("\n测试5: 检查类别名称规范化...")
test_names = [
    ("Periapical_Lesion", "Periapical Lesion"),
    ("Caries", "Caries"),
    ("  Impacted  ", "Impacted"),
]
for original, expected in test_names:
    normalized = _normalize_class_name(original)
    if normalized == expected:
        print(f"✓ '{original}' -> '{normalized}'")
    else:
        print(f"✗ '{original}' -> '{normalized}' (期望: '{expected}')")

# 测试6: 检查模型注册表
print("\n测试6: 检查模型注册表...")
for model_name, model_info in MODEL_REGISTRY.items():
    model_path = Path(model_info["path"])
    if model_path.exists():
        print(f"✓ {model_name}: {model_path.name} 存在")
    else:
        print(f"✗ {model_name}: {model_path} 不存在")

# 测试7: 检查默认模型路径
print("\n测试7: 检查默认模型路径...")
if DEFAULT_MODEL_PATH.exists():
    print(f"✓ 默认模型存在: {DEFAULT_MODEL_PATH}")
else:
    print(f"✗ 默认模型不存在: {DEFAULT_MODEL_PATH}")

# 测试8: 检查Detection dataclass
print("\n测试8: 检查Detection数据类...")
try:
    det = Detection(
        cls_id=0,
        label="Caries",
        confidence=0.85,
        x1=100.0,
        y1=200.0,
        x2=300.0,
        y2=400.0
    )
    row = det.as_row()
    assert "class" in row
    assert "confidence" in row
    assert row["confidence"] == 0.85
    print(f"✓ Detection数据类正常工作")
    print(f"  - Row: {row}")
except Exception as e:
    print(f"✗ Detection数据类测试失败: {e}")

print("\n测试9: 检查空检测Word报告明细...")
try:
    from docx import Document
    from PIL import Image

    image = Image.new("RGB", (80, 60), "white")
    with TemporaryDirectory() as temp_dir:
        report_path = export_single_docx_report(
            SingleReportData(
                image_name="empty.png",
                created_at="2026-06-22T00:00:00",
                model_name="test-model",
                original_image=image,
                model_input_image=image,
                annotated_image=image,
                detections=[],
                advice="测试建议",
                quality_text="测试质量",
                summary={},
                safety_notice="测试声明",
            ),
            Path(temp_dir),
        )
        text = "\n".join(cell.text for table in Document(report_path).tables for row in table.rows for cell in row.cells)
        assert "未检测到目标框" in text, "空检测报告明细表应写明未检测到目标框"
    print("✓ 空检测Word报告明细正常")
except Exception as e:
    print(f"✗ 空检测Word报告测试失败: {e}")
    sys.exit(1)

print("\n测试10: 检查对比模型结果可追溯...")
try:
    from docx import Document
    from PIL import Image

    image = Image.new("RGB", (80, 60), "white")
    detections_a = [{"class": "Caries", "confidence": 0.81, "x1": 1, "y1": 2, "x2": 20, "y2": 30}]
    detections_b = [{"class": "Impacted", "confidence": 0.76, "x1": 10, "y1": 12, "x2": 40, "y2": 50}]
    model_a = {
        "model": "model-a",
        "model_path": "a.pt",
        "detections": detections_a,
        "original": image,
        "model_input": image,
        "annotated": image,
        "full_annotated": image,
    }
    model_b = {
        "model": "model-b",
        "model_path": "b.pt",
        "detections": detections_b,
        "original": image,
        "model_input": image,
        "annotated": image,
        "full_annotated": image,
    }
    batch_state = [
        {
            "name": "compare.png",
            "display_name": "001 - compare.png",
            "result": model_a,
            "all_results": [model_a, model_b],
            "advice": "测试建议",
            "quality_text": "测试质量",
            "quality_level": "良好",
            "summary": {"模型模式": "对比模型"},
        }
    ]
    with TemporaryDirectory() as temp_dir:
        append_history_records(batch_state, temp_dir, 100)
        rows = history_rows(temp_dir)
        record = load_history_record(rows[0]["记录ID"], temp_dir)
        assert record["detection_count"] == 2, "历史记录应统计两个模型的检测框"
        assert "model-a" in record["model"] and "model-b" in record["model"], "历史记录应保留两个模型名称"
        assert len(record.get("model_results", [])) == 2, "历史记录应保留模型结果明细"

        ensure_app_dirs(temp_dir)
        case_path = case_dir(temp_dir) / "case_20260622_compare.json"
        case_path.write_text(
            json.dumps(
                {
                    "created_at": "2026-06-22T00:00:00",
                    "case_id": "compare-case",
                    "image_name": "compare.png",
                    "summary": {},
                    "model_results": record["model_results"],
                    "detections": detections_a,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        case_rows = list_case_records(temp_dir)
        assert case_rows[0]["检测数量"] == 2, "病例列表应统计两个模型的检测框"
        loaded_case = load_case_record(temp_dir, case_rows[0]["文件名"])
        assert len(loaded_case["model_results"]) == 2, "病例记录应保留模型结果明细"
        case_detail = format_case_record(loaded_case)
        assert "model-b" in case_detail and "Impacted" in case_detail, "病例详情文本应显示副模型检测框"

        report_path = export_batch_docx_report(batch_state, None, Path(temp_dir) / "reports")
        doc_text = "\n".join(
            paragraph.text for paragraph in Document(report_path).paragraphs
        )
        assert "model-a" in doc_text and "model-b" in doc_text, "批量Word报告应写入两个模型名称"
        assert len(Document(report_path).inline_shapes) >= 3, "批量Word报告应包含主结果图和分模型结果图"

        single_report_path = export_single_docx_report(
            SingleReportData(
                image_name="compare.png",
                created_at="2026-06-22T00:00:00",
                model_name="model-a",
                original_image=image,
                model_input_image=image,
                annotated_image=image,
                detections=detections_a,
                advice="测试建议",
                quality_text="测试质量",
                summary={},
                safety_notice="测试声明",
                model_results=[
                    {"model": "model-a", "model_path": "a.pt", "detections": detections_a, "annotated": image},
                    {"model": "model-b", "model_path": "b.pt", "detections": detections_b, "annotated": image},
                ],
            ),
            Path(temp_dir) / "single_reports",
        )
        single_doc_text = "\n".join(
            cell.text for table in Document(single_report_path).tables for row in table.rows for cell in row.cells
        )
        assert "model-a" in single_doc_text and "model-b" in single_doc_text, "单图Word报告应保留两个模型明细"
        assert len(Document(single_report_path).inline_shapes) >= 5, "单图Word报告应包含每个模型的结果图"
    print("✓ 对比模型结果追溯正常")
except Exception as e:
    print(f"✗ 对比模型追溯测试失败: {e}")
    sys.exit(1)

print("\n测试11: 检查批量同名图片总览不合并...")
try:
    item_a = {
        "name": "same.png",
        "display_name": "001 - same.png",
        "result": {"detections": [{"class": "Caries", "confidence": 0.8}]},
    }
    item_b = {
        "name": "same.png",
        "display_name": "002 - same.png",
        "result": {"detections": [{"class": "Caries", "confidence": 0.7}]},
    }
    summary = build_batch_summary([item_a, item_b])
    caries = next(row for row in summary["类别统计"] if row["类别"] == "Caries")
    assert caries["涉及图片数"] == 2, "同名批量图片应按显示名区分，不能合并为1张"
    focus_names = [row["图片名称"] for row in summary["重点关注图片"]]
    assert "001 - same.png" in focus_names and "002 - same.png" in focus_names, "重点关注图片应显示唯一名称"
    print("✓ 批量同名图片总览正常")
except Exception as e:
    print(f"✗ 批量同名图片总览测试失败: {e}")
    sys.exit(1)

print("\n测试12: 检查对比模式禁止重复模型...")
try:
    from app import MODEL_MODE_COMPARE, _configured_models, _with_current_defaults, save_ui_settings, test_model_file
    from src.dental_detection.assistant import AiSettings, DEFAULT_AI_BASE_URL

    try:
        _configured_models(MODEL_MODE_COMPARE, str(DEFAULT_MODEL_PATH), str(DEFAULT_MODEL_PATH))
    except Exception as exc:
        assert "同一个权重文件" in str(exc), "重复模型应提示用户选择另一个模型"
    else:
        raise AssertionError("对比模式不应允许主模型和对比模型指向同一文件")

    message = test_model_file(str(DEFAULT_MODEL_PATH), str(DEFAULT_MODEL_PATH), MODEL_MODE_COMPARE)
    assert "同一个权重文件" in message, "测试模型按钮应直接提示重复模型，而不是泛化为加载失败"

    with TemporaryDirectory() as temp_dir:
        try:
            save_ui_settings(
                False,
                "https://api.deepseek.com/v1",
                "deepseek-chat",
                "环境变量",
                "DEEPSEEK_API_KEY",
                "",
                "",
                False,
                False,
                True,
                temp_dir,
                "",
                "简洁版",
                True,
                False,
                MODEL_MODE_COMPARE,
                "models",
                str(DEFAULT_MODEL_PATH),
                str(DEFAULT_MODEL_PATH),
                True,
                100,
            )
        except Exception as exc:
            assert "同一个权重文件" in str(exc), "保存设置也应拦截重复模型配置"
        else:
            raise AssertionError("保存设置不应接受重复模型对比配置")

    openai_settings = AiSettings(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        key_mode="环境变量",
        api_key="OPENAI_API_KEY",
    )
    preserved = _with_current_defaults(openai_settings, config_exists=True)
    assert preserved.base_url == "https://api.openai.com/v1", "已保存的 OpenAI 配置不应被迁移为 DeepSeek"

    old_default = AiSettings(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        key_mode="环境变量",
        api_key="OPENAI_API_KEY",
    )
    migrated = _with_current_defaults(old_default, config_exists=False)
    assert migrated.base_url == DEFAULT_AI_BASE_URL, "首次运行旧默认配置应迁移为当前默认服务"
    print("✓ 对比模式重复模型拦截正常")
except Exception as e:
    print(f"✗ 对比模式重复模型测试失败: {e}")
    sys.exit(1)

print("\n测试13: 检查切换图片保留已导出报告路径...")
try:
    from PIL import Image
    from app import select_batch_item

    image = Image.new("RGB", (80, 60), "white")
    item = {
        "name": "keep-path.png",
        "display_name": "001 - keep-path.png",
        "result": {
            "original": image,
            "model_input": image,
            "annotated": image,
            "table": [],
            "detections": [],
        },
        "advice": "测试建议",
        "quality_text": "测试质量",
        "summary": {},
        "word_report_path": r"C:\tmp\report.docx",
        "zip_report_path": r"C:\tmp\report.zip",
    }
    outputs = select_batch_item("001 - keep-path.png", [item], False)
    assert outputs[19] == r"C:\tmp\report.docx", "切换图片后应保留 Word 报告路径"
    assert outputs[22] == r"C:\tmp\report.zip", "切换图片后应保留 ZIP 报告路径"
    print("✓ 切换图片保留报告路径正常")
except Exception as e:
    print(f"✗ 切换图片报告路径测试失败: {e}")
    sys.exit(1)

print("\n测试14: 检查对比模型ZIP导出包含分模型结果图...")
try:
    from PIL import Image
    from app import export_batch_results, export_single_report

    image = Image.new("RGB", (80, 60), "white")
    model_a = {
        "model": "model-a",
        "model_path": "a.pt",
        "detections": [{"class": "Caries", "confidence": 0.81, "x1": 1, "y1": 2, "x2": 20, "y2": 30}],
        "original": image,
        "model_input": image,
        "annotated": image,
        "full_annotated": image,
    }
    model_b = {
        "model": "model-b",
        "model_path": "b.pt",
        "detections": [{"class": "Impacted", "confidence": 0.76, "x1": 10, "y1": 12, "x2": 40, "y2": 50}],
        "original": image,
        "model_input": image,
        "annotated": image,
        "full_annotated": image,
    }
    batch_state = [
        {
            "name": "compare.png",
            "display_name": "001 - compare.png",
            "result": model_a,
            "all_results": [model_a, model_b],
            "advice": "测试建议",
            "quality_text": "测试质量",
            "quality_level": "良好",
            "summary": {"模型模式": "对比模型"},
        }
    ]
    with TemporaryDirectory() as temp_dir:
        _, _, single_state = export_single_report(batch_state, "001 - compare.png", temp_dir)
        single_zip = Path(single_state[0]["zip_report_path"])
        with zipfile.ZipFile(single_zip) as archive:
            names = archive.namelist()
        assert any("model_01" in name and name.endswith("_result.png") for name in names), "单图ZIP应包含主模型结果图"
        assert any("model_02" in name and name.endswith("_result.png") for name in names), "单图ZIP应包含副模型结果图"

        _, _, batch_state = export_batch_results(batch_state, temp_dir)
        batch_zip = Path(batch_state[0]["zip_report_path"])
        with zipfile.ZipFile(batch_zip) as archive:
            names = archive.namelist()
        assert any("model_01" in name and name.endswith("_result.png") for name in names), "批量ZIP应包含主模型结果图"
        assert any("model_02" in name and name.endswith("_result.png") for name in names), "批量ZIP应包含副模型结果图"
    print("✓ 对比模型ZIP分模型结果图正常")
except Exception as e:
    print(f"✗ 对比模型ZIP分模型结果图测试失败: {e}")
    sys.exit(1)

print("\n测试15: 检查历史记录保留ZIP报告路径...")
try:
    from src.dental_detection.record_formatters import format_history_record

    with TemporaryDirectory() as temp_dir:
        item = {
            "name": "zip-only.png",
            "display_name": "001 - zip-only.png",
            "result": {"model": "model-a", "detections": []},
            "zip_report_path": r"C:\tmp\zip-only-report.zip",
        }
        append_history_records([item], temp_dir, 100)
        rows = history_rows(temp_dir)
        record = load_history_record(rows[0]["记录ID"], temp_dir)
        assert record["report_path"] == r"C:\tmp\zip-only-report.zip", "历史记录应在没有Word路径时保留ZIP报告路径"
        detail = format_history_record(record)
        assert r"C:\tmp\zip-only-report.zip" in detail, "历史详情应显示ZIP报告路径"

        latest_item = {
            "name": "latest-report.png",
            "display_name": "001 - latest-report.png",
            "result": {"model": "model-a", "detections": []},
            "word_report_path": r"C:\tmp\old-word-report.docx",
            "zip_report_path": r"C:\tmp\latest-report.zip",
            "report_path": r"C:\tmp\latest-report.zip",
        }
        append_history_records([latest_item], temp_dir, 100)
        latest_rows = history_rows(temp_dir)
        latest_record = load_history_record(latest_rows[0]["记录ID"], temp_dir)
        assert latest_record["report_path"] == r"C:\tmp\latest-report.zip", "历史记录应优先保留最近一次导出的报告路径"
    print("✓ 历史记录ZIP报告路径正常")
except Exception as e:
    print(f"✗ 历史记录ZIP报告路径测试失败: {e}")
    sys.exit(1)

print("\n测试16: 检查历史/病例兼容百分号置信度和中文字段...")
try:
    from src.dental_detection.result_levels import enrich_detection_row, parse_confidence

    assert parse_confidence("81%") == 0.81, "百分号置信度应转换为0-1小数"
    assert parse_confidence(81) == 0.81, "0-100置信度数值应转换为0-1小数"
    enriched = enrich_detection_row({"类别": "Periapical_Lesion", "置信度": "76%", "x1": 1, "y1": 2, "x2": 20, "y2": 30})
    assert enriched["class"] == "Periapical_Lesion", "中文类别字段应被识别"
    assert enriched["confidence"] == 0.76, "中文置信度字段应被识别"
    assert enriched["关注等级"] == "重点关注", "百分号置信度应参与关注等级判断"

    with TemporaryDirectory() as temp_dir:
        legacy_item = {
            "name": "legacy.png",
            "result": {
                "model": "legacy-model",
                "detections": [
                    {"类别": "Caries", "置信度": "81%", "x1": 1, "y1": 2, "x2": 20, "y2": 30},
                ],
            },
        }
        append_history_records([legacy_item], temp_dir, 100)
        rows = history_rows(temp_dir)
        assert rows[0]["最高置信度"] == "0.81", "历史表应正确显示百分号置信度"
        assert rows[0]["关注等级"] == "重点关注", "历史表应正确计算百分号关注等级"

        ensure_app_dirs(temp_dir)
        case_path = case_dir(temp_dir) / "case_20260622_legacy.json"
        case_path.write_text(
            json.dumps(
                {
                    "created_at": "2026-06-22T00:00:00",
                    "case_id": "legacy-case",
                    "image_name": "legacy.png",
                    "detections": [{"类别": "Impacted", "置信度": 76, "x1": 1, "y1": 2, "x2": 20, "y2": 30}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        case_rows = list_case_records(temp_dir)
        assert case_rows[0]["最高置信度"] == 0.76, "病例列表应正确统计0-100置信度"
        assert case_rows[0]["关注等级"] == "重点关注", "病例列表应正确计算0-100关注等级"
    print("✓ 百分号置信度和中文字段兼容正常")
except Exception as e:
    print(f"✗ 百分号置信度和中文字段兼容测试失败: {e}")
    sys.exit(1)

print("\n测试17: 检查病例记录兼容空模型明细回退顶层检测框...")
try:
    with TemporaryDirectory() as temp_dir:
        ensure_app_dirs(temp_dir)
        case_path = case_dir(temp_dir) / "case_20260705_fallback.json"
        case_path.write_text(
            json.dumps(
                {
                    "created_at": "2026-07-05T00:00:00",
                    "case_id": "fallback-case",
                    "image_name": "fallback.png",
                    "model_results": [{"model": "legacy-model", "detections": []}],
                    "detections": [{"class": "Caries", "confidence": 0.83, "x1": 1, "y1": 2, "x2": 20, "y2": 30}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        case_rows = list_case_records(temp_dir)
        assert case_rows[0]["检测数量"] == 1, "空模型明细不应掩盖顶层 detections"
        loaded_case = load_case_record(temp_dir, case_rows[0]["文件名"])
        detail = format_case_record(loaded_case)
        assert "Caries" in detail and "龋齿" in detail, "病例详情应回退显示顶层检测框"
    print("✓ 病例空模型明细兼容正常")
except Exception as e:
    print(f"✗ 病例空模型明细兼容测试失败: {e}")
    sys.exit(1)

print("\n测试18: 检查对比模型建议覆盖副模型检测框...")
try:
    from app import _advice_detections
    from src.dental_detection.assistant import default_advice

    merged = _advice_detections(
        [
            {"model": "model-a", "detections": []},
            {
                "model": "model-b",
                "detections": [{"class": "Impacted", "confidence": 0.82, "x1": 1, "y1": 2, "x2": 20, "y2": 30}],
            },
        ]
    )
    assert len(merged) == 1, "建议输入应包含副模型独有检测框"
    assert merged[0]["model"] == "model-b" and merged[0]["模型"] == "model-b", "建议输入应保留检测框来源模型"
    advice = default_advice(merged)
    assert "阻生牙" in advice, "默认建议应覆盖副模型检出的类别"
    print("✓ 对比模型建议覆盖副模型检测框正常")
except Exception as e:
    print(f"✗ 对比模型建议覆盖副模型检测框测试失败: {e}")
    sys.exit(1)

print("\n测试19: 检查批量摘要和默认建议兼容中文检测字段...")
try:
    chinese_detection = {"类别": "Periapical_Lesion", "置信度": "82%", "x1": 1, "y1": 2, "x2": 20, "y2": 30}
    summary = build_batch_summary(
        [
            {
                "name": "legacy-cn.png",
                "display_name": "001 - legacy-cn.png",
                "result": {"detections": [chinese_detection]},
            }
        ]
    )
    assert summary["检测框总数"] == 1, "中文字段检测框应参与批量统计"
    assert summary["最高置信度"] == 0.82, "中文置信度字段应参与最高置信度统计"
    assert summary["涉及类别"] == "根尖周病变", "中文字段类别应正确映射到显示名称"
    assert summary["重点关注图片"][0]["原始类别"] == "Periapical_Lesion", "重点关注图片应保留规范类别"
    advice = default_advice([chinese_detection])
    assert "根尖周" in advice and "0.82" in advice, "默认建议应兼容中文类别和百分号置信度"
    print("✓ 批量摘要和默认建议中文字段兼容正常")
except Exception as e:
    print(f"✗ 批量摘要和默认建议中文字段兼容测试失败: {e}")
    sys.exit(1)

print("\n测试20: 检查不存在的历史报告文件不会显示为可下载文件...")
try:
    from app import _file_component_output, _remember_allowed_file_root

    with TemporaryDirectory() as temp_dir:
        missing_path = Path(temp_dir) / "missing-report.docx"
        _remember_allowed_file_root(temp_dir)
        output = _file_component_output(missing_path)
        assert output["visible"] is False, "不存在的报告文件不应显示下载组件"
        assert output["value"] is None, "不存在的报告文件不应作为 File 组件值"
    print("✓ 不存在报告文件下载入口隐藏正常")
except Exception as e:
    print(f"✗ 不存在报告文件下载入口测试失败: {e}")
    sys.exit(1)

print("\n测试21: 检查受管目录迁移到自身子目录不递归搬动新目录...")
try:
    from src.dental_detection.assistant import migrate_storage

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        old_cases = root / "cases"
        old_cases.mkdir()
        (old_cases / "case_legacy.json").write_text("{}", encoding="utf-8")
        new_storage = old_cases / "nested_storage"
        migrate_storage(str(old_cases), str(new_storage))
        migrated_case = new_storage / "cases" / "case_legacy.json"
        recursive_target = new_storage / "cases" / "nested_storage"
        assert migrated_case.exists(), "旧 cases 根目录里的病例文件应迁入新存储目录的 cases 子目录"
        assert not recursive_target.exists(), "迁移时不应把新存储目录再搬进自身子目录"
    print("✓ 受管目录迁移到自身子目录正常")
except Exception as e:
    print(f"✗ 受管目录迁移测试失败: {e}")
    sys.exit(1)

print("\n测试22: 检查检测框标签贴边时不会越出图像...")
try:
    from PIL import Image
    from src.dental_detection.visualization import draw_detections_with_filter, label_box_layout

    left, top, right, bottom, text_x, text_y = label_box_layout(
        image_width=80,
        image_height=60,
        anchor_x=76,
        anchor_y=4,
        text_width=42,
        text_height=12,
    )
    assert 0 <= left <= right <= 79, "标签背景应被限制在图像宽度内"
    assert 0 <= top <= bottom <= 59, "标签背景应被限制在图像高度内"
    assert text_x >= left and text_y >= top, "文字起点应位于标签背景内部"

    image = Image.new("RGB", (80, 60), "white")
    annotated = draw_detections_with_filter(
        image,
        [{"class": "Caries", "confidence": 0.91, "x1": 76, "y1": 4, "x2": 79, "y2": 30}],
    )
    assert annotated.size == image.size, "重绘结果不应改变图像尺寸"
    print("✓ 检测框标签贴边布局正常")
except Exception as e:
    print(f"✗ 检测框标签贴边布局测试失败: {e}")
    sys.exit(1)

print("\n测试23: 检查模型文件不存在时优先提示路径缺失...")
try:
    from src.dental_detection.error_messages import friendly_error_message

    message = friendly_error_message("model file not found: C:/missing/best.pt", "模型文件不存在")
    assert "相关文件不存在" in message, "模型缺失应优先提示文件不存在，而不是泛化为加载失败"
    assert "模型文件无法加载" not in message, "缺失文件不应被误判为权重损坏"
    print("✓ 模型缺失错误提示正常")
except Exception as e:
    print(f"✗ 模型缺失错误提示测试失败: {e}")
    sys.exit(1)

print("\n测试24: 检查模型扫描包含 mlpackage 目录模型...")
try:
    from src.dental_detection.model_files import scan_model_files

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        package = root / "exported_model.mlpackage"
        package.mkdir()
        choices = scan_model_files(root)
        assert any(Path(value).name == "exported_model.mlpackage" for _, value in choices), (
            "扫描模型目录时应把 .mlpackage 目录作为可选模型"
        )

        direct_choices = scan_model_files(package)
        assert len(direct_choices) == 1 and Path(direct_choices[0][1]).name == "exported_model.mlpackage", (
            "直接选择 .mlpackage 目录时应返回该模型"
        )
    print("✓ mlpackage 目录模型扫描正常")
except Exception as e:
    print(f"✗ mlpackage 目录模型扫描测试失败: {e}")
    sys.exit(1)

print("\n测试25: 检查示例图片加载后不依赖未关闭文件句柄...")
try:
    from app import EXAMPLE_DIR, load_demo_example

    example_path = next(EXAMPLE_DIR.glob("*.png"))
    image, info = load_demo_example(str(example_path))
    assert image.mode == "RGB", "示例图片应加载为 RGB"
    assert image.size[0] > 0 and image.size[1] > 0, "示例图片尺寸应有效"
    assert str(info).strip(), "示例图片应返回说明文本"
    with TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "example_copy.png"
        image.save(output_path)
        assert output_path.exists(), "示例图片对象应可独立保存，不依赖打开的源文件"
    print("✓ 示例图片加载句柄处理正常")
except Exception as e:
    print(f"✗ 示例图片加载测试失败: {e}")
    sys.exit(1)

print("\n测试26: 检查未选择历史记录时删除提示不会覆盖详情...")
try:
    from app import delete_selected_history_record

    with TemporaryDirectory() as temp_dir:
        _, _, detail, feedback = delete_selected_history_record("", temp_dir)
        assert "请选择一条检测历史" in detail, "未选择时历史详情应保持正常空状态"
        assert "请选择要删除的历史记录" in feedback, "未选择删除应把提示放在反馈区域"
    print("✓ 历史删除空选择提示正常")
except Exception as e:
    print(f"✗ 历史删除空选择提示测试失败: {e}")
    sys.exit(1)

print("\n测试27: 检查空模型明细不会掩盖主结果检测框...")
try:
    from docx import Document
    from PIL import Image
    from app import _item_results, export_batch_results
    from src.dental_detection.record_formatters import format_history_record

    image = Image.new("RGB", (80, 60), "white")
    primary = {
        "model": "primary-model",
        "model_path": "primary.pt",
        "detections": [{"class": "Caries", "confidence": 0.84, "x1": 1, "y1": 2, "x2": 20, "y2": 30}],
        "original": image,
        "model_input": image,
        "annotated": image,
        "full_annotated": image,
        "table": [],
    }
    item = {
        "name": "stale-results.png",
        "display_name": "001 - stale-results.png",
        "result": primary,
        "all_results": [{"model": "stale-empty-model", "detections": []}],
        "advice": "测试建议",
        "quality_text": "测试质量",
        "quality_level": "良好",
        "summary": {"模型模式": "单模型"},
    }
    assert _item_results(item)[0]["model"] == "primary-model", "空 all_results 不应掩盖主结果"
    summary = build_batch_summary([item])
    assert summary["检测框总数"] == 1, "批量摘要应回退统计主结果检测框"
    with TemporaryDirectory() as temp_dir:
        append_history_records([item], temp_dir, 100)
        rows = history_rows(temp_dir)
        record = load_history_record(rows[0]["记录ID"], temp_dir)
        assert record["detection_count"] == 1, "历史记录应回退保存主结果检测框"
        assert "龋齿" in format_history_record(record), "历史详情应显示主结果检测框"

        report_path = export_batch_docx_report([item], summary, Path(temp_dir) / "word")
        doc = Document(report_path)
        doc_text = "\n".join(
            [paragraph.text for paragraph in doc.paragraphs]
            + [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
        )
        assert "primary-model" in doc_text and "Caries" in doc_text, "批量 Word 应回退显示主结果检测框"

        _, _, exported_state = export_batch_results([item], temp_dir)
        batch_zip = Path(exported_state[0]["zip_report_path"])
        with zipfile.ZipFile(batch_zip) as archive:
            detections_json = json.loads(archive.read("detections.json").decode("utf-8"))
        exported_item = detections_json["items"][0]
        assert exported_item["models"][0]["model"] == "primary-model", "批量 ZIP 应回退主模型名称"
        assert exported_item["models"][0]["detections"][0]["class"] == "Caries", "批量 ZIP 应回退主检测框"
    print("✓ 空模型明细回退主结果正常")
except Exception as e:
    print(f"✗ 空模型明细回退主结果测试失败: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("测试完成！")
