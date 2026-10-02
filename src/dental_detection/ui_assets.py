from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT


ASSET_ROOT = PROJECT_ROOT / "assets"
STYLE_ROOT = ASSET_ROOT / "styles"
ROOT_SHELL_STYLE_PATH = STYLE_ROOT / "root-shell.css"

# Loading order is part of the frontend contract: tokens first, responsive
# overrides last. New UI work should extend the narrowest matching module.
CSS_BUNDLE_FILES = (
    STYLE_ROOT / "00-tokens.css",
    STYLE_ROOT / "10-foundation.css",
    STYLE_ROOT / "15-home.css",
    STYLE_ROOT / "20-layout.css",
    STYLE_ROOT / "30-controls-results.css",
    STYLE_ROOT / "31-settings-shell.css",
    STYLE_ROOT / "32-records-compat.css",
    STYLE_ROOT / "33-settings-components.css",
    STYLE_ROOT / "35-ai-chat.css",
    STYLE_ROOT / "40-responsive.css",
    STYLE_ROOT / "45-home-responsive.css",
    STYLE_ROOT / "50-utilities.css",
)
JS_BUNDLE_FILES = (
    ASSET_ROOT / "workbench.js",
    ASSET_ROOT / "chat-workspace.js",
)


def load_text_bundle(paths: tuple[Path, ...]) -> str:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        missing_text = "、".join(str(path) for path in missing)
        raise FileNotFoundError(f"前端资源文件缺失：{missing_text}")
    return "\n\n".join(path.read_text(encoding="utf-8").rstrip() for path in paths) + "\n"


def load_workbench_css() -> str:
    return load_text_bundle(CSS_BUNDLE_FILES)


def load_root_shell_head() -> str:
    css = load_text_bundle((ROOT_SHELL_STYLE_PATH,))
    return f"<style>\n{css}</style>"


def load_workbench_js() -> str:
    return load_text_bundle(JS_BUNDLE_FILES)
