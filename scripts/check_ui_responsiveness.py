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


def assert_history_page_settled(page, maximum: float, timings: list[tuple[str, float]]) -> None:
    started = perf_counter()
    timeout = max(10000, int(maximum * 1000))
    page.wait_for_function(
        """() => ![...document.querySelectorAll('.progress-text')]
            .some(element => /processing/i.test(element.textContent || ''))""",
        timeout=timeout,
    )
    report_select = page.get_by_label("已生成报告", exact=True)
    if report_select.count() and report_select.input_value():
        page.wait_for_function(
            """() => [...document.querySelectorAll('[data-testid="download-link"]')]
                .some(element => element.offsetParent !== null)""",
            timeout=timeout,
        )
    elapsed = perf_counter() - started
    timings.append(("检测历史完成渲染", elapsed))
    if elapsed > maximum:
        raise RuntimeError(f"检测历史完成渲染过慢：{elapsed:.2f}s > {maximum:.2f}s")


def assert_history_output_contract(page) -> None:
    history_feedback = page.get_by_label("历史反馈", exact=True).input_value()
    if not any(marker in history_feedback for marker in ("历史记录", "检测历史")):
        raise RuntimeError(f"历史反馈组件内容串位：{history_feedback[:80]}")

    history_detail = page.locator("#history-detail").inner_text()
    if "病例编号：" in history_detail:
        raise RuntimeError("历史详情错误显示为病例详情。")

    report_feedback = page.get_by_label("报告反馈", exact=True).input_value()
    if "检测时间：" in report_feedback:
        raise RuntimeError("报告反馈错误显示为历史详情。")

    report_detail = page.locator("#report-detail").inner_text()
    if "检测时间：" in report_detail or "病例编号：" in report_detail:
        raise RuntimeError("报告详情组件内容串位。")


def assert_named_button_heights(page, labels: list[tuple[str, ...]], *, tolerance: int = 1) -> None:
    heights = page.evaluate(
        """groups => groups.map(group => {
            const button = [...document.querySelectorAll('button')].find(element => {
                const rect = element.getBoundingClientRect();
                const text = (element.innerText || '').trim();
                return rect.width > 0 && rect.height > 0 && group.includes(text);
            });
            return button ? Math.round(button.getBoundingClientRect().height) : 0;
        })""",
        labels,
    )
    if any(height <= 0 for height in heights) or max(heights) - min(heights) > tolerance:
        raise RuntimeError(f"相邻操作按钮高度不一致：{heights}")


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


def assert_home_page_ready(page) -> None:
    hero = page.locator(".home-hero-image")
    hero.wait_for(state="visible", timeout=15000)
    page.wait_for_function(
        "element => Boolean(element && element.complete && element.naturalWidth > 0)",
        arg=hero.element_handle(),
        timeout=15000,
    )
    for label in ("开始单张分析", "进入批量检查"):
        button = page.get_by_role("button", name=label, exact=True)
        if button.count() != 1 or not button.is_visible():
            raise RuntimeError(f"首页入口不可用：{label}")


def assert_home_grid_and_actions_align(page, tolerance: int = 1) -> None:
    layout = page.evaluate(
        """() => {
            const buttons = [...document.querySelectorAll('.home-hero-actions .home-action')];
            const steps = [...document.querySelectorAll('.home-workflow-steps li')];
            return {
                buttons: buttons.map(element => {
                    const rect = element.getBoundingClientRect();
                    return {
                        top: rect.top,
                        bottom: rect.bottom,
                        marginBottom: parseFloat(getComputedStyle(element).marginBottom),
                    };
                }),
                steps: steps.map(element => ({
                    marginBottom: parseFloat(getComputedStyle(element).marginBottom),
                })),
            };
        }"""
    )
    if len(layout["buttons"]) != 2 or len(layout["steps"]) != 4:
        raise RuntimeError(f"首页按钮或流程步骤缺失：{layout}")
    if any(item["marginBottom"] > tolerance for item in layout["buttons"] + layout["steps"]):
        raise RuntimeError(f"首页组件仍带有 Gradio 默认下边距：{layout}")
    if (
        abs(layout["buttons"][0]["top"] - layout["buttons"][1]["top"]) > tolerance
        or abs(layout["buttons"][0]["bottom"] - layout["buttons"][1]["bottom"]) > tolerance
    ):
        raise RuntimeError(f"首页入口按钮未齐平：{layout['buttons']}")


def assert_viewer_label_contrast(page, minimum: float = 4.5) -> None:
    contrasts = page.evaluate(
        """() => {
            const parseColor = value => {
                const channels = (value.match(/[\\d.]+/g) || []).map(Number);
                return {
                    red: channels[0] || 0,
                    green: channels[1] || 0,
                    blue: channels[2] || 0,
                    alpha: channels.length > 3 ? channels[3] : 1,
                };
            };
            const luminance = color => {
                const convert = channel => {
                    const value = channel / 255;
                    return value <= 0.04045
                        ? value / 12.92
                        : Math.pow((value + 0.055) / 1.055, 2.4);
                };
                return 0.2126 * convert(color.red)
                    + 0.7152 * convert(color.green)
                    + 0.0722 * convert(color.blue);
            };
            return [...document.querySelectorAll(
                '.clinical-viewer .result-view-tabs button[role="tab"]'
            )].map(title => {
                const foreground = parseColor(getComputedStyle(title).color);
                let node = title;
                let background = {red: 255, green: 255, blue: 255, alpha: 1};
                while (node) {
                    const candidate = parseColor(getComputedStyle(node).backgroundColor);
                    if (candidate.alpha >= 0.99) {
                        background = candidate;
                        break;
                    }
                    node = node.parentElement;
                }
                const light = Math.max(luminance(foreground), luminance(background));
                const dark = Math.min(luminance(foreground), luminance(background));
                return {
                    label: (title.textContent || '').trim(),
                    ratio: (light + 0.05) / (dark + 0.05),
                };
            });
        }"""
    )
    failed = [item for item in contrasts if item["ratio"] < minimum]
    if not contrasts or failed:
        raise RuntimeError(f"检测查看器标签对比度不足：{contrasts}")


def assert_workbench_tab_rows_aligned(page, tolerance: int = 1) -> None:
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
    top_delta = abs(rows[0]["top"] - rows[1]["top"])
    height_delta = abs(rows[0]["height"] - rows[1]["height"])
    if top_delta > tolerance or height_delta > tolerance:
        raise RuntimeError(f"工作台选项卡未对齐：{rows}")


def assert_workbench_tabs_have_no_full_width_rule(page) -> None:
    rules = page.evaluate(
        """() => ['.sub-tabs', '.result-view-tabs'].map(selector => {
            const row = document.querySelector(`${selector} [role="tablist"]`);
            const wrapper = document.querySelector(`${selector} > .tab-wrapper`);
            if (!row || !wrapper) return null;
            const style = getComputedStyle(row);
            const after = getComputedStyle(row, '::after');
            const wrapperStyle = getComputedStyle(wrapper);
            return {
                selector,
                borderBottom: parseFloat(style.borderBottomWidth),
                afterDisplay: after.display,
                afterHeight: parseFloat(after.height) || 0,
                wrapperMarginBottom: parseFloat(wrapperStyle.marginBottom),
                wrapperPaddingBottom: parseFloat(wrapperStyle.paddingBottom),
            };
        })"""
    )
    if any(item is None for item in rules):
        raise RuntimeError(f"工作台选项卡行缺失：{rules}")
    if any(
        item["borderBottom"] > 0
        or item["afterDisplay"] != "none"
        or item["wrapperMarginBottom"] > 0
        or item["wrapperPaddingBottom"] > 0
        for item in rules
    ):
        raise RuntimeError(f"工作台选项卡仍有整行细线：{rules}")


def assert_example_dropdown_has_single_frame(page) -> None:
    details = page.evaluate(
        """() => {
            const input = document.querySelector('input[aria-label="选择示例"]');
            const inner = input?.closest('.secondary-wrap');
            const outer = input?.closest('.wrap-inner');
            if (!input || !inner || !outer) return null;
            input.focus();
            return {
                outerBorder: parseFloat(getComputedStyle(outer).borderTopWidth),
                innerBorder: parseFloat(getComputedStyle(inner).borderTopWidth),
                inputShadow: getComputedStyle(input).boxShadow,
            };
        }"""
    )
    if details is None:
        raise RuntimeError("真实示例下拉框缺失")
    if details["outerBorder"] > 0 or details["innerBorder"] < 1 or details["inputShadow"] != "none":
        raise RuntimeError(f"真实示例下拉框仍存在双层边界：{details}")


def assert_patient_toolbar_does_not_overlap_tabs(page, minimum_gap: int = 8) -> None:
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
    gap = layout["tabsTop"] - layout["patientBottom"]
    if gap < minimum_gap:
        raise RuntimeError(f"分析选项卡遮挡患者选择框：{layout}，间距 {gap}px")
    if (
        abs(layout["patientTop"] - layout["buttonTop"]) > 1
        or abs(layout["patientBottom"] - layout["buttonBottom"]) > 1
    ):
        raise RuntimeError(f"患者选择框与清空会话按钮未对齐：{layout}")
    if layout["outerBorder"] > 0 or layout["innerBorder"] < 1:
        raise RuntimeError(f"患者选择框仍存在双层边框：{layout}")


def assert_rows_aligned(
    page,
    label: str,
    selector: str = ".path-row",
    *,
    tolerance: int = 1,
) -> None:
    deltas = page.evaluate(
        """({selector, modelRow}) => [...document.querySelectorAll(selector)]
            .filter(row => {
                const rect = row.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            })
            .map(row => {
                const controls = modelRow
                    ? [
                        [...row.children].find(element => element.matches('button, .secondary-action')),
                        [...row.children].find(element => element.querySelector('.secondary-wrap')),
                    ]
                    : [...row.children]
                        .map(element => element.matches('button,input,textarea,select')
                            ? element : element.querySelector('button,input,textarea,select'));
                const bottoms = controls.filter(Boolean).map(element => Math.round(element.getBoundingClientRect().bottom));
                return bottoms.length ? Math.max(...bottoms) - Math.min(...bottoms) : 0;
            })""",
        {"selector": selector, "modelRow": "model-row" in selector},
    )
    if any(delta > tolerance for delta in deltas):
        raise RuntimeError(f"{label} 工具行未对齐：{deltas}")


def assert_path_rows_aligned(page, label: str) -> None:
    assert_rows_aligned(page, label, ".path-row")


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
        assert_no_page_overflow(page, "桌面首页")
        assert_home_page_ready(page)
        assert_home_grid_and_actions_align(page)
        timed_click(page, top_tab(page, "检测工作台"), "进入检测工作台", args.max_seconds, timings)
        assert_no_page_overflow(page, "桌面工作台")
        assert_viewer_label_contrast(page)
        assert_workbench_tab_rows_aligned(page)
        assert_workbench_tabs_have_no_full_width_rule(page)
        assert_patient_toolbar_does_not_overlap_tabs(page)
        ensure_accordion_open(page, accordion(page, "真实牙片示例"), "展开真实牙片示例", args.max_seconds, timings)
        assert_example_dropdown_has_single_frame(page)

        names = ["首页", "检测工作台", "AI 问答", "病例记录", "检测历史", "设置"]
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
                    assert_named_button_heights(
                        page,
                        [("保存病例", "完成检测后可保存"), ("刷新记录",)],
                    )
                if cycle == 0 and name == "检测历史":
                    timed_wait_for_value(
                        page,
                        page.get_by_label("历史反馈", exact=True),
                        "检测历史首次加载",
                        args.max_seconds,
                        timings,
                    )
                    assert_history_page_settled(page, args.max_seconds, timings)
                    assert_history_output_contract(page)

        timed_click(page, top_tab(page, "AI 问答"), "进入 AI 问答", args.max_seconds, timings)
        runtime_status = page.locator(".ai-runtime-strip").first
        runtime_status.wait_for(state="visible")
        runtime_text = runtime_status.inner_text()
        if not all(label in runtime_text for label in ("检测上下文", "AI 配置", "接口与模型")):
            raise RuntimeError(f"AI 运行状态信息不完整：{runtime_text}")
        timed_click(
            page,
            accordion(page, "最近对话"),
            "展开最近对话",
            args.max_seconds,
            timings,
        )
        conversation_select = page.get_by_label("本地对话记录", exact=True)
        if conversation_select.input_value():
            timed_click(
                page,
                page.get_by_role("button", name="加载对话", exact=True),
                "加载本地对话",
                args.max_seconds,
                timings,
            )
            timed_wait_for_value(
                page,
                page.get_by_label("对话记录反馈", exact=True),
                "本地对话加载完成",
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
                assert_rows_aligned(page, "模型选择", ".model-row", tolerance=10)
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

        for name in ["首页", "设置", "检测工作台", "检测历史", "病例记录", "AI 问答"]:
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
        assert_home_page_ready(mobile)
        assert_no_page_overflow(mobile, "移动端首页")
        top_tab(mobile, "检测工作台").click(timeout=10000)
        wait_for_ui(mobile)
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
