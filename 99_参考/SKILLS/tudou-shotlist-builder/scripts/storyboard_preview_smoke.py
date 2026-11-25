"""Offline DOM/interaction test of the reusable preview template, not storyboard artwork."""
import base64
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    source = (Path(__file__).resolve().parents[1] / 'templates' / 'STORYBOARD_PREVIEW.md').read_text(encoding='utf-8')
    def block(language):
        return re.search(r'```' + language + r'\n(.*?)\n```', source, re.S).group(1)
    markup = block('html')
    # A clearly non-artwork pixel fixture; never delivered as a generated board.
    pixel = base64.b64encode(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1kAAAAASUVORK5CYII=')).decode()
    replacements = dict(SB_UID='sb-test', SCENE_LABEL='组件测试，不是剧情分镜', PAGE_NUMBER='1',
                        REVISION='test-r1', STATUS_ZH='测试', ASPECT_RATIO='16:9',
                        IMAGE_DATA_URI='data:image/png;base64,' + pixel, NINE_PANEL_ALT='仅测试图片加载',
                        COVERAGE_SUMMARY='离线组件自检',
                        PANEL_ROWS='<tr><td>01</td><td><a href="#real-shot">SH01</a></td><td>测试</td><td>固定</td></tr>',
                        DRAWING_PROMPT_ZH='中文复制测试：\n保持换行与原文。')
    for key, value in replacements.items():
        markup = markup.replace('{' + key + '}', value)
    assert not re.search(r'\{[A-Z_]+\}', markup)
    html = ('<!doctype html><meta charset="utf-8"><style>' + block('css') + '</style>'
            '<article class="h3-unit" data-duration-seconds="12"><div class="prompt-block">原提示词</div></article>'
            + markup + '<div id="real-shot">真实镜头行</div><script>' + block('javascript') + '</script>')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        failures = []
        page.on('pageerror', lambda err: failures.append(str(err)))
        page.route('http://**/*', lambda route: route.abort())
        page.route('https://**/*', lambda route: route.abort())
        page.set_content(html)
        page.wait_for_function("document.querySelector('.sb-sheet').complete")
        assert page.locator('.sb-sheet').evaluate('(img) => img.naturalWidth') == 1
        assert page.locator('.h3-unit').count() == 1
        assert page.locator('.prompt-block').count() == 1
        assert page.locator('.h3-unit').get_attribute('data-duration-seconds') == '12'
        page.get_by_role('button', name='放大查看九宫格').click()
        assert page.locator('dialog').evaluate('(d) => d.open')
        page.keyboard.press('Escape')
        assert not page.locator('dialog').evaluate('(d) => d.open')
        page.get_by_role('button', name='放大查看九宫格').click()
        page.get_by_role('button', name='关闭放大图').click()
        assert not page.locator('dialog').evaluate('(d) => d.open')
        page.locator('summary').nth(0).click()
        page.get_by_role('link', name='SH01').click()
        assert page.evaluate('location.hash') == '#real-shot'
        page.locator('summary').nth(1).click()
        page.get_by_role('button', name='复制绘图提示词').click()
        page.wait_for_function("document.querySelector('.sb-copy-status').textContent.length > 0")
        status = page.locator('.sb-copy-status').inner_text()
        assert '已复制' in status or '已选中' in status
        if '已选中' in status:
            assert page.evaluate('window.getSelection().toString()') == replacements['DRAWING_PROMPT_ZH']
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.locator('.sb-sheet').bounding_box()['width'] <= 390
        assert not failures, failures
        browser.close()
    print('PASS：离线图片加载、放大/关闭/Esc、镜号跳转、中文复制降级、窄屏、视频计数隔离')


if __name__ == '__main__':
    main()
