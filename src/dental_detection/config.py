from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "dental_detect_12" / "weights" / "best.pt"
DEFAULT_EXAMPLE_IMAGE = PROJECT_ROOT / "assets" / "examples" / "bus.jpg"
