"""Synthetic browser checks: no hardware cameras, customer records or uploads."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHOICES = '<option value="user">Front camera</option><option value="environment">Rear camera</option>'
FAKE_MEDIA = r"""
window.requests = []; window.tracks = [];
Object.defineProperty(window, 'isSecureContext', {value: true});
Object.defineProperty(navigator, 'mediaDevices', {value: {
  getUserMedia(options) { return new Promise((resolve, reject) => requests.push({options, resolve, reject})); },
  async enumerateDevices() { return ['front', 'rear'].map(id => ({kind:'videoinput', deviceId:id, label:id + ' lens'})); }
}});
window.acquire = (index, id) => {
  const track = {stopped:false, stop(){ this.stopped = true; }, getSettings(){return {deviceId:id};}};
  tracks[index] = track;
  requests[index].resolve({getTracks:()=>[track], getVideoTracks:()=>[track]});
};
for (const video of document.querySelectorAll('video')) {
  Object.defineProperty(video, 'srcObject', {writable:true, value:null});
  Object.defineProperty(video, 'videoWidth', {value:1080});
  Object.defineProperty(video, 'videoHeight', {value:1920});
  video.play = async () => {};
}
CanvasRenderingContext2D.prototype.drawImage = () => {};
"""


def scenario(page, kind):
    if kind == 'collateral':
        html = ('<form><input id="upload" type="file" class="js-collateral-photo-input">'
                '<button type="button" class="js-collateral-camera" data-photo-input="upload">Camera</button></form>'
                '<dialog id="collateral-camera-dialog"><select data-camera-choice>' + CHOICES + '</select>'
                '<video data-camera-video></video><canvas data-camera-canvas></canvas><p data-camera-status></p>'
                '<button data-camera-capture>Capture</button><button class="js-camera-close">Stop</button></dialog>')
        script = 'apps/tenant_apps/loans/static/loans/collateral_camera.js'
        start, choice, capture, stop = '.js-collateral-camera', '[data-camera-choice]', '[data-camera-capture]', '.js-camera-close'
    elif kind == 'customer':
        html = ('<form><div data-customer-photo data-live="live" data-error="fallback"><input id="upload" type="file">'
                '<img data-photo-preview><div data-photo-camera><video data-photo-video></video></div>'
                '<div data-photo-controls><select data-photo-facing>' + CHOICES + '</select>'
                '<button type="button" data-photo-start>Camera</button><button type="button" data-photo-capture>Capture</button>'
                '<button type="button" data-photo-stop>Stop</button><button type="button" data-photo-discard>Discard</button></div>'
                '<p data-photo-status></p></div></form>')
        script = 'static/js/customer-photo.js'
        start, choice, capture, stop = '[data-photo-start]', '[data-photo-facing]', '[data-photo-capture]', '[data-photo-stop]'
    else:
        html = ('<form id="party-photo-form"><input id="upload" type="file"><input id="party-photo-image-data">'
                '<select id="party-camera-choice">' + CHOICES + '</select><div id="party-camera-panel"></div>'
                '<video id="party-camera-video"></video><canvas id="party-camera-canvas"></canvas>'
                '<button type="button" id="party-camera-start">Camera</button><button type="button" id="party-camera-capture">Capture</button>'
                '<button type="button" id="party-camera-stop">Stop</button><button type="button" id="party-camera-retake">Retake</button></form>')
        script = 'static/js/party-detail-camera.js'
        start, choice, capture, stop = '#party-camera-start', '#party-camera-choice', '#party-camera-capture', '#party-camera-stop'
    page.set_content(html)
    page.evaluate(FAKE_MEDIA)
    page.add_script_tag(path=str(ROOT / 'static/js/camera-selection.js'))
    page.add_script_tag(path=str(ROOT / script))
    if kind == 'customer':
        page.evaluate("document.dispatchEvent(new Event('DOMContentLoaded'))")
    page.locator(start).click()
    page.evaluate("acquire(0, 'front')")
    page.wait_for_function("document.querySelector('select').value === 'device:front'")
    assert page.locator(choice + ' option').count() == 4
    page.locator(choice).select_option('environment')
    assert page.evaluate('tracks[0].stopped')
    assert page.evaluate('requests[1].options.video.facingMode.ideal') == 'environment'
    page.evaluate("acquire(1, 'rear')")
    page.wait_for_function("document.querySelector('select').value === 'device:rear'")
    page.locator(choice).select_option('device:front')
    assert page.evaluate('tracks[1].stopped')
    assert page.evaluate('requests[2].options.video.deviceId.exact') == 'front'
    page.evaluate("acquire(2, 'front')")
    page.locator(capture).click()
    if kind == 'gallery':
        assert page.locator('#party-photo-image-data').input_value().startswith('data:image/jpeg;')
        assert page.evaluate("document.querySelector('canvas').height > document.querySelector('canvas').width")
    else:
        page.wait_for_function("document.querySelector('#upload').files.length === 1")
        page.wait_for_function("Array.from(document.querySelectorAll('img')).some(img => img.naturalWidth > 0)")
    assert page.evaluate('tracks[2].stopped')
    # A cancelled pending permission request must not reopen the camera later.
    page.locator(start).click()
    page.locator(stop).click()
    page.evaluate("acquire(3, 'front')")
    page.wait_for_function('tracks[3].stopped')
    # Rapid switching: only the newest request may become active.
    page.locator(start).click()
    page.locator(choice).select_option('environment')
    page.evaluate("acquire(5, 'rear'); acquire(4, 'front')")
    page.wait_for_function('tracks[4].stopped && !tracks[5].stopped')
    page.evaluate("window.dispatchEvent(new Event('pagehide'))")
    assert page.evaluate('tracks.every(track => track.stopped)')
    # A denied request leaves file upload usable.
    page.locator(start).click()
    page.evaluate("requests[6].reject(new Error('denied'))")
    page.wait_for_timeout(20)
    assert page.locator('#upload').is_enabled()
    print(f'PASS {kind}: front/rear/device switch, capture, cancellation, races, cleanup, upload fallback')


if __name__ == '__main__':
    with sync_playwright() as browser_api:
        browser = browser_api.chromium.launch(channel='msedge', headless=True)
        for kind in ('collateral', 'customer', 'gallery'):
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            scenario(page, kind)
            assert not errors, errors
            page.close()
        browser.close()
