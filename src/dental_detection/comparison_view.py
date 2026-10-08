from __future__ import annotations

import base64
from io import BytesIO
from html import escape
from typing import Any

from PIL import Image

from .result_items import model_result_name
from .visualization import as_rgb_image


MAX_COMPARE_EDGE = 1800


def _image_data_uri(image: Any) -> tuple[str, int, int]:
    rendered = as_rgb_image(image).copy()
    rendered.thumbnail((MAX_COMPARE_EDGE, MAX_COMPARE_EDGE), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    rendered.save(buffer, format="JPEG", quality=90, subsampling=0, optimize=True)
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}", rendered.width, rendered.height


def empty_comparison_html() -> str:
    return (
        '<div class="image-compare-empty">'
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<rect x="3" y="3" width="18" height="18" rx="2"></rect>'
        '<path d="m3 16 5-5 4 4 3-3 6 6"></path>'
        '<circle cx="9" cy="8" r="1.5"></circle>'
        '</svg><div><strong>等待检测结果</strong>'
        '<span>完成分析后，可拖动中间分隔线比较图像。</span></div>'
        "</div>"
    )


def build_comparison_html(results: list[dict[str, Any]]) -> str:
    valid = [item for item in results if isinstance(item, dict) and item.get("annotated") is not None]
    if not valid:
        return empty_comparison_html()

    primary = valid[0]
    if len(valid) > 1:
        before_image = primary["annotated"]
        after_image = valid[1]["annotated"]
        before_label = model_result_name(primary, "主模型")
        after_label = model_result_name(valid[1], "对比模型")
    else:
        before_image = primary.get("original")
        if before_image is None:
            before_image = primary["annotated"]
        after_image = primary["annotated"]
        before_label = "原始影像"
        after_label = model_result_name(primary, "检测结果")

    before_uri, width, height = _image_data_uri(before_image)
    after_uri, _, _ = _image_data_uri(after_image)
    safe_before = escape(before_label)
    safe_after = escape(after_label)
    aspect_ratio = f"{max(1, width)} / {max(1, height)}"
    return f"""
<div class="image-compare" data-image-compare style="--compare-position: 50%; --compare-aspect: {aspect_ratio};">
  <div class="image-compare-heading" aria-hidden="true">
    <span class="image-compare-label image-compare-label-before">{safe_before}</span>
    <span class="image-compare-label image-compare-label-after">{safe_after}</span>
  </div>
  <div class="image-compare-stage">
    <img class="image-compare-before" src="{before_uri}" alt="{safe_before}" />
    <div class="image-compare-after-wrap">
      <img class="image-compare-after" src="{after_uri}" alt="{safe_after}" />
    </div>
    <div class="image-compare-divider" aria-hidden="true"><span>↔</span></div>
    <input class="image-compare-range" type="range" min="0" max="100" value="50"
      aria-label="拖动比较 {safe_before} 与 {safe_after}" />
  </div>
  <p class="image-compare-caption">拖动中间分隔线查看两侧差异</p>
</div>
""".strip()
