# AI Progress Log

## 2026-05-11

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
