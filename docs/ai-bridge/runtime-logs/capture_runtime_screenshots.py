from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time

BASE = "http://127.0.0.1:7860"
ROOT = Path.cwd()
OUT = ROOT / "docs" / "ai-bridge" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "docs" / "ai-bridge" / "runtime-logs" / "06-screenshots.log"
EXAMPLE = ROOT / "assets" / "examples" / "dental" / "示例_龋齿.png"

messages = []

def log(msg):
    print(msg)
    messages.append(msg)


def wait_ready(page):
    page.goto(BASE, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)


def click_tab(page, name):
    tab = page.get_by_role("tab", name=name).first
    tab.click(timeout=15000)
    page.wait_for_timeout(1500)


def screenshot(page, filename, full=False):
    path = OUT / filename
    page.screenshot(path=str(path), full_page=full)
    log(f"saved {path}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    page = browser.new_page(viewport={"width": 1440, "height": 950})
    try:
        wait_ready(page)
        screenshot(page, "01-workbench-home.png")

        # Model dropdown evidence: Settings -> 模型选择 -> 高级模型路径设置 -> 目录内模型 dropdown.
        try:
            click_tab(page, "设置")
            click_tab(page, "模型选择")
            try:
                page.get_by_text("高级模型路径设置", exact=True).click(timeout=5000)
                page.wait_for_timeout(800)
            except Exception as exc:
                log(f"advanced accordion click skipped/failed: {exc}")
            try:
                page.get_by_label("目录内模型").click(timeout=8000)
                page.wait_for_timeout(1200)
            except Exception as exc:
                log(f"model dropdown open failed: {exc}")
            screenshot(page, "02-workbench-model-dropdown.png")
        except Exception as exc:
            log(f"02 screenshot failed: {exc}")
            screenshot(page, "02-workbench-model-dropdown.png")

        # Run a real UI detection with a bundled synthetic example image.
        try:
            click_tab(page, "检测工作台")
            file_inputs = page.locator("input[type=file]")
            if file_inputs.count() == 0:
                raise RuntimeError("no file input found")
            file_inputs.first.set_input_files(str(EXAMPLE))
            page.wait_for_timeout(2500)
            page.get_by_role("button", name="开始分析").first.click(timeout=15000)
            # Wait for any of the completion cues rather than a fixed result count.
            page.get_by_text("牙齿辅助建议").wait_for(timeout=120000)
            page.wait_for_timeout(12000)
            screenshot(page, "03-workbench-after-example-or-upload.png")
        except Exception as exc:
            log(f"03 detection/upload screenshot failed: {exc}")
            screenshot(page, "03-workbench-after-example-or-upload.png")

        try:
            click_tab(page, "AI 问答")
            screenshot(page, "04-ai-chat.png")
        except Exception as exc:
            log(f"04 screenshot failed: {exc}")
            screenshot(page, "04-ai-chat.png")

        try:
            click_tab(page, "病例记录")
            screenshot(page, "05-cases.png")
        except Exception as exc:
            log(f"05 screenshot failed: {exc}")
            screenshot(page, "05-cases.png")

        try:
            click_tab(page, "设置")
            screenshot(page, "06-settings.png")
        except Exception as exc:
            log(f"06 screenshot failed: {exc}")
            screenshot(page, "06-settings.png")

        mobile = browser.new_page(viewport={"width": 390, "height": 900}, is_mobile=True)
        try:
            wait_ready(mobile)
            screenshot(mobile, "07-mobile-workbench.png", full=False)
        finally:
            mobile.close()
    finally:
        browser.close()

LOG.write_text("\n".join(messages) + "\n", encoding="utf-8")
