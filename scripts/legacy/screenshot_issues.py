"""截图检查路径输入框和下拉框问题"""
from playwright.sync_api import sync_playwright
import time

from src.dental_detection.browser_fallback import launch_chromium_with_fallback

def capture_issues():
    with sync_playwright() as p:
        browser = launch_chromium_with_fallback(p, headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            page.goto('http://127.0.0.1:7860', timeout=60000, wait_until='domcontentloaded')
            time.sleep(5)

            # 1. 截取检测工作台的路径显示
            page.screenshot(path='outputs/issue_paths_workbench.png', full_page=False)
            print("✓ 工作台截图: outputs/issue_paths_workbench.png")

            # 2. 切换到设置页面
            tab = page.get_by_role('tab', name='设置')
            if tab.is_visible():
                tab.click()
                time.sleep(2)
                page.screenshot(path='outputs/issue_settings_full.png', full_page=True)
                print("✓ 设置页面完整截图: outputs/issue_settings_full.png")

                # 3. 切换到模型选择标签
                model_tab = page.get_by_role('tab', name='模型选择')
                if model_tab.is_visible():
                    model_tab.click()
                    time.sleep(1)
                    page.screenshot(path='outputs/issue_model_selection.png', full_page=False)
                    print("✓ 模型选择页面截图: outputs/issue_model_selection.png")

                    # 聚焦到下拉框区域
                    dropdown = page.locator('label:has-text("目录内模型")').locator('..')
                    if dropdown.is_visible():
                        dropdown.scroll_into_view_if_needed()
                        time.sleep(1)
                        page.screenshot(path='outputs/issue_dropdown_detail.png', full_page=False)
                        print("✓ 下拉框详细截图: outputs/issue_dropdown_detail.png")

            # 4. 切换到对话记录标签查看存储目录
            storage_tab = page.get_by_role('tab', name='对话记录')
            if storage_tab.is_visible():
                storage_tab.click()
                time.sleep(1)
                page.screenshot(path='outputs/issue_storage_dir.png', full_page=False)
                print("✓ 存储目录截图: outputs/issue_storage_dir.png")

        except Exception as e:
            print(f"错误: {e}")
        finally:
            browser.close()

if __name__ == '__main__':
    import os
    os.makedirs('outputs', exist_ok=True)
    capture_issues()
