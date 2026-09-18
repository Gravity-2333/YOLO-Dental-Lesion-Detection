import json, platform, sys
from pathlib import Path
result = {"python_executable": sys.executable, "python_version": sys.version, "platform": platform.platform()}
modules = {}
for name, import_name in [("gradio", "gradio"), ("ultralytics", "ultralytics"), ("torch", "torch"), ("cv2", "cv2"), ("PIL", "PIL")]:
    try:
        mod = __import__(import_name)
        modules[name] = {"ok": True, "version": getattr(mod, "__version__", "unknown"), "file": getattr(mod, "__file__", "")}
    except Exception as exc:
        modules[name] = {"ok": False, "error": repr(exc)}
result["modules"] = modules
try:
    import torch
    result["cuda"] = {
        "available": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()),
        "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
    }
except Exception as exc:
    result["cuda"] = {"error": repr(exc)}
root = Path.cwd()
yolov8_train = (root.parent / "yolov8-train").resolve()
models = {
    "baseline": root / "models" / "final_candidates" / "yolov8m_1280_full" / "weights" / "best.pt",
    "c2f_faster_lite": root / "models" / "final_candidates" / "yolov8m_c2f_faster_lite_1280_full" / "weights" / "best.pt",
}
result["paths"] = {
    "project_root": str(root),
    "yolov8_train": str(yolov8_train),
    "yolov8_train_exists": yolov8_train.exists(),
    "models": {name: {"path": str(path), "exists": path.exists(), "size_mb": round(path.stat().st_size / 1024 / 1024, 2) if path.exists() else None} for name, path in models.items()},
}
custom = {"sys_path_inserted": str(yolov8_train)}
try:
    if yolov8_train.exists():
        sys.path.insert(0, str(yolov8_train))
    import ultralytics
    custom["ultralytics_file_after_insert"] = getattr(ultralytics, "__file__", "")
    from ultralytics.nn.modules.block import C2fFasterLite, FasterLiteBottleneck
    custom["C2fFasterLite_import"] = True
    custom["FasterLiteBottleneck_import"] = True
except Exception as exc:
    custom["custom_import_error"] = repr(exc)
result["custom_ultralytics"] = custom
print(json.dumps(result, ensure_ascii=False, indent=2))
