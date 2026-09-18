"""创建专门的按钮对齐检查脚本"""
from playwright.sync_api import sync_playwright
import time

def check_button_alignment():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            page.goto('http://127.0.0.1:7860', timeout=60000, wait_until='domcontentloaded')
            time.sleep(5)

            # 截取检测工作台底部的报告导出区域
            page.screenshot(path='outputs/alignment_check_workbench.png', full_page=False)
            print("✓ 工作台截图: outputs/alignment_check_workbench.png")

            # 找到报告路径输入框和按钮，截取局部
            report_section = page.locator('textarea[aria-label="报告路径"]').locator('..')
            if report_section.is_visible():
                report_section.scroll_into_view_if_needed()
                time.sleep(1)
                # 截取包含该区域的较大范围
                bbox = report_section.bounding_box()
                if bbox:
                    page.screenshot(
                        path='outputs/alignment_detail_report.png',
                        clip={'x': max(0, bbox['x'] - 50), 'y': max(0, bbox['y'] - 20),
                              'width': min(1920, bbox['width'] + 100), 'height': bbox['height'] + 40}
                    )
                    print("✓ 报告区域详细截图: outputs/alignment_detail_report.png")

            # 切换到AI问答页面
            tab = page.get_by_role('tab', name='AI 问答')
            if tab.is_visible():
                tab.click()
                time.sleep(2)

                # 截取发送按钮区域
                chat_input_section = page.locator('textarea[aria-label="继续提问"]').locator('../..')
                if chat_input_section.is_visible():
                    chat_input_section.scroll_into_view_if_needed()
                    time.sleep(1)
                    bbox = chat_input_section.bounding_box()
                    if bbox:
                        page.screenshot(
                            path='outputs/alignment_detail_chat.png',
                            clip={'x': max(0, bbox['x'] - 50), 'y': max(0, bbox['y'] - 20),
                                  'width': min(1920, bbox['width'] + 100), 'height': bbox['height'] + 40}
                        )
                        print("✓ 发送按钮区域详细截图: outputs/alignment_detail_chat.png")

                # 截取导出对话区域
                export_section = page.locator('textarea[aria-label="导出路径"]').locator('../..')
                if export_section.is_visible():
                    export_section.scroll_into_view_if_needed()
                    time.sleep(1)
                    bbox = export_section.bounding_box()
                    if bbox:
                        page.screenshot(
                            path='outputs/alignment_detail_export.png',
                            clip={'x': max(0, bbox['x'] - 50), 'y': max(0, bbox['y'] - 20),
                                  'width': min(1920, bbox['width'] + 100), 'height': bbox['height'] + 40}
                        )
                        print("✓ 导出对话区域详细截图: outputs/alignment_detail_export.png")

        except Exception as e:
            print(f"错误: {e}")
        finally:
            browser.close()

if __name__ == '__main__':
    import os
    os.makedirs('outputs', exist_ok=True)
    check_button_alignment()
