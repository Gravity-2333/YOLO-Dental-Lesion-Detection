from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dental_detection.config import DEFAULT_MODEL_PATH
from src.dental_detection.runtime_paths import ensure_project_ultralytics_path

ULTRALYTICS_SOURCE = ensure_project_ultralytics_path()

try:
    from ultralytics import YOLO
except ModuleNotFoundError as exc:
    raise SystemExit(
        "无法导入 ultralytics。请确认已安装 ultralytics，或项目同级目录存在 "
        "yolov8-train/ultralytics。"
    ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a YOLO model file.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH))
    args = parser.parse_args()

    model_path = Path(args.model)
    model = YOLO(str(model_path))
    print(f"model: {model_path}")
    print(f"ultralytics_source: {ULTRALYTICS_SOURCE or 'python environment'}")
    print(f"task: {model.task}")
    print(f"names: {model.names}")
    print("status: ok")


if __name__ == "__main__":
    main()
