from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


TARGET_NAMES = {0: "Caries", 1: "Periapical_Lesion", 2: "Impacted"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
SPLITS = ("train", "val", "test")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class YoloBox:
    cls: int
    x: float
    y: float
    w: float
    h: float
    raw_class: str


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def map_coco_category(category_id_3: int, category_names: dict[int, str]) -> tuple[int | None, str]:
    raw = category_names.get(category_id_3, f"unknown_{category_id_3}")
    n = norm_name(raw)
    if n in {"caries", "deep_caries", "deep_carie"}:
        return 0, raw
    if n in {"periapical_lesion", "periapical_lesions"}:
        return 1, raw
    if n in {"impacted", "impacted_tooth", "impacted_teeth"}:
        return 2, raw
    return None, raw


def map_labelme_label(label: str) -> tuple[int | None, str]:
    parts = label.split("-")
    raw = parts[1] if len(parts) >= 2 else label
    token = raw.lower()
    if "çürük" in token or "curuk" in token or "caries" in token:
        return 0, raw
    if "lezyon" in token or "lesion" in token:
        return 1, raw
    if "gömülü" in token or "gomulu" in token or "impacted" in token:
        return 2, raw
    return None, raw


def clip_xyxy(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> tuple[float, float, float, float]:
    return max(0.0, x1), max(0.0, y1), min(float(width), x2), min(float(height), y2)


def xyxy_to_yolo(cls: int, x1: float, y1: float, x2: float, y2: float, width: int, height: int, raw_class: str) -> YoloBox | None:
    x1, y1, x2, y2 = clip_xyxy(x1, y1, x2, y2, width, height)
    bw = x2 - x1
    bh = y2 - y1
    if bw <= 0 or bh <= 0:
        return None
    return YoloBox(
        cls=cls,
        x=((x1 + x2) / 2) / width,
        y=((y1 + y2) / 2) / height,
        w=bw / width,
        h=bh / height,
        raw_class=raw_class,
    )


def discover_images(image_dir: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(image_dir.iterdir()) if p.is_file() and p.suffix.lower() in IMAGE_EXTS}


def prepare_output(output_root: Path, overwrite: bool) -> None:
    if output_root.exists():
        if not overwrite:
            raise FileExistsError(f"{output_root} already exists. Use --overwrite to rebuild it.")
        shutil.rmtree(output_root)
    for split in SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output_root / "preview").mkdir(parents=True, exist_ok=True)


def write_label(path: Path, boxes: list[YoloBox]) -> None:
    lines = [f"{b.cls} {b.x:.10f} {b.y:.10f} {b.w:.10f} {b.h:.10f}" for b in boxes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def convert_coco_split(
    *,
    split: str,
    json_path: Path,
    image_dir: Path,
    output_root: Path,
    report: dict,
) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    image_files = discover_images(image_dir)
    images = {img["id"]: img for img in data["images"]}
    category_names = {cat["id"]: cat["name"] for cat in data["categories_3"]}
    anns_by_image: dict[int, list[dict]] = defaultdict(list)
    for ann in data["annotations"]:
        anns_by_image[ann["image_id"]].append(ann)

    stats = report["splits"][split]
    stats["source_json"] = str(json_path)
    stats["source_images"] = str(image_dir)
    stats["json_images"] = len(data["images"])
    stats["source_image_files"] = len(image_files)
    stats["source_annotations"] = len(data["annotations"])
    stats["bbox_format"] = "COCO pixel xywh"

    for image_id, meta in sorted(images.items()):
        file_name = meta["file_name"]
        image_path = image_files.get(file_name)
        if image_path is None:
            report["missing_images"].append({"split": split, "image": file_name})
            continue

        width = int(meta["width"])
        height = int(meta["height"])
        boxes: list[YoloBox] = []
        for ann in anns_by_image.get(image_id, []):
            cls, raw = map_coco_category(int(ann["category_id_3"]), category_names)
            if cls is None:
                report["discarded_classes"][(split, raw)] += 1
                continue
            x, y, bw, bh = [float(v) for v in ann["bbox"]]
            severe = bw <= 0 or bh <= 0 or x >= width or y >= height or x + bw <= 0 or y + bh <= 0
            if x < 0 or y < 0 or x + bw > width or y + bh > height:
                report["clipped_bboxes"] += 1
            if severe:
                report["invalid_bboxes"].append({"split": split, "image": file_name, "bbox": ann["bbox"], "reason": "severe_coco_bbox"})
                continue
            box = xyxy_to_yolo(cls, x, y, x + bw, y + bh, width, height, raw)
            if box is None:
                report["invalid_bboxes"].append({"split": split, "image": file_name, "bbox": ann["bbox"], "reason": "zero_area_after_clip"})
                continue
            boxes.append(box)

        image_dst = output_root / "images" / split / file_name
        label_dst = output_root / "labels" / split / f"{Path(file_name).stem}.txt"
        shutil.copy2(image_path, image_dst)
        write_label(label_dst, boxes)
        update_stats(stats, boxes)


def convert_test_split(source_root: Path, output_root: Path, report: dict) -> None:
    split = "test"
    image_dir = source_root / "test" / "input"
    label_dir = source_root / "test" / "label"
    image_files = discover_images(image_dir)
    label_files = sorted(label_dir.glob("*.json"))
    used_images = set()

    stats = report["splits"][split]
    stats["source_json"] = str(label_dir)
    stats["source_images"] = str(image_dir)
    stats["json_images"] = len(label_files)
    stats["source_image_files"] = len(image_files)
    stats["source_annotations"] = 0
    stats["bbox_format"] = "LabelMe polygon -> external xyxy bbox"

    for json_path in label_files:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        file_name = data.get("imagePath") or f"{json_path.stem}.png"
        image_path = image_files.get(file_name)
        if image_path is None:
            report["missing_images"].append({"split": split, "image": file_name, "json": json_path.name})
            continue
        used_images.add(file_name)

        width = int(data.get("imageWidth") or Image.open(image_path).size[0])
        height = int(data.get("imageHeight") or Image.open(image_path).size[1])
        boxes: list[YoloBox] = []
        shapes = data.get("shapes", [])
        stats["source_annotations"] += len(shapes)
        for shape in shapes:
            label = str(shape.get("label", ""))
            cls, raw = map_labelme_label(label)
            if cls is None:
                report["discarded_classes"][(split, raw)] += 1
                continue
            points = shape.get("points") or []
            if len(points) < 2:
                report["invalid_bboxes"].append({"split": split, "image": file_name, "label": label, "reason": "too_few_polygon_points"})
                continue
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            severe = x2 <= 0 or y2 <= 0 or x1 >= width or y1 >= height
            if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
                report["clipped_bboxes"] += 1
            if severe:
                report["invalid_bboxes"].append({"split": split, "image": file_name, "label": label, "reason": "severe_polygon_bbox"})
                continue
            box = xyxy_to_yolo(cls, x1, y1, x2, y2, width, height, raw)
            if box is None:
                report["invalid_bboxes"].append({"split": split, "image": file_name, "label": label, "reason": "zero_area_after_clip"})
                continue
            boxes.append(box)

        image_dst = output_root / "images" / split / file_name
        label_dst = output_root / "labels" / split / f"{Path(file_name).stem}.txt"
        shutil.copy2(image_path, image_dst)
        write_label(label_dst, boxes)
        update_stats(stats, boxes)

    for file_name, image_path in image_files.items():
        if file_name in used_images:
            continue
        report["orphan_source_images"].append({"split": split, "image": file_name})


def update_stats(stats: dict, boxes: list[YoloBox]) -> None:
    stats["images"] += 1
    stats["labels"] += 1
    stats["boxes"] += len(boxes)
    if not boxes:
        stats["empty_labels"] += 1
    seen_classes = set()
    for box in boxes:
        stats["class_boxes"][box.cls] += 1
        seen_classes.add(box.cls)
    for cls in seen_classes:
        stats["class_images"][cls] += 1


def write_data_yaml(output_root: Path) -> None:
    text = f"""path: {output_root.as_posix()}
train: images/train
val: images/val
test: images/test

nc: 3
names:
  0: Caries
  1: Periapical_Lesion
  2: Impacted
"""
    (output_root / "data.yaml").write_text(text, encoding="utf-8")


CHECK_SCRIPT = r'''from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
NAMES = {0: "Caries", 1: "Periapical_Lesion", 2: "Impacted"}
COLORS = {0: (255, 80, 80), 1: (80, 220, 120), 2: (80, 150, 255)}


def find_images(path: Path):
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def parse_label(path: Path):
    boxes = []
    errors = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            errors.append((line_no, "not_5_columns", line))
            continue
        try:
            cls = int(float(parts[0]))
            x, y, w, h = [float(v) for v in parts[1:]]
        except ValueError:
            errors.append((line_no, "parse_error", line))
            continue
        if cls not in NAMES:
            errors.append((line_no, "class_not_0_1_2", line))
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            errors.append((line_no, "value_out_of_range", line))
        if x - w / 2 < -1e-9 or y - h / 2 < -1e-9 or x + w / 2 > 1 + 1e-9 or y + h / 2 > 1 + 1e-9:
            errors.append((line_no, "bbox_extends_outside_image", line))
        boxes.append((cls, x, y, w, h))
    return boxes, errors


def draw_preview(image_path: Path, label_path: Path, out_path: Path):
    image = ImageOps.exif_transpose(Image.open(image_path).convert("RGB"))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", max(14, image.width // 130))
    except Exception:
        font = ImageFont.load_default()
    boxes, _ = parse_label(label_path)
    width, height = image.size
    for cls, x, y, w, h in boxes:
        x1 = (x - w / 2) * width
        y1 = (y - h / 2) * height
        x2 = (x + w / 2) * width
        y2 = (y + h / 2) * height
        color = COLORS[cls]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=max(2, width // 500))
        draw.text((x1 + 3, y1 + 3), NAMES[cls], fill=color, font=font)
    image.thumbnail((1400, 900))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=92)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    dataset = args.dataset.resolve()
    errors = Counter()
    summary = {}
    for split in ("train", "val", "test"):
        image_dir = dataset / "images" / split
        label_dir = dataset / "labels" / split
        images = find_images(image_dir)
        labels = sorted(label_dir.glob("*.txt"))
        image_stems = {p.stem for p in images}
        label_stems = {p.stem for p in labels}
        missing = sorted(image_stems - label_stems)
        orphan = sorted(label_stems - image_stems)
        errors["missing_labels"] += len(missing)
        errors["orphan_labels"] += len(orphan)
        class_boxes = Counter()
        empty = 0
        rows = 0
        for label in labels:
            boxes, label_errors = parse_label(label)
            if not boxes:
                empty += 1
            for _, reason, _ in label_errors:
                errors[reason] += 1
            for cls, *_ in boxes:
                class_boxes[cls] += 1
            rows += len(boxes)
        summary[split] = {
            "images": len(images),
            "labels": len(labels),
            "boxes": rows,
            "empty_labels": empty,
            "class_boxes": dict(class_boxes),
        }
        if args.preview:
            positive = [img for img in images if (label_dir / f"{img.stem}.txt").read_text(encoding="utf-8", errors="ignore").strip()]
            sample = random.sample(positive, min(20, len(positive)))
            for idx, image_path in enumerate(sample):
                draw_preview(image_path, label_dir / f"{image_path.stem}.txt", dataset / "preview" / f"{split}_preview_20" / f"{idx:02d}_{image_path.stem}.jpg")

    print("summary:", summary)
    print("errors:", dict(errors))
    if any(errors.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
'''


def write_check_script(output_root: Path) -> None:
    (output_root / "check_yolo_dataset.py").write_text(CHECK_SCRIPT, encoding="utf-8")


def write_distribution_csv(output_root: Path, report: dict) -> None:
    with (output_root / "class_distribution.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "class_id", "class_name", "box_count", "image_count_with_class"])
        writer.writeheader()
        for split in SPLITS:
            stats = report["splits"][split]
            for cls, name in TARGET_NAMES.items():
                writer.writerow(
                    {
                        "split": split,
                        "class_id": cls,
                        "class_name": name,
                        "box_count": stats["class_boxes"][cls],
                        "image_count_with_class": stats["class_images"][cls],
                    }
                )


def write_discarded_csv(output_root: Path, report: dict) -> None:
    with (output_root / "discarded_classes.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "raw_class", "discarded_count"])
        writer.writeheader()
        for (split, raw_class), count in sorted(report["discarded_classes"].items()):
            writer.writerow({"split": split, "raw_class": raw_class, "discarded_count": count})


def render_report(source_root: Path, output_root: Path, report: dict) -> str:
    total_images = sum(report["splits"][s]["images"] for s in SPLITS)
    total_boxes = sum(report["splits"][s]["boxes"] for s in SPLITS)
    total_empty = sum(report["splits"][s]["empty_labels"] for s in SPLITS)
    lines = [
        "# DENTEX YOLOv8 3-Class Conversion Report",
        "",
        "## Source And Output",
        f"- Source root: `{source_root}`",
        f"- Output root: `{output_root}`",
        "- Original DENTEX files were not modified, moved, or deleted.",
        "- `training_data/quadrant` and `training_data/quadrant_enumeration` were intentionally not used.",
        "- Test split is converted for final evaluation only; it should not be used for training or hyperparameter tuning.",
        "",
        "## Format Inference",
        "- Train/val JSON is COCO-style with `images` and `annotations`; disease class is `category_id_3`.",
        "- Train/val bbox format is pixel `xywh`: `[x_min, y_min, width, height]`.",
        "- Test JSON is LabelMe polygon; all polygon points are converted to an external bbox.",
        "- Test labels were read as UTF-8. Mapping: `çürük -> Caries`, `lezyon -> Periapical_Lesion`, `gömülü -> Impacted`.",
        "- Empty labels are retained as YOLOv8-compatible negative samples after non-target classes are filtered.",
        "",
        "## Split Summary",
        "| split | images | labels | source annotations | target boxes | empty labels | Caries | Periapical_Lesion | Impacted |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for split in SPLITS:
        stats = report["splits"][split]
        lines.append(
            f"| {split} | {stats['images']} | {stats['labels']} | {stats['source_annotations']} | {stats['boxes']} | {stats['empty_labels']} | "
            f"{stats['class_boxes'][0]} | {stats['class_boxes'][1]} | {stats['class_boxes'][2]} |"
        )
    lines.extend(
        [
            "",
            "## Totals",
            f"- Total images: `{total_images}`",
            f"- Total labels: `{sum(report['splits'][s]['labels'] for s in SPLITS)}`",
            f"- Total target boxes: `{total_boxes}`",
            f"- Total empty labels: `{total_empty}`",
            "",
            "## Discarded Classes",
            "| split | raw class | count |",
            "| --- | --- | ---: |",
        ]
    )
    for (split, raw), count in sorted(report["discarded_classes"].items()):
        lines.append(f"| {split} | {raw} | {count} |")
    if not report["discarded_classes"]:
        lines.append("| all | none | 0 |")
    lines.extend(
        [
            "",
            "## Bbox And File Issues",
            f"- Missing source images: `{len(report['missing_images'])}`",
            f"- Orphan source test images: `{len(report['orphan_source_images'])}`",
            f"- Invalid/skipped bboxes: `{len(report['invalid_bboxes'])}`",
            f"- Clipped bboxes: `{report['clipped_bboxes']}`",
            "",
            "## Generated Files",
            "- `data.yaml`",
            "- `check_yolo_dataset.py`",
            "- `class_distribution.csv`",
            "- `discarded_classes.csv`",
            "- `preview/train_preview_20`, `preview/val_preview_20`, `preview/test_preview_20`",
            "",
            "## Minimal Smoke Training Command",
            "```powershell",
            f"yolo detect train model=yolov8n.pt data={output_root.as_posix()}/data.yaml imgsz=640 epochs=3 batch=8 workers=4",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(output_root: Path, source_root: Path, report: dict) -> None:
    (output_root / "convert_report.md").write_text(render_report(source_root, output_root, report), encoding="utf-8")


def new_report() -> dict:
    return {
        "splits": {
            split: {
                "images": 0,
                "labels": 0,
                "boxes": 0,
                "empty_labels": 0,
                "class_boxes": Counter(),
                "class_images": Counter(),
            }
            for split in SPLITS
        },
        "discarded_classes": Counter(),
        "missing_images": [],
        "orphan_source_images": [],
        "invalid_bboxes": [],
        "clipped_bboxes": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert DENTEX to a YOLOv8 3-class lesion detection dataset.")
    parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT / "data" / "raw" / "huggingface")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "transfer" / "dentex_yolov8_3cls")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    prepare_output(output_root, args.overwrite)
    report = new_report()

    convert_coco_split(
        split="train",
        json_path=source_root / "training_data" / "quadrant-enumeration-disease" / "train_quadrant_enumeration_disease.json",
        image_dir=source_root / "training_data" / "quadrant-enumeration-disease" / "xrays",
        output_root=output_root,
        report=report,
    )
    convert_coco_split(
        split="val",
        json_path=source_root / "validation_triple.json",
        image_dir=source_root / "validation_data" / "quadrant_enumeration_disease" / "xrays",
        output_root=output_root,
        report=report,
    )
    convert_test_split(source_root, output_root, report)

    write_data_yaml(output_root)
    write_check_script(output_root)
    write_distribution_csv(output_root, report)
    write_discarded_csv(output_root, report)
    write_report(output_root, source_root, report)

    serializable = {
        "splits": {
            split: {
                **{k: v for k, v in stats.items() if k not in {"class_boxes", "class_images"}},
                "class_boxes": dict(stats["class_boxes"]),
                "class_images": dict(stats["class_images"]),
            }
            for split, stats in report["splits"].items()
        },
        "discarded_classes": {f"{split}:{raw}": count for (split, raw), count in report["discarded_classes"].items()},
        "missing_images": report["missing_images"],
        "orphan_source_images": report["orphan_source_images"],
        "invalid_bboxes": report["invalid_bboxes"],
        "clipped_bboxes": report["clipped_bboxes"],
    }
    (output_root / "convert_summary.json").write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(serializable, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
