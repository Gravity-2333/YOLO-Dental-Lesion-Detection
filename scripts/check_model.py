from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dental_detection.config import DEFAULT_MODEL_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a YOLO model file.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH))
    args = parser.parse_args()

    model_path = Path(args.model)
    model = YOLO(str(model_path))
    print(f"model: {model_path}")
    print(f"task: {model.task}")
    print(f"names: {model.names}")
    print("status: ok")


if __name__ == "__main__":
    main()
