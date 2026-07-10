"""可移植的项目结构与前端资源验证入口。"""

from __future__ import annotations

from pathlib import Path
import sys

from src.dental_detection.ui_assets import CSS_BUNDLE_FILES, load_workbench_css


PROJECT_ROOT = Path(__file__).resolve().parent


def _check_css() -> list[str]:
    failures = [f"CSS 模块缺失：{path}" for path in CSS_BUNDLE_FILES if not path.is_file()]
    if failures:
        return failures
    css = load_workbench_css()
    for token in ("--shadow-card", "--success", "--warning", "--error"):
        if token not in css:
            failures.append(f"CSS 设计变量缺失：{token}")
    for rule in ("@keyframes pulse-border", "@media (max-width: 640px)", "[data-tooltip]"):
        if rule not in css:
            failures.append(f"CSS 关键规则缺失：{rule}")
    return failures


def _check_python_modules() -> list[str]:
    try:
        import app
        from src.dental_detection import advice, ai_client, conversation_store, settings_store

        app.build_app()
        assert advice.SAFETY_NOTICE
        assert ai_client.AI_REQUEST_TIMEOUT > 0
        assert conversation_store.save_conversation
        assert settings_store.AiSettings
    except Exception as exc:
        return [f"核心模块或 Gradio 应用构建失败：{exc}"]
    return []


def _check_project_files() -> list[str]:
    required = (
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "test_bugs.py",
        PROJECT_ROOT / "tests" / "test_ui_infrastructure.py",
        PROJECT_ROOT / "tests" / "test_assistant_modules.py",
        PROJECT_ROOT / "scripts" / "capture_ui_screenshots.py",
        PROJECT_ROOT / "scripts" / "pre_demo_check.py",
    )
    return [f"项目文件缺失：{path}" for path in required if not path.is_file()]


def _check_models() -> list[str]:
    from src.dental_detection.config import MODEL_REGISTRY

    failures = []
    for model_name, model_info in MODEL_REGISTRY.items():
        path = Path(model_info["path"])
        if not path.is_file():
            failures.append(f"模型文件缺失：{model_name} -> {path}")
    return failures


def main() -> int:
    checks = (
        ("前端样式", _check_css),
        ("Python 模块与应用构建", _check_python_modules),
        ("项目文件", _check_project_files),
        ("模型文件", _check_models),
    )
    failures: list[str] = []
    print("=" * 70)
    print("YOLO 牙科病变检测项目综合验证")
    print("=" * 70)
    for label, check in checks:
        current = check()
        if current:
            print(f"[FAIL] {label}")
            failures.extend(current)
        else:
            print(f"[PASS] {label}")

    if failures:
        print("\n失败详情：")
        for item in failures:
            print(f"- {item}")
        return 1

    print("\n综合验证通过。真实截图回归请使用 pre_demo_check.py --with-screenshots。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
