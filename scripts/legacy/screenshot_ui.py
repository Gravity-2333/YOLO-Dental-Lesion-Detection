"""使用playwright截图查看Gradio界面"""
from playwright.sync_api import sync_playwright
import time

from src.dental_detection.browser_fallback import launch_chromium_with_fallback

def capture_gradio_ui():
    with sync_playwright() as p:
        browser = launch_chromium_with_fallback(p, headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            # 访问Gradio应用
            page.goto('http://127.0.0.1:7860', timeout=60000, wait_until='domcontentloaded')
            time.sleep(5)

            # 截取完整页面
            page.screenshot(path='outputs/screenshot_full.png', full_page=True)
            print("✓ 已保存完整页面截图: outputs/screenshot_full.png")

            # 截取首屏
            page.screenshot(path='outputs/screenshot_viewport.png', full_page=False)
            print("✓ 已保存首屏截图: outputs/screenshot_viewport.png")

            # 点击不同的标签页并截图
            tabs = ['检测工作台', 'AI 问答', '病例记录', '设置']
            for i, tab_name in enumerate(tabs):
                try:
                    # 尝试点击标签
                    tab = page.get_by_role('tab', name=tab_name)
                    if tab.is_visible():
                        tab.click()
                        time.sleep(1)
                        page.screenshot(path=f'outputs/screenshot_tab_{i}_{tab_name}.png', full_page=True)
                        print(f"✓ 已保存'{tab_name}'标签截图: outputs/screenshot_tab_{i}_{tab_name}.png")
                except Exception as e:
                    print(f"× 无法截取'{tab_name}'标签: {e}")

        except Exception as e:
            print(f"错误: {e}")
        finally:
            browser.close()

if __name__ == '__main__':
    import os
    os.makedirs('outputs', exist_ok=True)
    capture_gradio_ui()
