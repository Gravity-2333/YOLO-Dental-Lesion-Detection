"""测试脚本 - 检查潜在的bug和边界条件"""
import sys
import json
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
    "api.deepseek.com",
    "https://api.openai.com/v1",
    "http://localhost:8000",
    "127.0.0.1:5000",
    "https://api.example.com/v1/chat/completions",
]
for url in test_urls:
    try:
        normalized = normalize_base_url(url)
        print(f"✓ {url} -> {normalized}")
    except Exception as e:
        print(f"✗ {url} 规范化失败: {e}")

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
    model_a = {"model": "model-a", "model_path": "a.pt", "detections": detections_a, "original": image, "model_input": image, "annotated": image}
    model_b = {"model": "model-b", "model_path": "b.pt", "detections": detections_b, "original": image, "model_input": image, "annotated": image}
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
                    {"model": "model-a", "model_path": "a.pt", "detections": detections_a},
                    {"model": "model-b", "model_path": "b.pt", "detections": detections_b},
                ],
            ),
            Path(temp_dir) / "single_reports",
        )
        single_doc_text = "\n".join(
            cell.text for table in Document(single_report_path).tables for row in table.rows for cell in row.cells
        )
        assert "model-a" in single_doc_text and "model-b" in single_doc_text, "单图Word报告应保留两个模型明细"
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
    from app import MODEL_MODE_COMPARE, _configured_models, save_ui_settings, test_model_file

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

print("\n" + "="*60)
print("测试完成！")
