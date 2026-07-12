from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:7860"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pre-demo checks for the YOLO Dental Lesion Detection project.")
    parser.add_argument("--skip-slow", action="store_true", help="Skip slower broad checks: test_bugs.py and verify_optimization.py.")
    parser.add_argument("--with-screenshots", action="store_true", help="Also capture UI regression screenshots. Requires the Gradio service.")
    parser.add_argument("--screenshot-output", default="docs/ai-bridge/screenshots/pre-demo", help="Output directory for screenshots.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Gradio service URL used for screenshot checks.")
    return parser.parse_args(argv)


def run_command(label: str, command: list[str]) -> tuple[bool, int]:
    print(f"\n[RUN] {label}")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode == 0:
        print(f"[PASS] {label}")
        return True, 0
    print(f"[FAIL] {label} exit={completed.returncode}")
    return False, completed.returncode


def check_service(base_url: str) -> tuple[bool, str]:
    try:
        with urlopen(base_url, timeout=10) as response:
            status = int(getattr(response, "status", 200))
    except (URLError, TimeoutError, OSError) as exc:
        return False, f"无法访问 {base_url}。请先运行 start_project.bat 启动服务后再带截图检查。原始错误：{exc}"
    if status >= 400:
        return False, f"访问 {base_url} 返回 HTTP {status}，请确认服务状态正常。"
    return True, f"HTTP {status}"


def build_commands(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    python = sys.executable
    commands = [
        ("模块化单元测试", [python, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("模型加载检查", [python, "scripts/check_model.py"]),
        ("模型 UI helper 检查", [python, "scripts/check_model_ui_helpers.py"]),
        ("导出 helper 检查", [python, "scripts/check_export_helpers.py"]),
    ]
    if not args.skip_slow:
        commands.extend(
            [
                ("兼容回归测试 test_bugs.py", [python, "test_bugs.py"]),
                ("综合优化验证 verify_optimization.py", [python, "verify_optimization.py"]),
            ]
        )
    return commands


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    failures: list[str] = []

    for label, command in build_commands(args):
        ok, _ = run_command(label, command)
        if not ok:
            failures.append(label)

    if args.with_screenshots:
        ok, message = check_service(str(args.base_url).rstrip("/"))
        if not ok:
            print(f"\n[FAIL] 截图前服务检查：{message}")
            failures.append("截图前服务检查")
        else:
            print(f"\n[PASS] 截图前服务检查：{message}")
            responsive_ok, _ = run_command(
                "UI 响应与布局压力检查",
                [
                    sys.executable,
                    "scripts/check_ui_responsiveness.py",
                    "--base-url",
                    str(args.base_url).rstrip("/"),
                ],
            )
            if not responsive_ok:
                failures.append("UI 响应与布局压力检查")
            screenshot_ok, _ = run_command(
                "UI 截图回归",
                [
                    sys.executable,
                    "scripts/capture_ui_screenshots.py",
                    "--base-url",
                    str(args.base_url).rstrip("/"),
                    "--output",
                    str(args.screenshot_output),
                ],
            )
            if not screenshot_ok:
                failures.append("UI 截图回归")

    print("\n" + "=" * 70)
    if failures:
        print("PRE-DEMO CHECK FAILED")
        print("失败项：")
        for item in failures:
            print(f"- {item}")
        print("=" * 70)
        return 1
    print("PRE-DEMO CHECK PASS")
    print(f"skip_slow={args.skip_slow}; with_screenshots={args.with_screenshots}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
