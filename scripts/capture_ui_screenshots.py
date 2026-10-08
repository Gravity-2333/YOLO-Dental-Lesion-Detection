from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dental_detection.browser_fallback import launch_chromium_with_fallback

DEFAULT_BASE_URL = "http://127.0.0.1:7860"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "ai-bridge" / "screenshots" / "ui-regression"
DEFAULT_EXAMPLE = (
    PROJECT_ROOT
    / "assets"
    / "branding"
    / "real-dental-panorama-test-00021.jpg"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture UI regression screenshots for the Gradio workbench.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Gradio base URL. Default: http://127.0.0.1:7860")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Directory for screenshots.")
    parser.add_argument("--suffix", default="", help="Optional suffix inserted before .png, for example -after.")
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE), help="Image used for the detection-flow screenshot.")
    return parser.parse_args(argv)


def check_service(base_url: str) -> None:
    try:
        with urlopen(base_url, timeout=10) as response:
            status = getattr(response, "status", 200)
    except URLError as exc:
        raise SystemExit(
            f"无法访问 {base_url}。请先启动服务，例如运行 start_project.bat，然后重试。原始错误：{exc}"
        ) from exc
    except TimeoutError as exc:
        raise SystemExit(f"访问 {base_url} 超时。请确认 Gradio 服务已启动并监听该地址。") from exc
    if int(status) >= 400:
        raise SystemExit(f"访问 {base_url} 返回 HTTP {status}，请确认服务状态正常。")


def name(base: str, suffix: str) -> str:
    stem = base[:-4] if base.endswith(".png") else base
    return f"{stem}{suffix}.png"


def wait_ready(page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)


def click_tab(page, tab_name: str) -> None:
    tab = page.locator(
        f'.app-primary-nav-list > li > button[data-app-target="{tab_name}"]'
    ).first
    if tab.count() == 0 or not tab.is_visible():
        raise RuntimeError(f"无法定位主导航入口：{tab_name}")
    try:
        tab.click(timeout=15000)
    except Exception:
        pass
    page.wait_for_function(
        """label => [...document.querySelectorAll(
                '.app-primary-nav-list > li > .app-nav-link[data-app-target]'
            )].some(element => element.dataset.appTarget === label
                && element.getAttribute('aria-current') === 'page')""",
        arg=tab_name,
        timeout=15000,
    )
    page.wait_for_timeout(1500)


def check_ai_to_workbench_navigation(page, console_errors: list[str]) -> None:
    click_tab(page, "AI 问答")
    if page.locator(".ai-chat-thread").count() != 1:
        raise RuntimeError("AI 工作台聊天区域未正确渲染。")
    click_tab(page, "检测工作台")
    page.get_by_text("上传影像", exact=True).wait_for(state="visible", timeout=15000)
    svelte_loops = [
        message for message in console_errors
        if "effect_update_depth_exceeded" in message
    ]
    if svelte_loops:
        raise RuntimeError("AI 工作台返回检测界面时触发了 Svelte 更新循环。")


def click_accordion(page, label: str) -> None:
    page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}")).first.click(timeout=15000)
    page.wait_for_timeout(800)


def click_settings_section(page, label: str) -> None:
    if label in {"接口", "自动化"}:
        parent = page.locator(".settings-nav-ai-parent")
        if parent.count() != 1:
            raise RuntimeError("无法定位 AI 设置父栏目。")
        if parent.get_attribute("aria-expanded") != "true":
            parent.click(timeout=10000)
    section = page.get_by_role("radio", name=label, exact=True)
    if section.count() == 0:
        raise RuntimeError(f"无法定位设置栏目：{label}")
    if label in {"接口", "自动化"}:
        section.first.wait_for(state="visible", timeout=5000)
    section.first.click(timeout=15000)
    page.wait_for_timeout(800)


def check_settings_round_trip_visibility(page, output_dir: Path, suffix: str) -> None:
    expected_titles = {
        "工作台": "工作台",
        "模型": "模型与推理",
        "接口": "AI 接口",
        "自动化": "对话自动化",
        "存储": "存储与隐私",
    }
    click_tab(page, "设置")
    for section, expected_title in expected_titles.items():
        click_settings_section(page, section)
        click_tab(page, "检测历史")
        click_tab(page, "设置")
        page.wait_for_timeout(500)
        visible_titles = page.evaluate(
            """() => [...document.querySelectorAll('.settings-pane')]
                .filter(pane => {
                    const rect = pane.getBoundingClientRect();
                    const style = getComputedStyle(pane);
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 1 && rect.height > 1;
                })
                .map(pane => pane.querySelector('h2')?.textContent?.trim() || '')"""
        )
        if visible_titles != [expected_title]:
            raise RuntimeError(
                f"设置栏目往返后显隐异常：{section} -> {visible_titles}，"
                f"期望仅显示 {expected_title}。"
            )
        if section == "模型":
            page.screenshot(
                path=str(output_dir / name("02-settings-model-return.png", suffix)),
                full_page=False,
            )


def check_settings_ai_subnavigation(page, output_dir: Path, suffix: str) -> None:
    click_tab(page, "设置")
    click_settings_section(page, "工作台")
    parent = page.locator(".settings-nav-ai-parent")
    interface = page.get_by_role("radio", name="接口", exact=True)
    automation = page.get_by_role("radio", name="自动化", exact=True)
    if parent.count() != 1 or parent.get_attribute("aria-expanded") != "false":
        raise RuntimeError("AI 设置父栏目初始收起状态异常。")
    if interface.is_visible() or automation.is_visible():
        raise RuntimeError("AI 设置子栏目在收起时仍然可见。")

    parent.click(timeout=10000)
    interface.wait_for(state="visible", timeout=5000)
    automation.wait_for(state="visible", timeout=5000)
    if parent.get_attribute("aria-expanded") != "true":
        raise RuntimeError("AI 设置父栏目展开状态未同步。")
    page.screenshot(
        path=str(output_dir / name("02-settings-ai-subnav-open.png", suffix)),
        full_page=False,
    )

    interface.click(timeout=10000)
    page.locator(".settings-page-heading h2", has_text="AI 接口").wait_for(state="visible")
    if not parent.evaluate("button => button.classList.contains('is-active')"):
        raise RuntimeError("选择接口子栏目后 AI 父栏目未显示激活状态。")
    page.screenshot(
        path=str(output_dir / name("02-settings-ai-interface.png", suffix)),
        full_page=False,
    )

    parent.click(timeout=10000)
    if interface.is_visible() or automation.is_visible():
        raise RuntimeError("AI 设置父栏目无法收起子栏目。")
    parent.click(timeout=10000)
    automation.wait_for(state="visible", timeout=5000)
    automation.click(timeout=10000)
    page.locator(".settings-page-heading h2", has_text="对话自动化").wait_for(state="visible")

    click_settings_section(page, "模型")
    if parent.get_attribute("aria-expanded") != "false":
        raise RuntimeError("离开 AI 设置后子栏目未自动收起。")


def configure_isolated_detection_session(page, storage_dir: Path) -> bool:
    click_tab(page, "设置")
    click_settings_section(page, "接口")
    ai_enabled = page.get_by_label("启用 AI 建议与问答")
    if ai_enabled.count() != 1:
        raise RuntimeError("截图会话无法唯一定位 AI 开关，已停止以避免外部请求。")
    ai_was_enabled = ai_enabled.is_checked()
    if ai_was_enabled:
        ai_enabled.uncheck(timeout=10000)

    click_settings_section(page, "存储")
    storage_input = page.get_by_label("存储目录")
    if storage_input.count() != 1:
        raise RuntimeError("截图会话无法唯一定位存储目录，已停止以避免写入真实数据。")
    isolated_path = str(storage_dir.resolve())
    storage_input.fill(isolated_path, timeout=10000)
    if storage_input.input_value() != isolated_path:
        raise RuntimeError("截图会话未能切换到临时数据目录，已停止以避免写入真实数据。")
    click_tab(page, "检测工作台")
    return ai_was_enabled


def open_ai_page_for_capture(page, restore_enabled: bool) -> None:
    if restore_enabled:
        click_tab(page, "设置")
        click_settings_section(page, "接口")
        ai_enabled = page.get_by_label("启用 AI 建议与问答")
        if not ai_enabled.is_checked():
            ai_enabled.check(timeout=10000)
    click_tab(page, "AI 问答")


def save(
    page,
    output_dir: Path,
    filename: str,
    *,
    full: bool = False,
    reset_scroll: bool = False,
) -> None:
    if reset_scroll:
        page.evaluate(
            """() => {
                if (document.activeElement instanceof HTMLElement) {
                    document.activeElement.blur();
                }
                const scrollingElement = document.scrollingElement || document.documentElement;
                scrollingElement.scrollTop = 0;
                scrollingElement.scrollLeft = 0;
                document.body.scrollTop = 0;
                document.body.scrollLeft = 0;
            }"""
        )
        page.wait_for_timeout(300)
    path = output_dir / filename
    page.screenshot(path=str(path), full_page=full)
    print(f"saved {path}")


def check_horizontal_overflow(page, label: str) -> None:
    dimensions = page.evaluate(
        """() => ({
            clientWidth: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
        })"""
    )
    if dimensions["scrollWidth"] > dimensions["clientWidth"] + 2:
        raise RuntimeError(
            f"{label} 存在横向溢出：{dimensions['scrollWidth']} > {dimensions['clientWidth']}"
        )


def check_visible_path_row_alignment(page, label: str) -> None:
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.path-row')]
            .filter(row => {
                const rect = row.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            })
            .map(row => {
                const controls = [...row.children]
                    .map(element => element.matches('button,input,textarea')
                        ? element
                        : element.querySelector('button,input,textarea'))
                    .filter(Boolean);
                const bottoms = controls.map(element => Math.round(element.getBoundingClientRect().bottom));
                return bottoms.length ? Math.max(...bottoms) - Math.min(...bottoms) : 0;
            })"""
    )
    if any(delta > 1 for delta in rows):
        raise RuntimeError(f"{label} 路径工具行未对齐：{rows}")


def check_visible_model_row_alignment(page, label: str) -> None:
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.model-row')]
            .filter(row => {
                const rect = row.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            })
            .map(row => {
                const button = [...row.children].find(element => element.matches('button, .secondary-action'));
                const dropdown = [...row.children].find(element => element.querySelector('.secondary-wrap'));
                const bottoms = [button, dropdown]
                    .filter(Boolean)
                    .map(element => Math.round(element.getBoundingClientRect().bottom));
                return bottoms.length ? Math.max(...bottoms) - Math.min(...bottoms) : 0;
            })"""
    )
    if any(delta > 10 for delta in rows):
        raise RuntimeError(f"{label} 模型工具行未对齐：{rows}")


def check_workbench_tab_alignment(page) -> None:
    rows = page.evaluate(
        """() => ['.sub-tabs', '.result-view-tabs'].map(selector => {
            const row = document.querySelector(`${selector} [role="tablist"]`);
            if (!row) return null;
            const rect = row.getBoundingClientRect();
            return {selector, top: rect.top, height: rect.height};
        })"""
    )
    if any(row is None for row in rows):
        raise RuntimeError(f"工作台选项卡行缺失：{rows}")
    if abs(rows[0]["top"] - rows[1]["top"]) > 1 or abs(rows[0]["height"] - rows[1]["height"]) > 1:
        raise RuntimeError(f"工作台选项卡未对齐：{rows}")


def check_patient_toolbar_clearance(page, minimum_gap: int = 8) -> None:
    layout = page.evaluate(
        """() => {
            const patient = document.querySelector('.workbench-patient-bar .compact-control');
            const button = document.querySelector('.patient-control-row > button');
            const outerFrame = document.querySelector('.patient-control-row .wrap-inner');
            const innerFrame = document.querySelector('.patient-control-row .secondary-wrap');
            const tabs = document.querySelector('.sub-tabs [role="tablist"]');
            if (!patient || !button || !outerFrame || !innerFrame || !tabs) return null;
            const patientRect = patient.getBoundingClientRect();
            const buttonRect = button.getBoundingClientRect();
            const tabsRect = tabs.getBoundingClientRect();
            return {
                patientTop: patientRect.top,
                patientBottom: patientRect.bottom,
                buttonTop: buttonRect.top,
                buttonBottom: buttonRect.bottom,
                tabsTop: tabsRect.top,
                outerBorder: parseFloat(getComputedStyle(outerFrame).borderTopWidth),
                innerBorder: parseFloat(getComputedStyle(innerFrame).borderTopWidth),
            };
        }"""
    )
    if layout is None:
        raise RuntimeError("工作台患者工具栏或分析选项卡缺失")
    if layout["tabsTop"] - layout["patientBottom"] < minimum_gap:
        raise RuntimeError(f"分析选项卡遮挡患者选择框：{layout}")
    if (
        abs(layout["patientTop"] - layout["buttonTop"]) > 1
        or abs(layout["patientBottom"] - layout["buttonBottom"]) > 1
    ):
        raise RuntimeError(f"患者选择框与清空会话按钮未对齐：{layout}")
    if layout["outerBorder"] > 0 or layout["innerBorder"] < 1:
        raise RuntimeError(f"患者选择框仍存在双层边框：{layout}")


def check_case_capture_layout(page) -> None:
    layout = page.evaluate(
        """() => {
            const accordion = document.querySelector('.record-management > button.label-wrap');
            const fields = [...document.querySelectorAll('.record-capture-fields input, .record-capture-fields textarea')];
            const fieldBlocks = [...document.querySelectorAll('.record-capture-fields > .form > .block')];
            const save = document.querySelector('button.record-save-button, .record-save-button button');
            const refresh = document.querySelector('button.record-toolbar-button, .record-toolbar-button button');
            const select = document.querySelector('.record-patient-select .wrap-inner');
            const nestedStrip = document.querySelector('.record-capture-strip > .record-capture-strip');
            if (!accordion || fields.length !== 2 || fieldBlocks.length !== 2 || !save || !refresh || !select || !nestedStrip) {
                return null;
            }
            const fieldRects = fields.map(field => field.getBoundingClientRect());
            const saveRect = save.getBoundingClientRect();
            const refreshRect = refresh.getBoundingClientRect();
            const selectRect = select.getBoundingClientRect();
            const accordionRect = accordion.getBoundingClientRect();
            const nestedStyle = getComputedStyle(nestedStrip);
            return {
                accordionHeight: accordionRect.height,
                accordionArrow: getComputedStyle(accordion, '::after').content,
                fieldHeights: fieldRects.map(rect => rect.height),
                fieldWidths: fieldRects.map(rect => rect.width),
                bottomOffsets: fieldRects.map(rect => Math.abs(rect.bottom - saveRect.bottom)),
                gaps: [fieldRects[1].left - fieldRects[0].right, saveRect.left - fieldRects[1].right],
                toolbarBottomOffset: Math.abs(selectRect.bottom - refreshRect.bottom),
                toolbarHeightOffset: Math.abs(selectRect.height - refreshRect.height),
                nestedPadding: nestedStyle.padding,
                nestedBackground: nestedStyle.backgroundColor,
                saveStyles: (() => {
                    const wasDisabled = save.disabled;
                    const previousTransition = save.style.getPropertyValue('transition');
                    const previousPriority = save.style.getPropertyPriority('transition');
                    save.style.setProperty('transition', 'none', 'important');
                    save.disabled = true;
                    void save.offsetWidth;
                    const disabledStyle = getComputedStyle(save);
                    const disabled = {
                        color: disabledStyle.color,
                        background: disabledStyle.backgroundColor,
                        opacity: disabledStyle.opacity,
                    };
                    save.disabled = false;
                    void save.offsetWidth;
                    const enabledStyle = getComputedStyle(save);
                    const enabled = {
                        color: enabledStyle.color,
                        background: enabledStyle.backgroundColor,
                        opacity: enabledStyle.opacity,
                    };
                    save.disabled = wasDisabled;
                    if (previousTransition) {
                        save.style.setProperty('transition', previousTransition, previousPriority);
                    } else {
                        save.style.removeProperty('transition');
                    }
                    return {disabled, enabled};
                })(),
            };
        }"""
    )
    if layout is None:
        raise RuntimeError("病例保存工具栏结构缺失。")
    if layout["accordionHeight"] > 52 or layout["accordionArrow"] in {"none", "normal"}:
        raise RuntimeError(f"患者档案管理折叠栏或箭头异常：{layout}")
    if any(abs(height - 46) > 1 for height in layout["fieldHeights"]):
        raise RuntimeError(f"病例输入框高度异常：{layout}")
    if any(width < 220 for width in layout["fieldWidths"]):
        raise RuntimeError(f"病例输入框宽度异常：{layout}")
    if any(offset > 1 for offset in layout["bottomOffsets"]):
        raise RuntimeError(f"病例输入框与保存按钮未对齐：{layout}")
    if any(gap < 8 or gap > 12 for gap in layout["gaps"]):
        raise RuntimeError(f"病例保存栏间距异常：{layout}")
    if layout["toolbarBottomOffset"] > 1 or layout["toolbarHeightOffset"] > 1:
        raise RuntimeError(f"患者选择器与刷新按钮未对齐：{layout}")
    if layout["nestedPadding"] != "0px" or layout["nestedBackground"] != "rgba(0, 0, 0, 0)":
        raise RuntimeError(f"病例保存区仍存在重复容器样式：{layout}")
    for state_name in ("disabled", "enabled"):
        style = layout["saveStyles"][state_name]
        if style["opacity"] != "1" or style["color"] == style["background"] or style["background"] == "rgba(0, 0, 0, 0)":
            raise RuntimeError(f"病例保存按钮 {state_name} 不可读：{layout}")
    if layout["saveStyles"]["enabled"]["background"] != "rgb(23, 111, 101)":
        raise RuntimeError(f"病例保存按钮启用态未使用主操作色：{layout}")


def preview_case_export_feedback(page) -> None:
    status = page.locator(".record-path-output").first
    if status.count() == 0:
        raise RuntimeError("病例导出路径反馈组件缺失。")
    if status.is_visible():
        raise RuntimeError("未导出病例报告时路径反馈不应占用页面空间。")
    status.evaluate(
        """element => {
            element.innerHTML = `
                <div class="report-export-status-line">
                    <span class="report-export-status-mark" aria-hidden="true"></span>
                    <span>已经导出 <strong title="E:\\data\\cases\\case_report.docx">cases/case_report.docx</strong></span>
                </div>`;
        }"""
    )
    status.wait_for(state="visible", timeout=5000)
    styles = status.evaluate(
        """element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            const mark = element.querySelector('.report-export-status-mark');
            const strong = element.querySelector('strong');
            return {
                height: rect.height,
                borderWidth: parseFloat(style.borderTopWidth),
                background: style.backgroundColor,
                markSize: mark?.getBoundingClientRect().width || 0,
                pathColor: strong ? getComputedStyle(strong).color : '',
            };
        }"""
    )
    if styles["height"] > 42 or styles["borderWidth"] > 0 or styles["background"] != "rgba(0, 0, 0, 0)":
        raise RuntimeError(f"病例路径反馈仍像输入框或卡片：{styles}")
    if styles["markSize"] < 6 or styles["pathColor"] != "rgb(23, 111, 101)":
        raise RuntimeError(f"病例路径反馈的状态标记或路径强调异常：{styles}")
    status.scroll_into_view_if_needed()
    page.wait_for_timeout(200)


def capture_empty_comparison_view(page, output_dir: Path, suffix: str) -> None:
    page.get_by_role("tab", name="滑动对比", exact=True).click(timeout=10000)
    empty = page.locator(".image-compare-empty")
    empty.wait_for(state="visible", timeout=5000)
    geometry = empty.evaluate(
        """element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return {
                height: rect.height,
                width: rect.width,
                borderWidth: parseFloat(style.borderTopWidth),
                overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            };
        }"""
    )
    if geometry["height"] < 468 or geometry["width"] < 480 or geometry["borderWidth"] < 1:
        raise RuntimeError(f"滑动对比空状态尺寸异常：{geometry}")
    if geometry["overflow"] > 1:
        raise RuntimeError(f"滑动对比空状态造成横向溢出：{geometry}")
    page.screenshot(path=str(output_dir / name("01-workbench-comparison-empty.png", suffix)))
    page.get_by_role("tab", name="检测结果", exact=True).click(timeout=10000)


def capture_ai_single_tooltip(page, output_dir: Path, suffix: str) -> None:
    trigger = page.locator(".ai-search-open")
    trigger.hover(timeout=10000)
    tooltip = page.locator("body > .ai-floating-tooltip.is-visible")
    tooltip.wait_for(state="visible", timeout=5000)
    state = trigger.evaluate(
        """element => ({
            floatingCount: document.querySelectorAll('body > .ai-floating-tooltip.is-visible').length,
            legacyContent: getComputedStyle(element, '::after').content,
        })"""
    )
    if state["floatingCount"] != 1 or state["legacyContent"] not in {"none", "normal"}:
        raise RuntimeError(f"AI 工具提示仍存在重复浮层：{state}")
    page.screenshot(path=str(output_dir / name("04-ai-chat-tooltip.png", suffix)))
    page.mouse.move(8, 8)


def show_context_help(page, scope: str) -> None:
    help_root = page.locator(f"{scope} .context-help:visible").first
    trigger = help_root.locator(".context-help-trigger")
    trigger.hover(timeout=10000)
    page.wait_for_timeout(400)
    state = help_root.locator(".context-help-bubble-card").evaluate(
        """element => {
            const rect = element.getBoundingClientRect();
            const clippedBy = [];
            for (let node = element.parentElement; node; node = node.parentElement) {
                const style = getComputedStyle(node);
                const nodeRect = node.getBoundingClientRect();
                const clipsX = ['hidden', 'clip'].includes(style.overflowX)
                    && (rect.left < nodeRect.left || rect.right > nodeRect.right);
                const clipsY = ['hidden', 'clip'].includes(style.overflowY)
                    && (rect.top < nodeRect.top || rect.bottom > nodeRect.bottom);
                if (clipsX || clipsY) clippedBy.push(`${node.tagName}.${String(node.className)}`);
            }
            return {
                valid: rect.width >= 220 && rect.height > 0 && clippedBy.length === 0,
                rect: {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom},
                clippedBy,
            };
        }"""
    )
    if not state["valid"]:
        raise RuntimeError(f"上下文提示气泡未显示：{scope} {state}")


def check_context_help_hover_only(page, scope: str) -> int:
    roots = page.locator(f"{scope} .context-help:visible")
    checked = 0
    for index in range(roots.count()):
        root = roots.nth(index)
        trigger = root.locator(".context-help-trigger")
        bubble = root.locator(".context-help-bubble")
        trigger.hover(timeout=10000)
        bubble.wait_for(state="visible", timeout=5000)
        trigger.click(timeout=5000)
        page.mouse.move(4, 4)
        page.wait_for_timeout(260)
        bubble.wait_for(state="hidden", timeout=5000)
        trigger.evaluate(
            """element => {
                element.setAttribute('tabindex', '-1');
                element.focus();
            }"""
        )
        page.wait_for_timeout(80)
        state = bubble.evaluate(
            """element => {
                const style = getComputedStyle(element);
                return {opacity: style.opacity, visibility: style.visibility};
            }"""
        )
        trigger.evaluate("element => { element.blur(); element.removeAttribute('tabindex'); }")
        if state["visibility"] != "hidden" or state["opacity"] != "0":
            raise RuntimeError(f"问号提示仍会被点击或焦点永久锁定：{scope} {state}")
        checked += 1
    return checked


def check_storage_heading_help(page, output_dir: Path, suffix: str) -> None:
    click_tab(page, "设置")
    click_settings_section(page, "存储")
    title = page.locator(".settings-page-heading h2", has_text="存储与隐私")
    if title.count() != 1 or not title.is_visible():
        raise RuntimeError("存储设置页标题缺失或重复。")
    if page.locator(".settings-card .section-heading", has_text="存储与隐私").count():
        raise RuntimeError("存储设置页仍保留重复的分区标题。")
    help_root = page.locator(".settings-page-heading > .context-help")
    if help_root.count() != 1 or not help_root.is_visible():
        raise RuntimeError("存储说明问号未移动到页面标题区域。")
    show_context_help(page, ".settings-page-heading")
    page.screenshot(
        path=str(output_dir / name("02-settings-storage-heading-help.png", suffix)),
        full_page=False,
    )


def capture_result_magnifier(page, output_dir: Path, suffix: str) -> None:
    stage = page.locator(".result-image-stage").first
    image = stage.locator(".primary-result-card img").first
    image.scroll_into_view_if_needed(timeout=10000)
    box = image.bounding_box()
    if not box:
        raise RuntimeError("无法获取检测结果图位置。")

    hover_x = box["x"] + box["width"] * 0.5
    hover_y = box["y"] + box["height"] * 0.5
    page.mouse.move(hover_x, hover_y)
    lens = page.locator("body > .result-magnifier")
    page.wait_for_timeout(250)
    if not lens.is_visible():
        state = page.evaluate(
            """({x, y}) => {
                const target = document.elementFromPoint(x, y);
                const image = document.querySelector('.primary-result-card img');
                const imageRect = image?.getBoundingClientRect();
                const toggle = document.querySelector('.result-magnifier-toggle');
                return {
                    point: {x, y},
                    target: target ? `${target.tagName}.${target.className}` : null,
                    insideResultCard: Boolean(target?.closest('.primary-result-card')),
                    imageRect: imageRect ? {
                        left: imageRect.left,
                        top: imageRect.top,
                        right: imageRect.right,
                        bottom: imageRect.bottom,
                    } : null,
                    runtimeEnabled: document.documentElement.dataset.resultMagnifierEnabled || '',
                    togglePressed: toggle?.getAttribute('aria-pressed') || '',
                };
            }""",
            {"x": hover_x, "y": hover_y},
        )
        raise RuntimeError(f"检测结果放大镜未显示：{state}")
    canvas_ready = lens.locator("canvas").evaluate(
        """canvas => {
            const context = canvas.getContext('2d');
            if (!context || !canvas.width || !canvas.height) return false;
            const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
            for (let index = 3; index < pixels.length; index += 4) {
                if (pixels[index] > 0) return true;
            }
            return false;
        }"""
    )
    if not canvas_ready:
        raise RuntimeError("悬停放大镜画布为空。")

    for quadrant, horizontal, vertical in (
        ("top-left", 0.4, 0.4),
        ("top-right", 0.6, 0.4),
        ("bottom-left", 0.4, 0.6),
        ("bottom-right", 0.6, 0.6),
    ):
        pointer_x = box["x"] + box["width"] * horizontal
        pointer_y = box["y"] + box["height"] * vertical
        page.mouse.move(
            pointer_x,
            pointer_y,
        )
        lens.wait_for(state="visible", timeout=5000)
        page.wait_for_timeout(100)
        if lens.get_attribute("data-quadrant") != quadrant:
            raise RuntimeError(f"放大镜象限位置错误：期望 {quadrant}。")
        lens_box = lens.bounding_box()
        if not lens_box:
            raise RuntimeError(f"无法读取 {quadrant} 放大框位置。")
        horizontally_correct = (
            lens_box["x"] + lens_box["width"] <= pointer_x
            if horizontal < 0.5
            else lens_box["x"] >= pointer_x
        )
        vertically_correct = (
            lens_box["y"] + lens_box["height"] <= pointer_y
            if vertical < 0.5
            else lens_box["y"] >= pointer_y
        )
        if not horizontally_correct or not vertically_correct:
            raise RuntimeError(
                f"{quadrant} 放大框未位于鼠标对应方向："
                f"pointer=({pointer_x}, {pointer_y}), lens={lens_box}"
            )

    zoom_before = lens.get_attribute("data-zoom")
    page.keyboard.down("Control")
    page.mouse.wheel(0, -120)
    page.keyboard.up("Control")
    zoom_after = lens.get_attribute("data-zoom")
    if zoom_before == zoom_after:
        raise RuntimeError("Ctrl + 滚轮未调整放大镜倍率。")

    overlay_valid = page.evaluate(
        """() => {
            const stage = document.querySelector('.result-image-stage');
            const legend = stage?.querySelector('.compact-result-legend');
            const image = stage?.querySelector('.primary-result-card img');
            if (!stage || !legend || !image) return false;
            const outer = stage.getBoundingClientRect();
            const inner = legend.getBoundingClientRect();
            const imageRect = image.getBoundingClientRect();
            return inner.width > 0 && inner.height > 0
                && inner.left >= outer.left && inner.right <= outer.right
                && inner.top >= imageRect.bottom - 1
                && inner.bottom <= outer.bottom
                && !legend.querySelector('.legend-separator');
        }"""
    )
    if not overlay_valid:
        raise RuntimeError("结果图例仍遮挡影像、超出结果区或保留了冒号。")

    toolbar_toggle = page.locator(".result-magnifier-toggle")
    if toolbar_toggle.count() != 1 or toolbar_toggle.get_attribute("aria-pressed") != "true":
        raise RuntimeError("结果图工具栏未显示已开启的放大镜按钮。")
    toolbar_toggle.click(timeout=10000)
    if toolbar_toggle.get_attribute("aria-pressed") != "false":
        raise RuntimeError("结果图工具栏未能关闭放大镜。")
    page.mouse.move(hover_x, hover_y)
    if page.locator(".result-magnifier.is-visible").count():
        raise RuntimeError("工具栏关闭放大镜后放大框仍然显示。")
    toolbar_toggle.click(timeout=10000)
    if toolbar_toggle.get_attribute("aria-pressed") != "true":
        raise RuntimeError("结果图工具栏未能重新开启放大镜。")
    current_box = image.bounding_box()
    if not current_box:
        raise RuntimeError("重新开启放大镜后无法获取检测结果图位置。")
    hover_x = current_box["x"] + current_box["width"] * 0.5
    hover_y = current_box["y"] + current_box["height"] * 0.5
    page.mouse.move(hover_x - 12, hover_y - 12)
    page.mouse.move(hover_x, hover_y)
    page.wait_for_timeout(250)
    if not lens.is_visible():
        state = page.evaluate(
            """({x, y}) => {
                const target = document.elementFromPoint(x, y);
                const toggle = document.querySelector('.result-magnifier-toggle');
                const setting = document.querySelector('#magnifier-enabled-setting input[type="checkbox"]');
                return {
                    point: {x, y},
                    target: target ? `${target.tagName}.${target.className}` : null,
                    insideResultCard: Boolean(target?.closest('.primary-result-card')),
                    runtimeEnabled: document.documentElement.dataset.resultMagnifierEnabled || '',
                    togglePressed: toggle?.getAttribute('aria-pressed') || '',
                    settingChecked: setting instanceof HTMLInputElement ? setting.checked : null,
                };
            }""",
            {"x": hover_x, "y": hover_y},
        )
        raise RuntimeError(f"重新开启后检测结果放大镜未显示：{state}")

    page.screenshot(path=str(output_dir / name("03-workbench-result-magnifier.png", suffix)))
    click_tab(page, "设置")
    click_settings_section(page, "工作台")
    toggle = page.get_by_label("开启检测图悬停放大镜", exact=True)
    toggle.uncheck(timeout=10000)
    click_tab(page, "检测工作台")
    disabled_image = page.locator(".primary-result-card img").first
    disabled_box = disabled_image.bounding_box()
    if not disabled_box:
        raise RuntimeError("关闭放大镜后无法重新定位结果图。")
    page.mouse.move(
        disabled_box["x"] + disabled_box["width"] * 0.62,
        disabled_box["y"] + disabled_box["height"] * 0.62,
    )
    if page.locator(".result-magnifier.is-visible").count():
        raise RuntimeError("关闭悬停放大镜后仍然显示放大框。")
    click_tab(page, "设置")
    click_settings_section(page, "工作台")
    page.get_by_label("开启检测图悬停放大镜", exact=True).check(timeout=10000)
    click_tab(page, "检测工作台")


def capture_disabled_export_button(page, output_dir: Path, suffix: str) -> None:
    trigger = page.get_by_role("button", name="导出", exact=True)
    trigger.scroll_into_view_if_needed(timeout=10000)
    page.wait_for_timeout(250)
    if trigger.is_enabled():
        raise RuntimeError("尚未检测时导出入口不应可用。")
    style = trigger.evaluate(
        """button => {
            const value = getComputedStyle(button);
            return {
                color: value.color,
                textFill: value.webkitTextFillColor,
                background: value.backgroundColor,
                border: value.borderColor,
                opacity: value.opacity,
            };
        }"""
    )
    if (
        style["opacity"] != "1"
        or style["color"] != style["textFill"]
        or style["color"] == style["background"]
    ):
        raise RuntimeError(f"导出按钮禁用态不可读：{style}")
    trigger.screenshot(path=str(output_dir / name("01-workbench-export-disabled.png", suffix)))


def capture_report_export_menu(page, output_dir: Path, suffix: str) -> None:
    trigger = page.get_by_role("button", name="导出", exact=True)
    trigger.scroll_into_view_if_needed(timeout=10000)
    page.wait_for_timeout(400)
    if not trigger.is_enabled():
        raise RuntimeError("完成检测后导出入口仍不可用。")
    if page.locator(".report-export-status-line").count():
        raise RuntimeError("尚未导出时不应显示导出结果提示。")
    if page.locator(".result-download-bar").count():
        raise RuntimeError("检测结果图下载仍占用独立区域。")

    trigger.hover()
    hover_style = trigger.evaluate(
        """button => {
            const style = getComputedStyle(button);
            return { color: style.color, background: style.backgroundColor, opacity: style.opacity };
        }"""
    )
    if hover_style["color"] == hover_style["background"] or hover_style["opacity"] != "1":
        raise RuntimeError(f"导出按钮悬浮态不可读：{hover_style}")

    trigger.click(timeout=10000)
    popover = page.locator(
        ".report-export-dock > .report-export-dock > .styler > .report-export-popover"
    )
    popover.wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(250)
    option_ui = page.evaluate(
        """() => ({
            icons: document.querySelectorAll('.report-export-option-icon svg').length,
            descriptions: document.querySelectorAll('.report-export-option-copy small').length,
            formats: [...document.querySelectorAll('.report-export-option-format')]
                .map(node => node.textContent.trim()),
        })"""
    )
    if option_ui != {"icons": 3, "descriptions": 3, "formats": ["DOCX", "ZIP", "PNG"]}:
        raise RuntimeError(f"导出菜单信息层级未正确渲染：{option_ui}")
    geometry = page.evaluate(
        """() => {
            const trigger = document.querySelector('.report-export-menu-trigger');
            const popover = document.querySelector(
                '.report-export-dock > .report-export-dock > .styler > .report-export-popover'
            );
            if (!trigger || !popover) return null;
            const source = trigger.getBoundingClientRect();
            const target = popover.getBoundingClientRect();
            const dock = [...document.querySelectorAll('.report-export-dock')]
                .filter(candidate => candidate.contains(trigger))
                .map(candidate => candidate.getBoundingClientRect())
                .find(rect => rect.width > 0);
            const headerBottom = document.querySelector('.app-header')?.getBoundingClientRect().bottom || 0;
            return {
                beside: target.right <= source.left || target.left >= source.right,
                rightAligned: Boolean(dock && Math.abs(dock.right - source.right) <= 4),
                inViewport: target.right <= window.innerWidth && target.bottom <= window.innerHeight,
                clearsHeader: target.top >= headerBottom,
            };
        }"""
    )
    if (
        not geometry
        or not geometry["beside"]
        or not geometry["rightAligned"]
        or not geometry["inViewport"]
        or not geometry["clearsHeader"]
    ):
        raise RuntimeError(f"导出浮层位置异常：{geometry}")
    page.screenshot(path=str(output_dir / name("03-workbench-export-menu.png", suffix)))

    word_action = page.locator("button.report-export-option-word")
    word_action_count = word_action.count()
    word_action_enabled = word_action.is_enabled() if word_action_count == 1 else False
    if word_action_count != 1 or not word_action_enabled:
        raise RuntimeError(
            "Word 报告操作未处于唯一且可用的状态："
            f"count={word_action_count}, enabled={word_action_enabled}。"
        )
    word_action.click(timeout=10000)
    status = page.locator(".report-export-status-line")
    status.wait_for(state="visible", timeout=120000)
    status_text = status.inner_text()
    if "已经导出" not in status_text or ".docx" not in status_text:
        raise RuntimeError(f"导出提示内容异常：{status_text}")
    page.screenshot(path=str(output_dir / name("03-workbench-export-success.png", suffix)))

    trigger.click(timeout=10000)
    image_action = page.locator("button.report-export-option-image")
    image_action.wait_for(state="visible", timeout=5000)
    if not image_action.is_enabled():
        raise RuntimeError("结果图片操作未处于可用状态。")
    image_action.click(timeout=10000)
    page.wait_for_function(
        """() => {
            const line = document.querySelector('.report-export-status-line');
            return Boolean(line && /\.png/i.test(line.textContent || '') && !/\.docx/i.test(line.textContent || ''));
        }""",
        timeout=120000,
    )
    page.screenshot(path=str(output_dir / name("03-workbench-image-export-success.png", suffix)))


def capture(args: argparse.Namespace) -> None:
    base_url = str(args.base_url).rstrip("/")
    output_dir = Path(args.output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    example = Path(args.example).expanduser()
    suffix = str(args.suffix or "")

    check_service(base_url)

    with TemporaryDirectory(prefix="dental-ui-regression-") as temp_storage, sync_playwright() as p:
        browser = launch_chromium_with_fallback(p, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        console_errors: list[str] = []
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        try:
            wait_ready(page, base_url)
            check_horizontal_overflow(page, "桌面首页")
            save(
                page,
                output_dir,
                name("00-home-desktop.png", suffix),
                reset_scroll=True,
            )
            page.evaluate(
                """() => {
                    const shell = document.querySelector('.app-header-shell');
                    const header = shell?.querySelector('.app-header');
                    const triggerAt = shell && header
                        ? shell.getBoundingClientRect().top
                            + window.scrollY
                            + header.getBoundingClientRect().height * 2
                        : 120;
                    window.scrollTo(0, Math.ceil(triggerAt + 2));
                }"""
            )
            page.wait_for_function(
                "() => document.querySelector('.app-header')?.classList.contains('app-header-floating')",
                timeout=5000,
            )
            page.wait_for_timeout(550)
            save(page, output_dir, name("00-home-floating-nav.png", suffix))
            page.evaluate("window.scrollTo(0, 0)")
            click_tab(page, "检测工作台")
            check_workbench_tab_alignment(page)
            check_patient_toolbar_clearance(page)
            capture_empty_comparison_view(page, output_dir, suffix)
            save(
                page,
                output_dir,
                name("01-workbench-desktop.png", suffix),
                reset_scroll=True,
            )
            capture_disabled_export_button(page, output_dir, suffix)
            show_context_help(page, ".workbench-model-status")
            save(page, output_dir, name("01-workbench-help-tooltip.png", suffix))
            if check_context_help_hover_only(page, "body") < 1:
                raise RuntimeError("检测工作台未找到可审计的问号提示。")

            try:
                click_tab(page, "设置")
                click_settings_section(page, "模型")
                try:
                    click_accordion(page, "高级")
                    page.wait_for_timeout(800)
                except Exception as exc:
                    print(f"advanced accordion click skipped/failed: {exc}")
                check_visible_path_row_alignment(page, "模型路径")
                check_visible_model_row_alignment(page, "模型选择")
                try:
                    page.get_by_label("目录内模型").click(timeout=8000)
                    page.wait_for_timeout(1200)
                except Exception as exc:
                    print(f"model dropdown open failed: {exc}")
                save(page, output_dir, name("02-workbench-model-selection.png", suffix))
            except Exception as exc:
                print(f"02 screenshot failed: {exc}")
                save(page, output_dir, name("02-workbench-model-selection.png", suffix))

            check_settings_ai_subnavigation(page, output_dir, suffix)
            check_settings_round_trip_visibility(page, output_dir, suffix)
            check_storage_heading_help(page, output_dir, suffix)

            ai_was_enabled = configure_isolated_detection_session(page, Path(temp_storage))
            try:
                if not example.exists():
                    raise RuntimeError(
                        f"真实测试图片不存在：{example}。"
                        "请通过 --example 指定一张真实牙科影像后重试。"
                    )
                file_inputs = page.locator("input[type=file]")
                if file_inputs.count() == 0:
                    raise RuntimeError("no file input found")
                file_inputs.first.set_input_files(str(example))
                page.wait_for_timeout(2500)
                result_images = page.locator(".primary-result-card img")
                before_result_src = (
                    result_images.first.get_attribute("src") if result_images.count() else ""
                )
                page.get_by_role("button", name="开始分析").first.click(timeout=15000)
                page.wait_for_function(
                    """before => {
                        const image = document.querySelector('.primary-result-card img');
                        return Boolean(image && image.complete && image.naturalWidth > 0
                            && image.src && (!before || image.src !== before));
                    }""",
                    arg=before_result_src,
                    timeout=120000,
                )
                page.wait_for_timeout(12000)
                save(
                    page,
                    output_dir,
                    name("03-workbench-detection-result.png", suffix),
                    reset_scroll=True,
                )
                capture_report_export_menu(page, output_dir, suffix)
                capture_result_magnifier(page, output_dir, suffix)
            except Exception as exc:
                print(f"03 detection/upload screenshot failed: {exc}")
                save(page, output_dir, name("03-workbench-detection-result.png", suffix))

            try:
                open_ai_page_for_capture(page, ai_was_enabled)
                save(
                    page,
                    output_dir,
                    name("04-ai-chat.png", suffix),
                    reset_scroll=True,
                )
                capture_ai_single_tooltip(page, output_dir, suffix)
            except Exception as exc:
                print(f"04-ai-chat.png screenshot failed: {exc}")
                save(page, output_dir, name("04-ai-chat.png", suffix))
            check_ai_to_workbench_navigation(page, console_errors)

            for tab_name, filename in [
                ("病例记录", "05-cases.png"),
                ("检测历史", "06-history.png"),
                ("设置", "06-settings.png"),
            ]:
                detail_page = browser.new_page(viewport={"width": 1440, "height": 950})
                try:
                    wait_ready(detail_page, base_url)
                    click_tab(detail_page, tab_name)
                    if tab_name == "病例记录":
                        check_case_capture_layout(detail_page)
                    save(
                        detail_page,
                        output_dir,
                        name(filename, suffix),
                        full=tab_name == "检测历史",
                        reset_scroll=True,
                    )
                    checked_help = check_context_help_hover_only(detail_page, "body")
                    if tab_name in {"病例记录", "检测历史"} and checked_help != 1:
                        raise RuntimeError(f"{tab_name} 页头问号提示数量异常：{checked_help}")
                    if tab_name == "病例记录":
                        preview_case_export_feedback(detail_page)
                        save(
                            detail_page,
                            output_dir,
                            name("05-cases-export-feedback.png", suffix),
                        )
                    if tab_name == "设置":
                        show_context_help(detail_page, ".settings-pane-host")
                        save(
                            detail_page,
                            output_dir,
                            name("06-settings-help-tooltip.png", suffix),
                        )
                        click_settings_section(detail_page, "存储")
                        check_visible_path_row_alignment(detail_page, "存储目录")
                        save(
                            detail_page,
                            output_dir,
                            name("06-settings-storage.png", suffix),
                            full=True,
                        )
                        if check_context_help_hover_only(detail_page, "body") < 1:
                            raise RuntimeError("存储设置未找到可审计的问号提示。")
                except Exception as exc:
                    print(f"{filename} screenshot failed: {exc}")
                    save(detail_page, output_dir, name(filename, suffix))
                finally:
                    detail_page.close()

            mobile = browser.new_page(viewport={"width": 390, "height": 900}, is_mobile=True)
            try:
                wait_ready(mobile, base_url)
                check_horizontal_overflow(mobile, "移动端首页")
                save(
                    mobile,
                    output_dir,
                    name("00-home-mobile.png", suffix),
                    reset_scroll=True,
                )
                mobile.evaluate(
                    """() => {
                        const shell = document.querySelector('.app-header-shell');
                        const header = shell?.querySelector('.app-header');
                        const triggerAt = shell && header
                            ? shell.getBoundingClientRect().top
                                + window.scrollY
                                + header.getBoundingClientRect().height * 2
                            : 180;
                        window.scrollTo(0, Math.ceil(triggerAt + 2));
                    }"""
                )
                mobile.wait_for_function(
                    "() => document.querySelector('.app-header')?.classList.contains('app-header-floating')",
                    timeout=5000,
                )
                mobile.wait_for_timeout(550)
                save(mobile, output_dir, name("00-home-floating-nav-mobile.png", suffix))
                mobile.evaluate("window.scrollTo(0, 0)")
                click_tab(mobile, "检测工作台")
                check_horizontal_overflow(mobile, "移动端工作台")
                show_context_help(mobile, ".workbench-model-status")
                save(
                    mobile,
                    output_dir,
                    name("07-workbench-help-tooltip-mobile.png", suffix),
                )
                save(
                    mobile,
                    output_dir,
                    name("07-workbench-mobile.png", suffix),
                    reset_scroll=True,
                )
                click_tab(mobile, "设置")
                mobile.locator(".settings-actions").wait_for(state="visible", timeout=15000)
                check_horizontal_overflow(mobile, "移动端设置页")
                save(
                    mobile,
                    output_dir,
                    name("08-settings-mobile.png", suffix),
                    full=True,
                    reset_scroll=True,
                )
                click_tab(mobile, "病例记录")
                mobile.locator(".case-workspace .record-review-layout").wait_for(
                    state="visible", timeout=15000
                )
                check_horizontal_overflow(mobile, "移动端病例工作区")
                save(
                    mobile,
                    output_dir,
                    name("09-cases-mobile.png", suffix),
                    full=True,
                    reset_scroll=True,
                )
                click_tab(mobile, "检测历史")
                mobile.locator(".history-workspace .record-review-layout").wait_for(
                    state="visible", timeout=15000
                )
                check_horizontal_overflow(mobile, "移动端历史审阅台")
                save(
                    mobile,
                    output_dir,
                    name("10-history-mobile.png", suffix),
                    full=True,
                    reset_scroll=True,
                )
            finally:
                mobile.close()
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> None:
    capture(parse_args(argv))


if __name__ == "__main__":
    main()
