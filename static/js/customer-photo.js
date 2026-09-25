/* Camera frames use the existing multipart ImageField, never a separate upload. */
document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-customer-photo]');
  if (!root) return;
  const input = root.querySelector('input[type=file]');
  const clear = root.querySelector('input[type=checkbox]');
  const preview = root.querySelector('[data-photo-preview]');
  const panel = root.querySelector('[data-photo-camera]');
  const video = root.querySelector('[data-photo-video]');
  const start = root.querySelector('[data-photo-start]');
  const capture = root.querySelector('[data-photo-capture]');
  const stop = root.querySelector('[data-photo-stop]');
  const discard = root.querySelector('[data-photo-discard]');
  const status = root.querySelector('[data-photo-status]');
  const facing = root.querySelector('[data-photo-facing]');
  const saved = preview.getAttribute('src') || '';
  let stream = null, objectUrl = null, generation = 0;
  root.querySelector('[data-photo-controls]').hidden = false;

  function stopCamera() {
    generation++;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.srcObject = null;
    panel.hidden = true;
    start.disabled = false;
    capture.disabled = stop.disabled = true;
  }
  function revokePreview() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
  function showSelection() {
    stopCamera();
    revokePreview();
    const file = input.files?.[0];
    if (file) {
      if (clear) clear.checked = false;
      objectUrl = URL.createObjectURL(file);
      preview.src = objectUrl;
      preview.hidden = false;
      discard.hidden = false;
      status.textContent = file.type.startsWith('image/') ? root.dataset.ready : root.dataset.invalid;
    } else {
      preview.src = saved;
      preview.hidden = !saved || !!clear?.checked;
      discard.hidden = true;
      status.textContent = root.dataset.stopped;
    }
  }
  input.addEventListener('change', showSelection);
  clear?.addEventListener('change', () => {
    input.value = '';
    showSelection();
  });
  discard.addEventListener('click', () => {
    input.value = '';
    showSelection();
    start.focus();
  });
  async function startCamera() {
    stopCamera();
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || typeof DataTransfer === 'undefined') {
      status.textContent = root.dataset.error;
      return;
    }
    const request = generation;
    start.disabled = true;
    stop.disabled = false;
    status.textContent = root.dataset.waiting;
    try {
      const acquired = await navigator.mediaDevices.getUserMedia(window.RokkadCameraSelection.constraints(facing, 'user'));
      if (request !== generation) {
        acquired.getTracks().forEach(track => track.stop());
        return;
      }
      stream = acquired;
      panel.hidden = false;
      video.srcObject = stream;
      await video.play();
      if (request !== generation) return;
      capture.disabled = false;
      status.textContent = root.dataset.live;
      window.RokkadCameraSelection.refresh(facing, stream, () => request === generation);
      capture.focus();
    } catch (_) {
      if (request !== generation) return;
      stopCamera();
      status.textContent = root.dataset.error;
    }
  }
  start.addEventListener('click', startCamera);
  stop.addEventListener('click', () => {
    stopCamera();
    status.textContent = root.dataset.stopped;
    start.focus();
  });
  facing?.addEventListener('change', () => {
    if (stream || start.disabled) return startCamera();
  });
  capture.addEventListener('click', () => {
    if (!stream || !video.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    stopCamera();
    const frame = generation;
    canvas.toBlob(blob => {
      if (frame !== generation) return;
      try {
        if (!blob) throw new Error('No frame');
        const transfer = new DataTransfer();
        transfer.items.add(new File([blob], 'customer-photo.jpg', {type: 'image/jpeg'}));
        input.files = transfer.files;
        showSelection();
        discard.focus();
      } catch (_) {
        status.textContent = root.dataset.error;
      }
    }, 'image/jpeg', 0.9);
  });
  root.closest('form').addEventListener('submit', stopCamera);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopCamera(); });
  window.addEventListener('pagehide', () => { stopCamera(); revokePreview(); });
  window.addEventListener('pageshow', () => { if (input.files?.length) showSelection(); });
});
