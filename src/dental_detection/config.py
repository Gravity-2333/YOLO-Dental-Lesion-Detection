from .runtime_paths import CUSTOM_ULTRALYTICS_PATH, PROJECT_ROOT, WORKSPACE_ROOT

MODEL_REGISTRY = {
    "YOLOv8m 原始结构": {
        "path": PROJECT_ROOT
        / "models"
        / "final_candidates"
        / "yolov8m_1280_full"
        / "weights"
        / "best.pt",
        "role": "高精度候选",
        "architecture": "YOLOv8m",
        "metrics": {
            "test_mAP50": 0.6660,
            "test_mAP50_95": 0.3692,
            "params": "25.841M",
            "gflops": "314.780",
        },
    },
    "YOLOv8m C2f-Faster-lite": {
        "path": PROJECT_ROOT
        / "models"
        / "final_candidates"
        / "yolov8m_c2f_faster_lite_1280_full"
        / "weights"
        / "best.pt",
        "role": "优化结构候选",
        "architecture": "YOLOv8m + C2f-Faster-lite",
        "metrics": {
            "test_mAP50": 0.6491,
            "test_mAP50_95": 0.3804,
            "params": "20.690M",
            "gflops": "275.030",
        },
    },
}

DEFAULT_MODEL_NAME = "YOLOv8m C2f-Faster-lite"
DEFAULT_MODEL_PATH = MODEL_REGISTRY[DEFAULT_MODEL_NAME]["path"]
DEFAULT_EXAMPLE_IMAGE = PROJECT_ROOT / "assets" / "examples" / "bus.jpg"
