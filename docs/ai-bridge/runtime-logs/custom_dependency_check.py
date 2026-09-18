import json, sys
from pathlib import Path
root = Path.cwd()
yolov8_train = (root.parent / "yolov8-train").resolve()
result = {"yolov8_train": str(yolov8_train), "exists": yolov8_train.exists()}
try:
    sys.path.insert(0, str(yolov8_train))
    from ultralytics.nn.modules import C2fFasterLite
    result["from_ultralytics_nn_modules_C2fFasterLite"] = True
except Exception as exc:
    result["from_ultralytics_nn_modules_C2fFasterLite"] = False
    result["modules_error"] = repr(exc)
try:
    from ultralytics.nn.modules.dental_neck import FasterLiteBottleneck, C2fFasterLite as DentalC2fFasterLite
    result["from_dental_neck"] = True
except Exception as exc:
    result["from_dental_neck"] = False
    result["dental_neck_error"] = repr(exc)
try:
    from ultralytics import YOLO
    model = YOLO(str(root / "models" / "final_candidates" / "yolov8m_c2f_faster_lite_1280_full" / "weights" / "best.pt"))
    result["c2f_model_load"] = True
    result["names"] = getattr(model, "names", {})
except Exception as exc:
    result["c2f_model_load"] = False
    result["model_load_error"] = repr(exc)
print(json.dumps(result, ensure_ascii=False, indent=2))
