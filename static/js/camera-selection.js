/* Device names become available after camera permission. Keep choices page-local. */
window.RokkadCameraSelection = {
  constraints(select, fallback) {
    const choice = select?.value || fallback;
    return {audio: false, video: choice.startsWith('device:')
      ? {deviceId: {exact: choice.slice(7)}} : {facingMode: {ideal: choice}}};
  },
  async refresh(select, stream, isCurrent) {
    if (!select || !navigator.mediaDevices?.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      if (!isCurrent()) return;
      const selected = stream.getVideoTracks?.()[0]?.getSettings?.().deviceId;
      select.querySelectorAll('[data-camera-device]').forEach(option => option.remove());
      devices.filter(device => device.kind === 'videoinput' && device.deviceId).forEach((device, index) => {
        const option = document.createElement('option');
        option.value = 'device:' + device.deviceId;
        option.textContent = device.label || `Camera ${index + 1}`;
        option.dataset.cameraDevice = 'true';
        select.appendChild(option);
        if (device.deviceId === selected) select.value = option.value;
      });
    } catch (_) { /* Front/rear choices and file upload remain available. */ }
  },
};
