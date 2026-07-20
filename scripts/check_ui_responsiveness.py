from __future__ import annotations

import argparse
from pathlib import Path
from statistics import quantiles
import re
import sys
from time import perf_counter
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dental_detection.browser_fallback import launch_chromium_with_fallback
from src.dental_detection.ui_constants import MODEL_MODE_COMPARE, MODEL_MODE_SINGLE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查主要页面切换、重组件展开和移动端布局响应速度。")
    parser.add_argument("--base-url", default="http://127.0.0.1:7860")
    parser.add_argument("--max-seconds", type=float, default=3.0)
    parser.add_argument("--cycles", type=int, default=3)
    return parser.parse_args()


def wait_for_ui(page) -> None:
    page.evaluate(
        """() => new Promise(resolve => requestAnimationFrame(
            () => requestAnimationFrame(resolve)
        ))"""
    )


def timed_click(page, locator, label: str, maximum: float, timings: list[tuple[str, float]]) -> None:
    started = perf_counter()
    locator.click(timeout=max(10000, int(maximum * 3000)))
    wait_for_ui(page)
    elapsed = perf_counter() - started
    timings.append((label, elapsed))
    if elapsed > maximum:
        raise RuntimeError(f"{label} 响应过慢：{elapsed:.2f}s > {maximum:.2f}s")


def timed_wait_for_value(page, locator, label: str, maximum: float, timings: list[tuple[str, float]]) -> None:
    started = perf_counter()
    page.wait_for_function(
        "element => Boolean(element && element.value)",
        arg=locator.element_handle(),
        timeout=max(10000, int(maximum * 1000)),
    )
    elapsed = perf_counter() - started
    timings.append((label, elapsed))
    if elapsed > maximum:
        raise RuntimeError(f"{label} 完成过慢：{elapsed:.2f}s > {maximum:.2f}s")


def ensure_accordion_open(page, locator, label: str, maximum: float, timings: list[tuple[str, float]]) -> None:
    if locator.get_attribute("aria-expanded") != "true":
        timed_click(page, locator, label, maximum, timings)


def top_tab(page, name: str):
    return page.get_by_role("tab", name=name, exact=True).first


def accordion(page, name: str):
    return page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}")).first


def first_visible(matches, name: str):
    for index in range(matches.count()):
        candidate = matches.nth(index)
        if candidate.is_visible():
            return candidate
    raise RuntimeError(f"未找到可见控件：{name}")


def visible_radio(page, value: str):
    matches = page.locator('input[type="radio"]')
    visible_values = []
    for index in range(matches.count()):
        candidate = matches.nth(index)
        if candidate.is_visible():
            visible_values.append(candidate.input_value())
            if candidate.input_value() == value:
                return candidate
    raise RuntimeError(f"未找到可见单选项：{value}；可见值={visible_values}")


def has_visible_radio(page, value: str) -> bool:
    matches = page.locator('input[type="radio"]')
    return any(
        matches.nth(index).is_visible() and matches.nth(index).input_value() == value
        for index in range(matches.count())
    )


def assert_no_page_overflow(page, label: str) -> None:
    size = page.evaluate(
        "() => ({client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
    )
    if size["scroll"] > size["client"] + 2:
        raise RuntimeError(f"{label} 横向溢出：{size['scroll']} > {size['client']}")


def assert_path_rows_aligned(page, label: str) -> None:
    deltas = page.evaluate(
        """() => [...document.querySelectorAll('.path-row')]
            .filter(row => row.offsetParent)
            .map(row => {
                const controls = [...row.children]
                    .map(element => element.matches('button,input,textarea')
                        ? element : element.querySelector('button,input,textarea'))
                    .filter(Boolean);
                const bottoms = controls.map(element => Math.round(element.getBoundingClientRect().bottom));
                return bottoms.length ? Math.max(...bottoms) - Math.min(...bottoms) : 0;
            })"""
    )
    if any(delta > 1 for delta in deltas):
        raise RuntimeError(f"{label} 路径工具行未对齐：{deltas}")


def percentile_95(values: list[float]) -> float:
    if len(values) < 2:
        return values[0] if values else 0.0
    return quantiles(values, n=20, method="inclusive")[18]


def main() -> int:
    args = parse_args()
    base_url = str(args.base_url).rstrip("/")
    with urlopen(base_url, timeout=10) as response:
        if int(getattr(response, "status", 200)) >= 400:
            raise RuntimeError(f"服务返回 HTTP {response.status}")

    timings: list[tuple[str, float]] = []
    with sync_playwright() as playwright:
        browser = launch_chromium_with_fallback(playwright, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        page.set_default_timeout(10000)
        page.goto(base_url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(6000)
        assert_no_page_overflow(page, "桌面工作台")

        names = ["检测工作台", "AI 问答", "病例记录", "检测历史", "设置"]
        for cycle in range(max(1, int(args.cycles))):
            for name in names:
                timed_click(page, top_tab(page, name), f"主导航 {cycle + 1}/{name}", args.max_seconds, timings)
                if cycle == 0 and name == "病例记录":
                    timed_wait_for_value(
                        page,
                        page.get_by_label("病例反馈", exact=True),
                        "病例记录首次加载",
                        args.max_seconds,
                        timings,
                    )
                if cycle == 0 and name == "检测历史":
                    timed_wait_for_value(
                        page,
                        page.get_by_label("历史反馈", exact=True),
                        "检测历史首次加载",
                        args.max_seconds,
                        timings,
                    )

        timed_click(page, top_tab(page, "设置"), "进入设置", args.max_seconds, timings)
        for name in ["模型与推理", "模型说明", "AI 接口", "存储与隐私"]:
            timed_click(page, accordion(page, name), f"展开设置/{name}", args.max_seconds, timings)
            if name == "模型与推理":
                timed_click(
                    page,
                    accordion(page, "高级模型路径设置"),
                    "展开高级模型路径",
                    args.max_seconds,
                    timings,
                )
                assert_path_rows_aligned(page, "模型路径")
            if name == "存储与隐私":
                assert_path_rows_aligned(page, "存储路径")

        timed_click(page, top_tab(page, "病例记录"), "进入病例记录", args.max_seconds, timings)
        timed_click(
            page,
            accordion(page, "结构化病例列表"),
            "展开结构化病例列表",
            args.max_seconds,
            timings,
        )
        timed_click(page, top_tab(page, "检测历史"), "进入检测历史", args.max_seconds, timings)
        for name in ["结构化历史列表", "结构化报告列表"]:
            timed_click(page, accordion(page, name), f"展开{name}", args.max_seconds, timings)

        for name in ["设置", "检测工作台", "检测历史", "病例记录", "AI 问答"]:
            timed_click(page, top_tab(page, name), f"重组件后导航/{name}", args.max_seconds, timings)
        assert_no_page_overflow(page, "重组件展开后的桌面页面")

        timed_click(page, top_tab(page, "设置"), "进入设置/模式回归", args.max_seconds, timings)
        model_accordion = accordion(page, "模型与推理")
        ensure_accordion_open(page, model_accordion, "展开设置/模式回归", args.max_seconds, timings)
        if not has_visible_radio(page, MODEL_MODE_COMPARE):
            # Gradio may restore the accordion's stale aria state after a tab switch;
            # one guarded retry keeps this check focused on the visible control.
            timed_click(page, model_accordion, "重试展开设置/模式回归", args.max_seconds, timings)
        compare_toggle = first_visible(page.get_by_label("允许对比模型模式", exact=True), "允许对比模型模式")
        if compare_toggle.is_checked() is False:
            timed_click(page, compare_toggle, "启用对比模型模式", args.max_seconds, timings)
        compare_radio = visible_radio(page, MODEL_MODE_COMPARE)
        if compare_radio.is_checked() is False:
            timed_click(page, compare_radio, "切换双模型对比", args.max_seconds, timings)
        single_radio = visible_radio(page, MODEL_MODE_SINGLE)
        if single_radio.is_checked() is False:
            timed_click(page, single_radio, "切回单模型检测", args.max_seconds, timings)

        mobile = browser.new_page(viewport={"width": 390, "height": 900}, is_mobile=True)
        mobile.goto(base_url, wait_until="domcontentloaded", timeout=90000)
        mobile.wait_for_timeout(4000)
        assert_no_page_overflow(mobile, "移动端工作台")
        mobile.close()
        browser.close()

    values = [elapsed for _, elapsed in timings]
    print(f"PASS UI responsiveness: checks={len(values)} max={max(values):.3f}s p95={percentile_95(values):.3f}s")
    for label, elapsed in sorted(timings, key=lambda item: item[1], reverse=True)[:8]:
        print(f"  {elapsed:.3f}s  {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
