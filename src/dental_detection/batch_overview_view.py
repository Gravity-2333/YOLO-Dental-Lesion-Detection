from __future__ import annotations

import csv
import io
from typing import Any


def html_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def html_table(rows: list[dict[str, Any]], columns: list[str], empty_text: str) -> str:
    if not rows:
        return f'<p class="empty-note">{html_escape(empty_text)}</p>'
    headers = "".join(f"<th>{html_escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html_escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def batch_overview_html(overview: dict[str, Any]) -> str:
    if not overview:
        return ""
    stat_items = [
        ("图片总数", overview.get("图片总数", 0)),
        ("成功处理", overview.get("成功处理", 0)),
        ("处理失败", overview.get("处理失败", 0)),
        ("检测框总数", overview.get("检测框总数", 0)),
        ("平均置信度", overview.get("平均置信度", 0)),
        ("最高置信度", overview.get("最高置信度", 0)),
    ]
    stat_html = "".join(
        f'<div class="overview-stat"><span>{html_escape(label)}</span><strong>{html_escape(value)}</strong></div>'
        for label, value in stat_items
    )
    failed_rows = [{"失败图片": item} for item in overview.get("失败图片", [])]
    empty_rows = [{"无检测结果图片": item} for item in overview.get("无检测结果图片", [])]
    poor_quality_rows = [{"质量较差图片": item} for item in overview.get("质量较差图片", [])]
    return f"""
<section class="batch-overview-panel">
  <div class="overview-stats">{stat_html}</div>
  <p class="overview-classes">涉及类别：{html_escape(overview.get("涉及类别", "无"))}</p>
  <h3>类别统计</h3>
  {html_table(overview.get("类别统计", []), ["类别", "中文名称", "检测框数量", "涉及图片数", "最高置信度", "平均置信度"], "暂无类别统计")}
  <h3>重点关注图片</h3>
  {html_table(overview.get("重点关注图片", []), ["排名", "图片名称", "最高类别", "最高置信度", "检测框数量", "关注等级"], "暂无重点关注图片")}
  <details><summary>失败图片：{len(failed_rows)} 张</summary>{html_table(failed_rows, ["失败图片"], "无失败图片")}</details>
  <details><summary>无检测结果图片：{len(empty_rows)} 张</summary>{html_table(empty_rows, ["无检测结果图片"], "无未检出图片")}</details>
  <details><summary>质量较差图片：{len(poor_quality_rows)} 张</summary>{html_table(poor_quality_rows, ["质量较差图片"], "暂无质量较差图片")}</details>
</section>
"""


def batch_overview_csv_text(overview: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["批量检测总览"])
    for label in ["图片总数", "成功处理", "处理失败", "检测框总数", "平均置信度", "最高置信度", "涉及类别"]:
        writer.writerow([label, overview.get(label, "无" if label == "涉及类别" else 0)])
    writer.writerow([])
    writer.writerow(["类别统计"])
    class_columns = ["类别", "中文名称", "检测框数量", "涉及图片数", "最高置信度", "平均置信度"]
    writer.writerow(class_columns)
    for row in overview.get("类别统计", []):
        writer.writerow([row.get(column, "") for column in class_columns])
    writer.writerow([])
    writer.writerow(["重点关注图片"])
    focus_columns = ["排名", "图片名称", "最高类别", "最高置信度", "检测框数量", "关注等级"]
    writer.writerow(focus_columns)
    for row in overview.get("重点关注图片", []):
        writer.writerow([row.get(column, "") for column in focus_columns])
    writer.writerow([])
    writer.writerow(["质量较差图片"])
    for image_name in overview.get("质量较差图片", []):
        writer.writerow([image_name])
    writer.writerow([])
    writer.writerow(["无检测结果图片"])
    for image_name in overview.get("无检测结果图片", []):
        writer.writerow([image_name])
    writer.writerow([])
    writer.writerow(["失败图片"])
    for image_name in overview.get("失败图片", []):
        writer.writerow([image_name])
    return buffer.getvalue()
