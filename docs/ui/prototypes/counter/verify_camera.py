"""Local simulated camera tests: no physical device is accessed."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch()
    for width in (1440, 390):
        page = browser.new_page(viewport={'width': width, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script('''
          window.demoStreams = [];
          Object.defineProperty(navigator, 'mediaDevices', {value: {
            getUserMedia: async () => {
              const canvas = document.createElement('canvas');
              canvas.width = 320; canvas.height = 240;
              canvas.getContext('2d').fillRect(0, 0, 320, 240);
              const stream = canvas.captureStream(10);
              window.demoStreams.push(stream);
              return stream;
            }
          }, configurable: true});
        ''')
        page.goto(Path(__file__).with_name('index.html').as_uri())
        page.locator('[data-person="0"]').click()
        page.locator('[data-action="collateral"]').click()
        page.locator('[data-camera-open]').click()
        expect(page.locator('#camera-capture')).to_be_enabled()
        page.locator('#camera-capture').click()
        expect(page.locator('#camera-still')).to_be_visible()
        assert page.evaluate('demoStreams[0].getTracks().every(t => t.readyState === "ended")')
        page.locator('#camera-retake').click()
        expect(page.locator('#camera-capture')).to_be_enabled()
        page.locator('#camera-capture').click()
        page.locator('#camera-use').click()
        expect(page.locator('#camera-dialog')).not_to_be_visible()
        expect(page.locator('#photo-preview img')).to_be_visible()
        assert page.locator('#photo-preview img').evaluate('(img) => img.complete && img.naturalWidth > 0')
        page.locator('[data-camera-open]').click()
        expect(page.locator('#camera-capture')).to_be_enabled()
        page.keyboard.press('Escape')
        assert page.evaluate('demoStreams.every(s => s.getTracks().every(t => t.readyState === "ended"))')
        page.evaluate('() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException("denied", "NotAllowedError"); }; }')
        page.locator('[data-camera-open]').click()
        expect(page.locator('#camera-status')).to_contain_text('permission was denied')
        with page.expect_file_chooser():
            page.locator('#camera-upload').click()
        expect(page.locator('#camera-dialog')).not_to_be_visible()
        assert not errors, errors
        page.close()
    browser.close()
print('PASS: simulated capture, retake, use, stream cleanup, permission denial, upload fallback at both widths')
