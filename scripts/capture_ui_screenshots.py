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


def click_accordion(page, label: str) -> None:
    page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}")).first.click(timeout=15000)
    page.wait_for_timeout(800)


def configure_isolated_detection_session(page, storage_dir: Path) -> bool:
    click_tab(page, "设置")
    click_accordion(page, "AI 接口")
    ai_enabled = page.get_by_label("启用 AI 建议与问答")
    if ai_enabled.count() != 1:
        raise RuntimeError("截图会话无法唯一定位 AI 开关，已停止以避免外部请求。")
    ai_was_enabled = ai_enabled.is_checked()
    if ai_was_enabled:
        ai_enabled.uncheck(timeout=10000)

    click_accordion(page, "存储与隐私")
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
        ai_enabled = page.get_by_label("启用 AI 建议与问答")
        if not ai_enabled.is_visible():
            click_accordion(page, "AI 接口")
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
        try:
            wait_ready(page, base_url)
            check_horizontal_overflow(page, "桌面首页")
            save(
                page,
                output_dir,
                name("00-home-desktop.png", suffix),
                reset_scroll=True,
            )
            page.get_by_role("button", name="Test", exact=True).hover()
            page.wait_for_function(
                "() => getComputedStyle(document.querySelector('.app-nav-submenu-level-1')).visibility === 'visible'",
                timeout=5000,
            )
            page.wait_for_timeout(300)
            save(page, output_dir, name("00-home-test-menu.png", suffix))
            page.get_by_role("button", name="系统页面", exact=True).hover()
            page.wait_for_function(
                "() => getComputedStyle(document.querySelector('.app-nav-submenu-level-2')).visibility === 'visible'",
                timeout=5000,
            )
            page.wait_for_timeout(350)
            save(page, output_dir, name("00-home-test-submenu.png", suffix))
            page.mouse.move(1, 1)
            page.keyboard.press("Escape")
            page.evaluate("document.activeElement?.blur()")
            page.evaluate(
                """() => {
                    const shell = document.querySelector('.app-header-shell');
                    const triggerAt = shell
                        ? shell.getBoundingClientRect().bottom + window.scrollY
                        : 120;
                    window.scrollTo(0, Math.ceil(triggerAt + 2));
                }"""
            )
            page.wait_for_function(
                "() => document.querySelector('.app-header')?.classList.contains('app-header-floating')",
                timeout=5000,
            )
            page.wait_for_timeout(350)
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

            try:
                click_tab(page, "设置")
                click_accordion(page, "模型与推理")
                try:
                    page.get_by_text("高级模型路径设置", exact=True).click(timeout=5000)
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
                        click_accordion(detail_page, "存储与隐私")
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
                        const triggerAt = shell
                            ? shell.getBoundingClientRect().bottom + window.scrollY
                            : 180;
                        window.scrollTo(0, Math.ceil(triggerAt + 2));
                    }"""
                )
                mobile.wait_for_function(
                    "() => document.querySelector('.app-header')?.classList.contains('app-header-floating')",
                    timeout=5000,
                )
                mobile.wait_for_timeout(350)
                save(mobile, output_dir, name("00-home-floating-nav-mobile.png", suffix))
                mobile.evaluate("window.scrollTo(0, 0)")
                click_tab(mobile, "检测工作台")
                check_horizontal_overflow(mobile, "移动端工作台")
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
            finally:
                mobile.close()
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> None:
    capture(parse_args(argv))


if __name__ == "__main__":
    main()
