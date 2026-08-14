(() => {
  const dialog = document.getElementById("collateral-camera-dialog");
  if (!dialog || dialog.dataset.initialized === "true") return;
  dialog.dataset.initialized = "true";

  const video = dialog.querySelector("[data-camera-video]");
  const canvas = dialog.querySelector("[data-camera-canvas]");
  const status = dialog.querySelector("[data-camera-status]");
  const captureButton = dialog.querySelector("[data-camera-capture]");
  let stream = null;
  let targetInput = null;

  const stopCamera = () => {
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    targetInput = null;
  };

  const closeCamera = () => {
    stopCamera();
    if (dialog.open) dialog.close();
  };

  document.addEventListener("click", async (event) => {
    const trigger = event.target.closest(".js-collateral-camera");
    if (!trigger) return;
    targetInput = document.getElementById(trigger.dataset.photoInput);
    if (!targetInput) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      targetInput.click();
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" } },
      });
      video.srcObject = stream;
      await video.play();
      status.textContent = "Position the collateral clearly, then capture.";
      dialog.showModal();
    } catch (_error) {
      targetInput.click();
      stopCamera();
    }
  });

  dialog.querySelectorAll(".js-camera-close").forEach((button) => {
    button.addEventListener("click", closeCamera);
  });
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeCamera();
  });

  captureButton.addEventListener("click", () => {
    if (!targetInput || !video.videoWidth || !video.videoHeight) {
      status.textContent = "The camera is not ready yet.";
      return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob || !targetInput) {
        status.textContent = "The photograph could not be captured. Please try again.";
        return;
      }
      const file = new File([blob], `collateral-${Date.now()}.jpg`, {
        type: "image/jpeg",
        lastModified: Date.now(),
      });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      targetInput.files = transfer.files;
      targetInput.dispatchEvent(new Event("change", { bubbles: true }));
      closeCamera();
    }, "image/jpeg", 0.9);
  });
})();
