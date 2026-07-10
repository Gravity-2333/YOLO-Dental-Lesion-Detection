from __future__ import annotations

import argparse
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dental_detection.browser_fallback import launch_chromium_with_fallback

DEFAULT_BASE_URL = "http://127.0.0.1:7860"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "ai-bridge" / "screenshots" / "ui-regression"
DEFAULT_EXAMPLE = PROJECT_ROOT / "assets" / "examples" / "dental" / "示例_龋齿.png"


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
    page.get_by_role("tab", name=tab_name).first.click(timeout=15000)
    page.wait_for_timeout(1500)


def save(page, output_dir: Path, filename: str, *, full: bool = False) -> None:
    path = output_dir / filename
    page.screenshot(path=str(path), full_page=full)
    print(f"saved {path}")


def capture(args: argparse.Namespace) -> None:
    base_url = str(args.base_url).rstrip("/")
    output_dir = Path(args.output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    example = Path(args.example).expanduser()
    suffix = str(args.suffix or "")

    check_service(base_url)

    with sync_playwright() as p:
        browser = launch_chromium_with_fallback(p, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        try:
            wait_ready(page, base_url)
            save(page, output_dir, name("01-workbench-home.png", suffix))

            try:
                click_tab(page, "设置")
                click_tab(page, "模型选择")
                try:
                    page.get_by_text("高级模型路径设置", exact=True).click(timeout=5000)
                    page.wait_for_timeout(800)
                except Exception as exc:
                    print(f"advanced accordion click skipped/failed: {exc}")
                try:
                    page.get_by_label("目录内模型").click(timeout=8000)
                    page.wait_for_timeout(1200)
                except Exception as exc:
                    print(f"model dropdown open failed: {exc}")
                save(page, output_dir, name("02-workbench-model-dropdown.png", suffix))
            except Exception as exc:
                print(f"02 screenshot failed: {exc}")
                save(page, output_dir, name("02-workbench-model-dropdown.png", suffix))

            try:
                click_tab(page, "检测工作台")
                if not example.exists():
                    raise RuntimeError(f"example image not found: {example}")
                file_inputs = page.locator("input[type=file]")
                if file_inputs.count() == 0:
                    raise RuntimeError("no file input found")
                file_inputs.first.set_input_files(str(example))
                page.wait_for_timeout(2500)
                page.get_by_role("button", name="开始分析").first.click(timeout=15000)
                page.get_by_text("牙齿辅助建议").wait_for(timeout=120000)
                page.wait_for_timeout(12000)
                save(page, output_dir, name("03-workbench-after-example-or-upload.png", suffix))
            except Exception as exc:
                print(f"03 detection/upload screenshot failed: {exc}")
                save(page, output_dir, name("03-workbench-after-example-or-upload.png", suffix))

            for tab_name, filename in [
                ("AI 问答", "04-ai-chat.png"),
                ("病例记录", "05-cases.png"),
                ("设置", "06-settings.png"),
            ]:
                try:
                    click_tab(page, tab_name)
                    save(page, output_dir, name(filename, suffix))
                except Exception as exc:
                    print(f"{filename} screenshot failed: {exc}")
                    save(page, output_dir, name(filename, suffix))

            mobile = browser.new_page(viewport={"width": 390, "height": 900}, is_mobile=True)
            try:
                wait_ready(mobile, base_url)
                save(mobile, output_dir, name("07-mobile-workbench.png", suffix))
            finally:
                mobile.close()
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> None:
    capture(parse_args(argv))


if __name__ == "__main__":
    main()
