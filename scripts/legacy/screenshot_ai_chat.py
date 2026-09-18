"""截图AI问答页面的详细视图"""
from playwright.sync_api import sync_playwright
import time

from src.dental_detection.browser_fallback import launch_chromium_with_fallback

def capture_ai_chat_detail():
    with sync_playwright() as p:
        browser = launch_chromium_with_fallback(p, headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            # 访问Gradio应用
            page.goto('http://127.0.0.1:7860', timeout=60000, wait_until='domcontentloaded')
            time.sleep(5)

            # 点击AI问答标签
            tab = page.get_by_role('tab', name='AI 问答')
            if tab.is_visible():
                tab.click()
                time.sleep(2)

                # 截取AI问答页面
                page.screenshot(path='outputs/ai_chat_detail.png', full_page=False)
                print("✓ 已保存AI问答页面截图: outputs/ai_chat_detail.png")

                # 聚焦到输入区域并截图
                chat_input = page.locator('textarea[aria-label="继续提问"]')
                if chat_input.is_visible():
                    chat_input.scroll_into_view_if_needed()
                    time.sleep(1)
                    page.screenshot(path='outputs/ai_chat_input_area.png', full_page=False)
                    print("✓ 已保存输入区域截图: outputs/ai_chat_input_area.png")

                # 获取页面HTML结构用于分析
                chat_section = page.locator('.chat-card').first
                if chat_section.is_visible():
                    html = chat_section.inner_html()
                    with open('outputs/ai_chat_structure.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    print("✓ 已保存HTML结构: outputs/ai_chat_structure.html")

        except Exception as e:
            print(f"错误: {e}")
        finally:
            browser.close()

if __name__ == '__main__':
    import os
    os.makedirs('outputs', exist_ok=True)
    capture_ai_chat_detail()
