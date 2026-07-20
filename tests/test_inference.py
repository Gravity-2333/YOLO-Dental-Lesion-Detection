from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from time import sleep
from types import SimpleNamespace
import unittest

from PIL import Image

from src.dental_detection.inference import DentalDetector


class _FakeModel:
    def __init__(self) -> None:
        self.names = {0: "Caries"}
        self._state_lock = Lock()
        self.active = 0
        self.max_active = 0

    def predict(self, **_kwargs):
        with self._state_lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            sleep(0.03)
            return [SimpleNamespace(boxes=None)]
        finally:
            with self._state_lock:
                self.active -= 1


class InferenceSafetyTests(unittest.TestCase):
    def test_cached_detector_serializes_concurrent_predictions(self) -> None:
        detector = object.__new__(DentalDetector)
        detector.model_path = Path("fake.pt")
        detector.model = _FakeModel()
        detector.names = detector.model.names
        detector._predict_lock = Lock()
        image = Image.new("RGB", (16, 16), "white")

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(detector.predict, [image, image]))

        self.assertEqual(detector.model.max_active, 1)


if __name__ == "__main__":
    unittest.main()
