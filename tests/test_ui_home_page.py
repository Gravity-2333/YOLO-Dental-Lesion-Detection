from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
import unittest

import app
from src.dental_detection.ui_assets import CSS_BUNDLE_FILES, load_workbench_css, load_workbench_js
from src.dental_detection.ui_home_page import HOME_HERO_IMAGE_PATH, build_home_page_html


EXPECTED_HERO_SHA256 = "4aa92e8c32e7396c78291dad0589a7c22d282997b8e7a3fee22b3a06e79aaa8e"


class HomePageTests(unittest.TestCase):
    def test_home_hero_uses_the_versioned_real_dataset_copy(self) -> None:
        payload = HOME_HERO_IMAGE_PATH.read_bytes()

        self.assertEqual(payload[:2], b"\xff\xd8")
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EXPECTED_HERO_SHA256)
        self.assertIn("assets", HOME_HERO_IMAGE_PATH.parts)
        self.assertIn("branding", HOME_HERO_IMAGE_PATH.parts)

    def test_home_page_keeps_product_navigation_and_safety_contracts(self) -> None:
        html = build_home_page_html()

        self.assertIn("智能健康牙齿分析", html)
        self.assertIn('data-app-target="检测工作台"', html)
        self.assertIn('data-workbench-target="单张分析"', html)
        self.assertIn('data-workbench-target="批量分析"', html)
        self.assertIn('data-app-target="设置"', html)
        self.assertIn("专业牙科医生复核", html)
        self.assertIn("data:image/jpeg;base64,", html)
        self.assertNotIn("示例_无明显目标.png", html)

    def test_home_page_is_a_dedicated_module_and_the_default_tab(self) -> None:
        source = inspect.getsource(app.build_app)

        self.assertIn('with gr.Tab("首页"):', source)
        self.assertIn("build_home_page()", source)
        self.assertLess(source.index('with gr.Tab("首页"):'), source.index('with gr.Tab("检测工作台"):'))

    def test_home_styles_are_loaded_as_their_own_bundle_module(self) -> None:
        bundle_names = [path.name for path in CSS_BUNDLE_FILES]
        css = load_workbench_css()

        self.assertIn("15-home.css", bundle_names)
        self.assertIn("45-home-responsive.css", bundle_names)
        self.assertLess(bundle_names.index("10-foundation.css"), bundle_names.index("15-home.css"))
        self.assertLess(bundle_names.index("15-home.css"), bundle_names.index("20-layout.css"))
        self.assertLess(bundle_names.index("40-responsive.css"), bundle_names.index("45-home-responsive.css"))
        self.assertLess(bundle_names.index("45-home-responsive.css"), bundle_names.index("50-utilities.css"))
        self.assertIn(".home-hero", css)
        self.assertIn(".home-capability-grid", css)
        self.assertIn(".home-workflow", css)
        self.assertIn("@media (max-width: 640px)", css)

    def test_home_actions_use_the_shared_navigation_script(self) -> None:
        javascript = load_workbench_js()

        self.assertIn("navigateFromHome", javascript)
        self.assertIn('event.target.closest("[data-app-target]")', javascript)
        self.assertIn('activateTab(".main-tabs", pageLabel)', javascript)
        self.assertIn('activateTab(".sub-tabs", workbenchLabel)', javascript)

    def test_removed_simulated_asset_is_not_referenced_by_active_code(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        removed_asset = project_root / "assets" / "examples" / "dental" / "示例_无明显目标.png"
        screenshot_source = (project_root / "scripts" / "capture_ui_screenshots.py").read_text(
            encoding="utf-8"
        )

        self.assertFalse(removed_asset.exists())
        self.assertNotIn("示例_无明显目标.png", screenshot_source)
        self.assertIn("real-dental-panorama-test-00021.jpg", screenshot_source)
        self.assertIn('name("00-home-desktop.png", suffix)', screenshot_source)
        self.assertIn('name("00-home-mobile.png", suffix)', screenshot_source)


if __name__ == "__main__":
    unittest.main()
