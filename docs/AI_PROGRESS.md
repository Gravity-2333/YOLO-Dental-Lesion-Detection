# AI Progress Log

## 2026-05-11

### UI Localization

- Updated `app.py` so the Gradio page is displayed in Chinese.
- Localized the page title, upload panel, inference controls, run button, output labels, detection table headers, JSON summary keys, and empty-image error message.
- Verified UTF-8 file reading with `Get-Content -Encoding UTF8` after a PowerShell display-encoding warning.

### Gradio JSON Fix

- Fixed a Gradio output error caused by integer keys in the JSON summary.
- Converted class mapping keys from integers to strings before returning them to `gr.JSON`.

### Dataset Handling

- Inspected local `yolov8_dental/` training dataset.
- Dataset contains 664 `.png` images, 664 `.txt` YOLO labels, and is about 2.59 GB.
- Added `yolov8_dental/` to `.gitignore` because the raw dental image dataset is too large for normal Git history and may require privacy/licensing review before sharing.
- Keep dataset metadata/templates in the repository, but store raw images and labels locally or with a dataset-specific storage solution such as Git LFS, DVC, release assets, or controlled cloud storage.

### Completed

- Checked `models/dental_detect_12/weights/best.pt`.
  - The model loads successfully with Ultralytics.
  - Task: `detect`.
  - Classes: `Caries`, `Periapical Lesion`, `Impacted`.
- Organized the repository:
  - Dental trained model moved to `models/dental_detect_12/`.
  - Original pretrained-like weights moved to `models/pretrained/`.
  - Old COCO smoke-test `best.pt` moved under `experiments/legacy_coco_smoke/`.
  - Historical YOLO smoke-test outputs moved to `experiments/legacy_coco_smoke/`.
  - Example image moved to `assets/examples/`.
  - Legacy directory listing moved to `docs/legacy_tree.txt`.
- Added a Gradio prototype in `app.py`.
- Added reusable inference code in `src/dental_detection/`.
- Added model checking utility in `scripts/check_model.py`.
- Added dataset config template in `data/dental_lesion.yaml`.
- Added dependency list in `requirements.txt`.

### Current Model Notes

- Model path: `models/dental_detect_12/weights/best.pt`.
- Training source recorded in `models/dental_detect_12/args.yaml`.
- Best recorded validation row in `models/dental_detect_12/results.csv`:
  - epoch: 43
  - precision: 0.54402
  - recall: 0.59501
  - mAP50: 0.5594
  - mAP50-95: 0.3692

### Next Suggested Work

- Replace the temporary example image with real dental image samples that are safe to keep in the repository.
- Add batch prediction for folders.
- Add export support for ONNX/TensorRT after the Gradio prototype is stable.
- Add a validation script once the local dental dataset is available.

### GitHub Submission Draft

PR title:

```text
[codex] 搭建牙科YOLO检测Gradio原型
```

PR body:

```markdown
## 变更内容

- 新增 Gradio Web 原型，支持上传图片、调整置信度和 IoU，并输出标注图、检测表格和摘要信息。
- 新增 `src/dental_detection/` 推理模块，将模型加载、预测解析和标注绘制从界面代码中拆分出来。
- 整理项目结构，将牙科检测模型、预训练权重、历史实验输出、示例图片、文档和脚本分目录管理。
- 新增 `scripts/check_model.py`，用于快速检查 YOLO 权重是否能被 Ultralytics 正常加载。
- 新增 `docs/AI_PROGRESS.md`，记录 AI 后续协作过程、模型检查结果和项目进展。
- 新增 `data/dental_lesion.yaml` 数据集配置模板和 `requirements.txt` 依赖说明。

## 验证

- `mamba run -n yolo python scripts/check_model.py`
- 直接调用 `run_detection()` 完成一次 CPU 推理冒烟测试
- 启动 Gradio 服务并访问 `http://127.0.0.1:7860`，HTTP 状态码为 200

## 备注

- 当前默认模型为 `models/dental_detect_12/weights/best.pt`。
- 模型类别为 `Caries`、`Periapical Lesion`、`Impacted`。
- 本机未安装 GitHub CLI `gh`，因此 PR 需要通过 GitHub 页面手动创建。
```
