/* Camera capture for the local concept only; nothing is uploaded or persisted. */
(() => {
  const dialog = $('#camera-dialog');
  const video = $('#camera-video');
  const still = $('#camera-still');
  const status = $('#camera-status');
  const capture = $('#camera-capture');
  const use = $('#camera-use');
  const retake = $('#camera-retake');
  let stream = null, pendingPhoto = null, generation = 0;

  function stop() {
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.srcObject = null;
  }
  function discard() {
    if (pendingPhoto) URL.revokeObjectURL(pendingPhoto);
    pendingPhoto = null;
    still.removeAttribute('src');
  }
  async function start() {
    const attempt = ++generation;
    stop();
    discard();
    still.hidden = use.hidden = retake.hidden = true;
    capture.hidden = false;
    capture.disabled = true;
    video.hidden = true;
    status.textContent = 'Allow camera access to take a photo.';
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('unavailable');
      const opened = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } }, audio: false,
      });
      if (attempt !== generation || !dialog.open) {
        opened.getTracks().forEach(track => track.stop());
        return;
      }
      stream = opened;
      video.srcObject = opened;
      video.hidden = false;
      await video.play();
      if (attempt !== generation || !dialog.open) return;
      capture.disabled = false;
      status.textContent = 'Position the collateral in the frame, then capture.';
    } catch (error) {
      if (attempt !== generation || !dialog.open) return;
      stop();
      video.hidden = true;
      status.textContent = error.name === 'NotAllowedError'
        ? 'Camera permission was denied. Allow it in your browser settings and retry, or upload an image.'
        : 'Camera is unavailable. Check that it is connected and not in use, then retry or upload an image.';
      retake.hidden = false;
      retake.textContent = 'Retry camera';
    }
  }
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-camera-open]')) return;
    retake.textContent = 'Retake';
    dialog.showModal();
    start();
  });
  capture.addEventListener('click', () => {
    if (!video.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const attempt = generation;
    capture.disabled = true;
    canvas.toBlob(blob => {
      if (attempt !== generation || !dialog.open) return;
      if (!blob) {
        status.textContent = 'Photo could not be captured. Please try again.';
        capture.disabled = false;
        return;
      }
      pendingPhoto = URL.createObjectURL(blob);
      still.src = pendingPhoto;
      still.hidden = use.hidden = retake.hidden = false;
      retake.textContent = 'Retake';
      video.hidden = capture.hidden = true;
      stop();
      status.textContent = 'Check that the item is clear before using this photo.';
      use.focus();
    }, 'image/jpeg', 0.9);
  });
  retake.addEventListener('click', start);
  use.addEventListener('click', () => {
    if (!pendingPhoto) return;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    photoUrl = pendingPhoto;
    pendingPhoto = null;
    $('#photo').value = '';
    $('#photo-preview').innerHTML = `<img src="${photoUrl}" alt="Captured collateral reference">`;
    dialog.close();
    toast('Photo added to this sample session.');
  });
  $('#camera-upload').addEventListener('click', () => {
    dialog.close();
    $('#photo').click();
  });
  function cleanup() { generation++; stop(); discard(); }
  dialog.addEventListener('close', cleanup);
  dialog.addEventListener('cancel', cleanup);
  window.addEventListener('pagehide', cleanup);
})();
