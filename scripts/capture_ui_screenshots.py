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
    section = page.get_by_role("radio", name=label, exact=True)
    if section.count() == 0:
        raise RuntimeError(f"无法定位设置栏目：{label}")
    section.first.click(timeout=15000)
    page.wait_for_timeout(800)


def configure_isolated_detection_session(page, storage_dir: Path) -> bool:
    click_tab(page, "设置")
    click_settings_section(page, "AI")
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
        click_settings_section(page, "AI")
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


def show_context_help(page, scope: str, *, focus: bool = False) -> None:
    help_root = page.locator(f"{scope} .context-help:visible").first
    trigger = help_root.locator(".context-help-trigger")
    if focus:
        trigger.focus(timeout=10000)
    else:
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


def capture_result_magnifier(page, output_dir: Path, suffix: str) -> None:
    stage = page.locator(".result-image-stage").first
    image = stage.locator(".primary-result-card img").first
    stage.scroll_into_view_if_needed(timeout=10000)
    box = image.bounding_box()
    if not box:
        raise RuntimeError("无法获取检测结果图位置。")

    page.mouse.move(box["x"] + box["width"] * 0.56, box["y"] + box["height"] * 0.58)
    lens = stage.locator(".result-magnifier.is-visible")
    lens.wait_for(state="visible", timeout=5000)
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

    overlay_valid = page.evaluate(
        """() => {
            const stage = document.querySelector('.result-image-stage');
            const legend = stage?.querySelector('.compact-result-legend');
            if (!stage || !legend) return false;
            const outer = stage.getBoundingClientRect();
            const inner = legend.getBoundingClientRect();
            return inner.width > 0 && inner.height > 0
                && inner.left >= outer.left && inner.right <= outer.right
                && inner.top >= outer.top && inner.bottom <= outer.bottom;
        }"""
    )
    if not overlay_valid:
        raise RuntimeError("结果图例未正确收纳在图片区域内。")

    stage.screenshot(path=str(output_dir / name("03-workbench-result-magnifier.png", suffix)))
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


def capture_report_export_menu(page, output_dir: Path, suffix: str) -> None:
    trigger = page.get_by_role("button", name="导出报告", exact=True)
    trigger.scroll_into_view_if_needed(timeout=10000)
    page.wait_for_timeout(400)
    if not trigger.is_enabled():
        raise RuntimeError("完成检测后导出报告入口仍不可用。")
    if page.locator(".report-export-status-line").count():
        raise RuntimeError("尚未导出时不应显示导出结果提示。")

    trigger.click(timeout=10000)
    popover = page.locator(
        ".report-export-dock > .report-export-dock > .styler > .report-export-popover"
    )
    popover.wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(250)
    geometry = page.evaluate(
        """() => {
            const trigger = document.querySelector('.report-export-menu-trigger');
            const popover = document.querySelector(
                '.report-export-dock > .report-export-dock > .styler > .report-export-popover'
            );
            if (!trigger || !popover) return null;
            const source = trigger.getBoundingClientRect();
            const target = popover.getBoundingClientRect();
            return {
                toRight: target.left >= source.right,
                inViewport: target.right <= window.innerWidth && target.bottom <= window.innerHeight,
            };
        }"""
    )
    if not geometry or not geometry["toRight"] or not geometry["inViewport"]:
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
            save(
                page,
                output_dir,
                name("01-workbench-desktop.png", suffix),
                reset_scroll=True,
            )
            show_context_help(page, ".workbench-model-status")
            save(page, output_dir, name("01-workbench-help-tooltip.png", suffix))

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
                    save(
                        detail_page,
                        output_dir,
                        name(filename, suffix),
                        full=tab_name == "检测历史",
                        reset_scroll=True,
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
                show_context_help(mobile, ".workbench-model-status", focus=True)
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
