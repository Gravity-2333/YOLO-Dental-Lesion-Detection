from __future__ import annotations

import unittest

from src.dental_detection.ui_assets import CSS_BUNDLE_FILES, load_workbench_css, load_workbench_js
from src.dental_detection.ui_contracts import (
    COMMON_OUTPUT_KEYS,
    COMMON_OUTPUT_QUALITY_INDEX,
    common_output_values,
)


class UiAssetTests(unittest.TestCase):
    def test_css_bundle_is_complete_and_ordered(self) -> None:
        self.assertTrue(all(path.is_file() for path in CSS_BUNDLE_FILES))
        css = load_workbench_css()
        self.assertLess(css.index(":root"), css.index(".gradio-container"))
        self.assertIn("@media (max-width: 640px)", css)

    def test_javascript_bundle_loads(self) -> None:
        self.assertIn("MutationObserver", load_workbench_js())


class UiContractTests(unittest.TestCase):
    def test_common_output_contract_preserves_declared_order(self) -> None:
        values = {key: key for key in reversed(COMMON_OUTPUT_KEYS)}
        self.assertEqual(common_output_values(values), COMMON_OUTPUT_KEYS)

    def test_common_output_contract_rejects_missing_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "缺少"):
            common_output_values({})

    def test_quality_index_is_derived_from_contract(self) -> None:
        self.assertEqual(COMMON_OUTPUT_KEYS[COMMON_OUTPUT_QUALITY_INDEX], "quality")


if __name__ == "__main__":
    unittest.main()
