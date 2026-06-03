from __future__ import annotations

import argparse
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


SOURCE_CLASS_NAMES = {
    0: "Caries",
    1: "Crown",
    2: "Filling",
    3: "Implant",
    4: "Malaligned",
    5: "Mandibular Canal",
    6: "Missing teeth",
    7: "Periapical lesion",
    8: "Retained root",
    9: "Root Canal Treatment",
    10: "Root Piece",
    11: "impacted tooth",
    12: "maxillary sinus",
    13: "Bone Loss",
    14: "Fracture teeth",
    15: "Permanent Teeth",
    16: "Supra Eruption",
    17: "TAD",
    18: "abutment",
    19: "attrition",
    20: "bone defect",
    21: "gingival former",
    22: "metal band",
    23: "orthodontic brackets",
    24: "permanent retainer",
    25: "post - core",
    26: "plating",
    27: "wire",
    28: "Cyst",
    29: "Root resorption",
    30: "Primary teeth",
}

CLASS_MAP = {0: 0, 7: 1, 11: 2}
TARGET_CLASS_NAMES = {0: "Caries", 1: "Periapical Lesion", 2: "Impacted"}
SPLITS = ("train", "valid", "test")
TARGET_SPLITS = ("train", "val", "test")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BoxRecord:
    cls: int
    x: float
    y: float
    w: float
    h: float


@dataclass
class ImageRecord:
    source_split: str
    image_path: Path
    label_path: Path
    original_id: str
    boxes: list[BoxRecord] = field(default_factory=list)


def original_id_from_stem(stem: str) -> str:
    return stem.split(".rf.")[0]


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = (len(ordered) - 1) * pct / 100
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - idx) + ordered[hi] * (idx - lo)


def parse_label_line(parts: list[str], skip_reasons: Counter, context: str) -> tuple[int, float, float, float, float, str] | None:
    if len(parts) < 5:
        skip_reasons["too_few_fields"] += 1
        return None
    try:
        cls = int(float(parts[0]))
        coords = [float(v) for v in parts[1:]]
    except ValueError:
        skip_reasons["parse_error"] += 1
        return None

    if len(coords) == 4:
        x, y, w, h = coords
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            skip_reasons["bbox_value_out_of_range"] += 1
            return None
        if x - w / 2 < 0 or y - h / 2 < 0 or x + w / 2 > 1 or y + h / 2 > 1:
            skip_reasons["bbox_extends_outside_image"] += 1
            return None
        return cls, x, y, w, h, "bbox"

    if len(coords) % 2 != 0:
        skip_reasons["polygon_odd_coordinate_count"] += 1
        return None
    if len(coords) < 6:
        skip_reasons["polygon_too_few_points"] += 1
        return None

    raw_xs = coords[0::2]
    raw_ys = coords[1::2]
    # 检测坐标是否超出 [0,1] 归一化范围（可能是像素坐标误当作归一化坐标）
    if any(v < -0.01 or v > 1.01 for v in raw_xs + raw_ys):
        skip_reasons["polygon_coordinate_out_of_normalized_range"] += 1
    xs = [clamp01(v) for v in raw_xs]
    ys = [clamp01(v) for v in raw_ys]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        skip_reasons["polygon_zero_area_after_clip"] += 1
        return None
    return cls, (x1 + x2) / 2, (y1 + y2) / 2, w, h, "polygon"


def read_source_dataset(source_root: Path):
    audit = {
        "source_root": str(source_root.resolve()),
        "source_yaml": "",
        "split_stats": {},
        "format_counts": Counter(),
        "class_instances": Counter(),
        "class_images": Counter(),
        "class_instances_by_split": {split: Counter() for split in SPLITS},
        "areas": [],
        "widths": [],
        "heights": [],
        "missing_labels": [],
        "orphan_labels": [],
        "empty_labels": [],
        "invalid_reasons": Counter(),
        "invalid_examples": [],
        "source_leaks": {},
    }
    yaml_path = source_root / "data.yaml"
    if yaml_path.exists():
        audit["source_yaml"] = yaml_path.read_text(encoding="utf-8", errors="ignore")

    all_images: list[ImageRecord] = []
    source_original_splits: dict[str, set[str]] = defaultdict(set)

    for split in SPLITS:
        image_dir = source_root / split / "images"
        label_dir = source_root / split / "labels"
        images = sorted(p for p in image_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
        labels = sorted(p for p in label_dir.rglob("*.txt") if p.is_file())
        image_stems = {p.stem for p in images}
        label_stems = {p.stem for p in labels}
        missing = sorted(image_stems - label_stems)
        orphan = sorted(label_stems - image_stems)
        audit["missing_labels"].extend((split, stem) for stem in missing)
        audit["orphan_labels"].extend((split, stem) for stem in orphan)

        instance_count = 0
        for image_path in images:
            original_id = original_id_from_stem(image_path.stem)
            source_original_splits[original_id].add(split)
            label_path = label_dir / f"{image_path.stem}.txt"
            selected_boxes: list[BoxRecord] = []
            image_classes = set()

            if not label_path.exists():
                all_images.append(ImageRecord(split, image_path, label_path, original_id, selected_boxes))
                continue

            text = label_path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                audit["empty_labels"].append((split, image_path.stem))
                all_images.append(ImageRecord(split, image_path, label_path, original_id, selected_boxes))
                continue

            for line_no, line in enumerate(text.splitlines(), 1):
                parsed = parse_label_line(line.split(), audit["invalid_reasons"], f"{label_path}:{line_no}")
                if parsed is None:
                    if len(audit["invalid_examples"]) < 30:
                        audit["invalid_examples"].append((split, label_path.name, line_no, line[:140]))
                    continue
                cls, x, y, w, h, fmt = parsed
                audit["format_counts"][fmt] += 1
                audit["areas"].append(w * h)
                audit["widths"].append(w)
                audit["heights"].append(h)
                audit["class_instances"][cls] += 1
                audit["class_instances_by_split"][split][cls] += 1
                image_classes.add(cls)
                instance_count += 1
                if cls in CLASS_MAP:
                    selected_boxes.append(BoxRecord(CLASS_MAP[cls], x, y, w, h))

            for cls in image_classes:
                audit["class_images"][cls] += 1
            all_images.append(ImageRecord(split, image_path, label_path, original_id, selected_boxes))

        audit["split_stats"][split] = {
            "images": len(images),
            "labels": len(labels),
            "instances": instance_count,
            "missing_labels": len(missing),
            "orphan_labels": len(orphan),
            "empty_labels": sum(1 for s, _ in audit["empty_labels"] if s == split),
        }

    audit["source_leaks"] = {
        original_id: sorted(splits) for original_id, splits in source_original_splits.items() if len(splits) > 1
    }
    return all_images, audit


def split_groups(records: list[ImageRecord], ratios: dict[str, float], seed: int):
    groups: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        groups[record.original_id].append(record)

    group_items = []
    for original_id, items in groups.items():
        class_counts = Counter()
        class_images = Counter()
        for item in items:
            image_classes = {box.cls for box in item.boxes}
            class_images.update(image_classes)
            class_counts.update(box.cls for box in item.boxes)
        group_items.append(
            {
                "original_id": original_id,
                "items": items,
                "images": len(items),
                "instances": sum(class_counts.values()),
                "class_counts": class_counts,
                "class_images": class_images,
            }
        )

    rng = random.Random(seed)
    rng.shuffle(group_items)
    group_items.sort(key=lambda g: (g["instances"], max(g["class_counts"].values() or [0]), g["images"]), reverse=True)

    total_images = sum(g["images"] for g in group_items)
    total_instances = sum(g["instances"] for g in group_items)
    total_class_counts = Counter()
    for group in group_items:
        total_class_counts.update(group["class_counts"])

    targets = {
        split: {
            "images": total_images * ratio,
            "instances": total_instances * ratio,
            "class_counts": Counter({cls: total_class_counts[cls] * ratio for cls in TARGET_CLASS_NAMES}),
        }
        for split, ratio in ratios.items()
    }

    assigned = {split: [] for split in ratios}
    running = {
        split: {"images": 0, "instances": 0, "class_counts": Counter()} for split in ratios
    }

    def score(candidate_split: str, group) -> float:
        total_error = 0.0
        for split in ratios:
            after_images = running[split]["images"]
            after_instances = running[split]["instances"]
            after_classes = running[split]["class_counts"].copy()
            if split == candidate_split:
                after_images += group["images"]
                after_instances += group["instances"]
                after_classes.update(group["class_counts"])

            image_error = ((after_images - targets[split]["images"]) / max(1, total_images)) ** 2
            instance_error = ((after_instances - targets[split]["instances"]) / max(1, total_instances)) ** 2
            class_error = 0.0
            for cls in TARGET_CLASS_NAMES:
                denom = max(1.0, float(total_class_counts[cls]))
                class_error += ((after_classes[cls] - targets[split]["class_counts"][cls]) / denom) ** 2
            total_error += class_error * 6.0 + instance_error * 2.0 + image_error
        return total_error

    for group in group_items:
        split = min(ratios, key=lambda name: (score(name, group), running[name]["images"]))
        assigned[split].extend(group["items"])
        running[split]["images"] += group["images"]
        running[split]["instances"] += group["instances"]
        running[split]["class_counts"].update(group["class_counts"])

    return assigned


def clean_output_root(output_root: Path, overwrite: bool) -> None:
    if output_root.exists():
        if not overwrite:
            raise FileExistsError(f"Output root already exists: {output_root}. Use --overwrite to replace it.")
        shutil.rmtree(output_root)
    for split in TARGET_SPLITS:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)


def write_dataset(assigned: dict[str, list[ImageRecord]], output_root: Path, overwrite: bool):
    clean_output_root(output_root, overwrite)
    written = {split: [] for split in TARGET_SPLITS}
    collisions = 0

    for split, records in assigned.items():
        for record in records:
            image_dst = output_root / "images" / split / record.image_path.name
            label_dst = output_root / "labels" / split / f"{record.image_path.stem}.txt"
            if image_dst.exists() or label_dst.exists():
                collisions += 1
                image_dst = output_root / "images" / split / f"{record.source_split}__{record.image_path.name}"
                label_dst = output_root / "labels" / split / f"{record.source_split}__{record.image_path.stem}.txt"
            shutil.copy2(record.image_path, image_dst)
            lines = [
                f"{box.cls} {box.x:.10f} {box.y:.10f} {box.w:.10f} {box.h:.10f}"
                for box in record.boxes
            ]
            label_dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
            written[split].append((image_dst, label_dst))
    return written, collisions


def summarize_records(records: list[ImageRecord]) -> dict:
    class_instances = Counter()
    class_images = Counter()
    for record in records:
        image_classes = {box.cls for box in record.boxes}
        class_images.update(image_classes)
        class_instances.update(box.cls for box in record.boxes)
    total_instances = sum(class_instances.values())
    return {
        "images": len(records),
        "instances": total_instances,
        "class_instances": dict(class_instances),
        "class_images": dict(class_images),
        "class_instance_ratio": {
            cls: (class_instances[cls] / total_instances if total_instances else 0.0) for cls in TARGET_CLASS_NAMES
        },
    }


def verify_output(output_root: Path) -> dict:
    result = {
        "split_stats": {},
        "invalid_reasons": Counter(),
        "missing_labels": [],
        "orphan_labels": [],
        "leaks": {},
    }
    original_splits: dict[str, set[str]] = defaultdict(set)

    for split in TARGET_SPLITS:
        image_dir = output_root / "images" / split
        label_dir = output_root / "labels" / split
        images = sorted(p for p in image_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
        labels = sorted(p for p in label_dir.rglob("*.txt") if p.is_file())
        image_stems = {p.stem for p in images}
        label_stems = {p.stem for p in labels}
        result["missing_labels"].extend((split, stem) for stem in sorted(image_stems - label_stems))
        result["orphan_labels"].extend((split, stem) for stem in sorted(label_stems - image_stems))

        class_instances = Counter()
        class_images = Counter()
        instances = 0
        for image_path in images:
            original_splits[original_id_from_stem(image_path.stem)].add(split)
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                continue
            image_classes = set()
            for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    result["invalid_reasons"]["not_5_columns"] += 1
                    continue
                try:
                    cls = int(float(parts[0]))
                    x, y, w, h = [float(v) for v in parts[1:]]
                except ValueError:
                    result["invalid_reasons"]["parse_error"] += 1
                    continue
                if cls not in TARGET_CLASS_NAMES:
                    result["invalid_reasons"]["class_not_0_1_2"] += 1
                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    result["invalid_reasons"]["bbox_value_out_of_range"] += 1
                if x - w / 2 < -1e-9 or y - h / 2 < -1e-9 or x + w / 2 > 1 + 1e-9 or y + h / 2 > 1 + 1e-9:
                    result["invalid_reasons"]["bbox_extends_outside_image"] += 1
                instances += 1
                class_instances[cls] += 1
                image_classes.add(cls)
            class_images.update(image_classes)

        result["split_stats"][split] = {
            "images": len(images),
            "labels": len(labels),
            "instances": instances,
            "class_instances": dict(class_instances),
            "class_images": dict(class_images),
        }

    result["leaks"] = {oid: sorted(splits) for oid, splits in original_splits.items() if len(splits) > 1}
    return result


def table_row(values) -> str:
    return "| " + " | ".join(str(v) for v in values) + " |"


def render_report(audit: dict, filtered_records: list[ImageRecord], split_summary: dict, verification: dict, output_root: Path, collisions: int) -> str:
    total_source_images = sum(v["images"] for v in audit["split_stats"].values())
    dropped_images = total_source_images - len(filtered_records)
    dropped_pct = dropped_images / total_source_images * 100 if total_source_images else 0
    areas = audit["areas"]

    lines = [
        "# Dataset Audit Report",
        "",
        "## Source",
        f"- Source root: `{audit['source_root']}`",
        f"- Generated output root: `{output_root.resolve()}`",
        "- Original `data.yaml` issue: source paths point to `/home/loki/DentalObjectDetection/data/YOLO/...`, and `test` points to `valid/images`.",
        "- Training was not run.",
        "",
        "## Source Split Summary",
        table_row(["split", "images", "labels", "instances", "missing labels", "orphan labels", "empty labels"]),
        table_row(["---", "---:", "---:", "---:", "---:", "---:", "---:"]),
    ]
    for split in SPLITS:
        stats = audit["split_stats"][split]
        lines.append(table_row([split, stats["images"], stats["labels"], stats["instances"], stats["missing_labels"], stats["orphan_labels"], stats["empty_labels"]]))

    lines.extend([
        "",
        "## Source Class Summary",
        table_row(["id", "name", "instances", "images", "train inst", "valid inst", "test inst"]),
        table_row(["---:", "---", "---:", "---:", "---:", "---:", "---:"]),
    ])
    for cls in range(31):
        lines.append(
            table_row(
                [
                    cls,
                    SOURCE_CLASS_NAMES[cls],
                    audit["class_instances"][cls],
                    audit["class_images"][cls],
                    audit["class_instances_by_split"]["train"][cls],
                    audit["class_instances_by_split"]["valid"][cls],
                    audit["class_instances_by_split"]["test"][cls],
                ]
            )
        )

    lines.extend([
        "",
        "## Label Geometry",
        f"- Parsed bbox labels: {audit['format_counts']['bbox']}",
        f"- Parsed polygon labels: {audit['format_counts']['polygon']}",
        f"- Invalid/skipped source annotations: {sum(audit['invalid_reasons'].values())}",
        f"- Invalid reason counts: `{dict(audit['invalid_reasons'])}`",
        "",
        "### Bbox Area Distribution",
        table_row(["metric", "value"]),
        table_row(["---", "---:"]),
    ])
    for pct in [0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100]:
        value = percentile(areas, pct)
        lines.append(table_row([f"P{pct}", f"{value:.10f}" if value is not None else "n/a"]))
    lines.extend(["", "### Small Target Ratio", table_row(["area threshold", "count", "ratio"]), table_row(["---:", "---:", "---:"])])
    for threshold in [0.001, 0.0025, 0.005, 0.01, 0.02, 0.05]:
        count = sum(1 for area in areas if area < threshold)
        ratio = count / len(areas) * 100 if areas else 0
        lines.append(table_row([threshold, count, f"{ratio:.2f}%"]))

    lines.extend([
        "",
        "## Source Leakage",
        f"- Potential original_id leaks across source train/valid/test: {len(audit['source_leaks'])}",
    ])
    for original_id, splits in list(audit["source_leaks"].items())[:20]:
        lines.append(f"- `{original_id}`: {', '.join(splits)}")

    lines.extend([
        "",
        "## Filtered Dataset",
        f"- Kept images with target classes: {len(filtered_records)}",
        f"- Dropped images without Caries / Periapical lesion / impacted tooth: {dropped_images} ({dropped_pct:.2f}%)",
        f"- Filename collisions while copying: {collisions}",
        "",
        table_row(["split", "images", "instances", "Caries inst", "Periapical inst", "Impacted inst", "Caries img", "Periapical img", "Impacted img"]),
        table_row(["---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"]),
    ])
    for split in TARGET_SPLITS:
        stats = split_summary[split]
        lines.append(
            table_row(
                [
                    split,
                    stats["images"],
                    stats["instances"],
                    stats["class_instances"].get(0, 0),
                    stats["class_instances"].get(1, 0),
                    stats["class_instances"].get(2, 0),
                    stats["class_images"].get(0, 0),
                    stats["class_images"].get(1, 0),
                    stats["class_images"].get(2, 0),
                ]
            )
        )

    lines.extend(["", "### Split Instance Ratios", table_row(["split", "Caries", "Periapical Lesion", "Impacted"]), table_row(["---", "---:", "---:", "---:"])])
    for split in TARGET_SPLITS:
        ratios = split_summary[split]["class_instance_ratio"]
        lines.append(table_row([split, f"{ratios[0] * 100:.2f}%", f"{ratios[1] * 100:.2f}%", f"{ratios[2] * 100:.2f}%"]))

    lines.extend([
        "",
        "## Verification",
        f"- Invalid output label reasons: `{dict(verification['invalid_reasons'])}`",
        f"- Missing labels: {len(verification['missing_labels'])}",
        f"- Orphan labels: {len(verification['orphan_labels'])}",
        f"- original_id leaks after regrouping: {len(verification['leaks'])}",
        "",
        table_row(["split", "images", "labels", "instances", "Caries inst", "Periapical inst", "Impacted inst"]),
        table_row(["---", "---:", "---:", "---:", "---:", "---:", "---:"]),
    ])
    for split in TARGET_SPLITS:
        stats = verification["split_stats"][split]
        lines.append(table_row([split, stats["images"], stats["labels"], stats["instances"], stats["class_instances"].get(0, 0), stats["class_instances"].get(1, 0), stats["class_instances"].get(2, 0)]))

    return "\n".join(lines) + "\n"


def write_yaml(path: Path, server_dataset_root: str) -> None:
    text = f"""path: {server_dataset_root}
train: images/train
val: images/val
test: images/test

nc: 3
names:
  0: Caries
  1: Periapical Lesion
  2: Impacted
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a clean 3-class YOLO detection dataset from the 31-class dental dataset.")
    parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT / "data" / "raw" / "dental_31cls")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "transfer" / "dental_lesion_3cls_large")
    parser.add_argument("--server-dataset-root", default="transfer/dental_lesion_3cls_large")
    parser.add_argument("--yaml-out", type=Path, default=Path("data/dental_lesion_3cls_large.yaml"))
    parser.add_argument("--report-out", type=Path, default=Path("docs/dataset_audit_report.md"))
    parser.add_argument("--summary-json", type=Path, default=Path("docs/dataset_audit_summary.json"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    records, audit = read_source_dataset(args.source_root)
    filtered_records = [record for record in records if record.boxes]
    assigned = split_groups(filtered_records, {"train": 0.8, "val": 0.1, "test": 0.1}, args.seed)
    split_summary = {split: summarize_records(items) for split, items in assigned.items()}
    _, collisions = write_dataset(assigned, args.output_root, args.overwrite)
    verification = verify_output(args.output_root)

    args.yaml_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(args.yaml_out, args.server_dataset_root)
    report = render_report(audit, filtered_records, split_summary, verification, args.output_root, collisions)
    args.report_out.write_text(report, encoding="utf-8")

    summary = {
        "output_root": str(args.output_root.resolve()),
        "filtered_images": len(filtered_records),
        "dropped_images": sum(v["images"] for v in audit["split_stats"].values()) - len(filtered_records),
        "split_summary": split_summary,
        "verification": {
            "split_stats": verification["split_stats"],
            "invalid_reasons": dict(verification["invalid_reasons"]),
            "missing_labels": len(verification["missing_labels"]),
            "orphan_labels": len(verification["orphan_labels"]),
            "leaks": len(verification["leaks"]),
        },
        "source_invalid_reasons": dict(audit["invalid_reasons"]),
        "source_leaks": len(audit["source_leaks"]),
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
