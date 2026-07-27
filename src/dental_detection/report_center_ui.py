from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

import gradio as gr
import pandas as pd

from .error_messages import friendly_error_message
from .gradio_files import clear_file_output, file_component_output
from .personal_workspace import (
    delete_personal_report,
    ensure_personal_workspace,
    get_personal_report,
    list_personal_reports,
)
from .record_views import dataframe_table_html
from .settings_store import storage_root
from .workspace_models import ReportAsset
from .workspace_store import WorkspaceError

REPORT_TABLE_COLUMNS = ["生成时间", "文件名", "格式", "模型", "文件状态"]
REPORT_TRASH_LABEL = "移入回收站"
REPORT_TRASH_CONFIRM_LABEL = "再次点击确认"


@dataclass(frozen=True, slots=True)
class ReportCenterComponents:
    report_select: gr.Dropdown
    report_table: gr.HTML
    report_detail: gr.Textbox
    report_file: gr.File
    report_feedback: gr.Textbox
    refresh_button: gr.Button
    trash_button: gr.Button


def _report_path(storage_dir: str, report: ReportAsset) -> Path:
    root = storage_root(storage_dir).expanduser().resolve()
    path = (root / report.storage_key).resolve()
    if path == root or root not in path.parents:
        raise ValueError("报告文件路径超出当前数据目录。")
    return path


def _local_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return str(value or "")


def _file_status(storage_dir: str, report: ReportAsset) -> str:
    try:
        return "可用" if _report_path(storage_dir, report).is_file() else "文件缺失"
    except (OSError, RuntimeError, ValueError):
        return "路径无效"


def _report_statuses(storage_dir: str, reports: list[ReportAsset]) -> dict[str, str]:
    return {report.id: _file_status(storage_dir, report) for report in reports}


def _report_choices(
    storage_dir: str,
    reports: list[ReportAsset],
    statuses: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    if statuses is None:
        statuses = _report_statuses(storage_dir, reports)
    choices = []
    for report in reports:
        label = f"{report.file_name} · {_local_timestamp(report.created_at)}"
        if statuses.get(report.id) != "可用":
            label += " · 文件缺失"
        choices.append((label, report.id))
    return choices


def _report_table_html(
    storage_dir: str,
    reports: list[ReportAsset],
    statuses: dict[str, str] | None = None,
) -> str:
    if statuses is None:
        statuses = _report_statuses(storage_dir, reports)
    rows = [
        [
            _local_timestamp(report.created_at),
            report.file_name,
            report.report_format.upper(),
            report.model_version or "未记录",
            statuses.get(report.id, "路径无效"),
        ]
        for report in reports
    ]
    frame = pd.DataFrame(rows, columns=REPORT_TABLE_COLUMNS)
    return dataframe_table_html(frame, "当前患者暂无报告记录。")


def _report_detail(storage_dir: str, report: ReportAsset | None) -> str:
    if report is None:
        return "暂无报告记录。"
    status = _file_status(storage_dir, report)
    return "\n".join(
        [
            f"文件名：{report.file_name}",
            f"格式：{report.report_format.upper()}",
            f"生成时间：{_local_timestamp(report.created_at)}",
            f"模型：{report.model_version or '未记录'}",
            f"检测任务：{report.task_id}",
            f"文件状态：{status}",
        ]
    )


def _report_file_output(storage_dir: str, report: ReportAsset | None):
    if report is None:
        return clear_file_output()
    try:
        path = _report_path(storage_dir, report)
    except (OSError, RuntimeError, ValueError):
        return clear_file_output()
    return file_component_output(path) if path.is_file() else clear_file_output()


def _load_reports(storage_dir: str, patient_id: str) -> list[ReportAsset]:
    return list_personal_reports(storage_dir, patient_id, limit=200)


def build_report_center(
    storage_dir: str,
    patient_id: str,
    *,
    load_initial: bool = True,
) -> ReportCenterComponents:
    reports = _load_reports(storage_dir, patient_id) if load_initial else []
    statuses = _report_statuses(storage_dir, reports)
    choices = _report_choices(storage_dir, reports, statuses)
    selected_id = choices[0][1] if choices else None
    selected = reports[0] if reports else None
    with gr.Group(elem_classes=["section-card", "case-card"]):
        gr.HTML(
            '<div class="card-heading"><div><h2>报告中心</h2>'
            '<p>集中查看当前患者已生成的 Word 和 ZIP 报告。</p></div></div>'
        )
        with gr.Row(elem_classes=["compact-row"]):
            refresh_button = gr.Button("刷新报告", elem_classes=["secondary-action", "compact-button"])
            trash_button = gr.Button(
                REPORT_TRASH_LABEL,
                interactive=bool(selected),
                elem_classes=["danger-action", "compact-button"],
            )
        report_feedback = gr.Textbox(
            label="报告反馈",
            interactive=False,
            lines=1,
            elem_classes=["inline-feedback"],
        )
        report_select = gr.Dropdown(label="已生成报告", choices=choices, value=selected_id)
        with gr.Accordion(
            "结构化报告列表",
            open=False,
            elem_classes=["compact-accordion"],
        ):
            report_table = gr.HTML(
                value=_report_table_html(storage_dir, reports, statuses),
                elem_classes=["record-table-shell"],
            )
        initial_file = _report_file_output(storage_dir, selected)
        report_file = gr.File(
            value=initial_file["value"],
            label="下载报告",
            visible=bool(initial_file["visible"]),
        )
        report_detail = gr.Textbox(
            value=_report_detail(storage_dir, selected),
            label="报告详情",
            interactive=False,
            lines=7,
        )
    return ReportCenterComponents(
        report_select=report_select,
        report_table=report_table,
        report_detail=report_detail,
        report_file=report_file,
        report_feedback=report_feedback,
        refresh_button=refresh_button,
        trash_button=trash_button,
    )


def refresh_report_center(
    storage_dir: str,
    patient_id: str,
    feedback: str = "",
    *,
    include_file: bool = True,
):
    try:
        reports = _load_reports(storage_dir, patient_id)
        statuses = _report_statuses(storage_dir, reports)
        choices = _report_choices(storage_dir, reports, statuses)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise gr.Error(friendly_error_message(exc, "报告记录读取失败")) from exc
    selected_id = choices[0][1] if choices else None
    selected = reports[0] if reports else None
    return (
        gr.update(choices=choices, value=selected_id),
        _report_table_html(storage_dir, reports, statuses),
        _report_detail(storage_dir, selected),
        _report_file_output(storage_dir, selected) if include_file else clear_file_output(),
        feedback,
        gr.update(value=REPORT_TRASH_LABEL, interactive=bool(selected)),
    )


def load_report_center_item(report_id: str, storage_dir: str, patient_id: str):
    if not str(report_id or "").strip():
        return (
            "暂无报告记录。",
            clear_file_output(),
            "",
            gr.update(value=REPORT_TRASH_LABEL, interactive=False),
        )
    try:
        report = get_personal_report(storage_dir, patient_id, report_id)
        path = _report_path(storage_dir, report)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        raise gr.Error(friendly_error_message(exc, "报告记录读取失败")) from exc
    if not path.is_file():
        return (
            _report_detail(storage_dir, report),
            clear_file_output(),
            "报告文件已不存在，可以将这条失效记录移入回收站。",
            gr.update(value=REPORT_TRASH_LABEL, interactive=True),
        )
    return (
        _report_detail(storage_dir, report),
        file_component_output(path),
        "",
        gr.update(value=REPORT_TRASH_LABEL, interactive=True),
    )


def load_active_report_center_item(report_id: str, storage_dir: str, patient_id: str):
    """Load the selected report, falling back to the first item on initial tab entry."""
    active_id = str(report_id or "").strip()
    if not active_id:
        try:
            reports = _load_reports(storage_dir, patient_id)
        except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
            raise gr.Error(friendly_error_message(exc, "报告记录读取失败")) from exc
        active_id = reports[0].id if reports else ""
    return load_report_center_item(active_id, storage_dir, patient_id)


def load_tab_report_center_file(
    report_id: str,
    storage_dir: str,
    patient_id: str,
):
    """Hydrate the selected report file, falling back only on first tab entry."""
    _, file_output, _, _ = load_active_report_center_item(report_id, storage_dir, patient_id)
    return file_output


def trash_report_center_item(report_id: str, storage_dir: str, patient_id: str):
    if not str(report_id or "").strip():
        raise gr.Error("请先选择一条报告记录。")
    moved_to: Path | None = None
    original_path: Path | None = None
    try:
        report = get_personal_report(storage_dir, patient_id, report_id)
        original_path = _report_path(storage_dir, report)
        if original_path.is_file():
            trash_dir = ensure_personal_workspace(storage_dir).store.root / "reports_trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            moved_to = trash_dir / f"{original_path.stem}_{stamp}{original_path.suffix}"
            shutil.move(str(original_path), str(moved_to))
        delete_personal_report(storage_dir, patient_id, report.id)
    except (OSError, sqlite3.Error, WorkspaceError, TypeError, ValueError) as exc:
        if moved_to is not None and original_path is not None and moved_to.exists() and not original_path.exists():
            try:
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(moved_to), str(original_path))
            except OSError:
                pass
        raise gr.Error(friendly_error_message(exc, "报告移入回收站失败")) from exc
    message = "报告已移入回收站。" if moved_to is not None else "失效的报告记录已移除。"
    return refresh_report_center(storage_dir, patient_id, message)


def _report_trash_target(report_id: str, storage_dir: str, patient_id: str) -> str:
    return "\n".join(
        (
            str(storage_dir or "").strip(),
            str(patient_id or "").strip(),
            str(report_id or "").strip(),
        )
    )


def confirm_trash_report_center_item(
    report_id: str,
    storage_dir: str,
    patient_id: str,
    confirmation: dict | None = None,
):
    if not str(report_id or "").strip():
        raise gr.Error("请先选择一条报告记录。")
    target = _report_trash_target(report_id, storage_dir, patient_id)
    armed_target = str((confirmation or {}).get("target") or "")
    if armed_target != target:
        return (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            "再次点击按钮后，所选报告将移入回收站。",
            gr.update(value=REPORT_TRASH_CONFIRM_LABEL, interactive=True),
            {"target": target},
        )

    values = list(trash_report_center_item(report_id, storage_dir, patient_id))
    button_update = dict(values[-1])
    button_update["value"] = REPORT_TRASH_LABEL
    values[-1] = button_update
    return (*values, {})


def reset_report_trash_confirmation():
    return {}
