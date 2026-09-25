(() => {
  const dialog = document.getElementById("collateral-camera-dialog");
  if (!dialog || dialog.dataset.initialized === "true") return;
  dialog.dataset.initialized = "true";

  const previews = new Map();
  const previewSelection = (input) => {
    const old = previews.get(input);
    if (old) { URL.revokeObjectURL(old.url); old.element.remove(); previews.delete(input); }
    const file = input.files?.[0];
    if (!file || !["image/jpeg", "image/png"].includes(file.type)) return;
    const element = document.createElement("figure");
    element.className = "mt-2 mb-0";
    element.dataset.collateralPhotoPreview = "true";
    const image = document.createElement("img");
    const url = URL.createObjectURL(file);
    image.src = url;
    image.alt = "Selected collateral photograph";
    image.className = "img-thumbnail";
    image.style.cssText = "max-width:12rem;max-height:10rem;object-fit:contain";
    const caption = document.createElement("figcaption");
    caption.className = "small text-body-secondary mt-1";
    caption.textContent = "Selected photo: save the form to upload it. Choose another file or use the camera to retake.";
    element.append(image, caption);
    (input.closest(".input-group") || input).insertAdjacentElement("afterend", element);
    previews.set(input, {url, element});
  };
  document.addEventListener("change", (event) => {
    if (event.target.matches(".js-collateral-photo-input")) previewSelection(event.target);
  });
  document.addEventListener("reset", (event) => setTimeout(() => {
    event.target.querySelectorAll(".js-collateral-photo-input").forEach(previewSelection);
  }, 0));
  const prunePreviews = () => {
    for (const [input, preview] of previews) if (!input.isConnected) {
      URL.revokeObjectURL(preview.url); preview.element.remove(); previews.delete(input);
    }
  };
  new MutationObserver(prunePreviews).observe(document.body, {childList:true, subtree:true});
  window.addEventListener("pagehide", () => {
    for (const preview of previews.values()) { URL.revokeObjectURL(preview.url); preview.element.remove(); }
    previews.clear();
  });
  window.addEventListener("pageshow", () => {
    document.querySelectorAll(".js-collateral-photo-input").forEach(previewSelection);
  });

  const video = dialog.querySelector("[data-camera-video]");
  const canvas = dialog.querySelector("[data-camera-canvas]");
  const status = dialog.querySelector("[data-camera-status]");
  const captureButton = dialog.querySelector("[data-camera-capture]");
  const choice = dialog.querySelector("[data-camera-choice]");
  let stream = null, targetInput = null, generation = 0;

  const stopCamera = () => {
    generation++;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.srcObject = null;
    captureButton.disabled = true;
  };
  const closeCamera = () => {
    stopCamera();
    targetInput = null;
    if (dialog.open) dialog.close();
  };
  const startCamera = async () => {
    stopCamera();
    const request = generation;
    status.textContent = "Allow camera access, then position the collateral clearly.";
    try {
      const acquired = await navigator.mediaDevices.getUserMedia(window.RokkadCameraSelection.constraints(choice, "environment"));
      if (request !== generation) { acquired.getTracks().forEach(track => track.stop()); return; }
      stream = acquired;
      video.srcObject = stream;
      await video.play();
      if (request !== generation) return;
      captureButton.disabled = false;
      status.textContent = "Position the collateral clearly, then capture. You can change camera above.";
      window.RokkadCameraSelection.refresh(choice, stream, () => request === generation);
    } catch (_) {
      if (request !== generation) return;
      stopCamera();
      status.textContent = "Could not access this camera. Choose another camera, or cancel and choose an image file.";
    }
  };
  document.addEventListener("click", event => {
    const trigger = event.target.closest(".js-collateral-camera");
    if (!trigger) return;
    closeCamera();
    targetInput = document.getElementById(trigger.dataset.photoInput);
    if (!targetInput) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof DataTransfer === "undefined") {
      targetInput.click();
      targetInput = null;
      return;
    }
    dialog.showModal();
    startCamera();
  });
  choice.addEventListener("change", startCamera);
  document.addEventListener("visibilitychange", () => { if (document.hidden) closeCamera(); });
  window.addEventListener("pagehide", closeCamera);
  document.addEventListener("submit", closeCamera);

  dialog.querySelectorAll(".js-camera-close").forEach((button) => {
    button.addEventListener("click", closeCamera);
  });
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeCamera();
  });
  dialog.addEventListener("close", () => { if (!dialog.open) closeCamera(); });

  captureButton.addEventListener("click", () => {
    if (!stream || !targetInput || !video.videoWidth || !video.videoHeight) {
      status.textContent = "The camera is not ready yet.";
      return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const input = targetInput;
    stopCamera();
    const frame = generation;
    canvas.toBlob((blob) => {
      if (frame !== generation || input !== targetInput) return;
      if (!blob || !targetInput) {
        status.textContent = "The photograph could not be captured. Please try again.";
        startCamera();
        return;
      }
      try {
        const file = new File([blob], `collateral-${Date.now()}.jpg`, {
          type: "image/jpeg",
          lastModified: Date.now(),
        });
        const transfer = new DataTransfer();
        transfer.items.add(file);
        targetInput.files = transfer.files;
        targetInput.dispatchEvent(new Event("change", { bubbles: true }));
        closeCamera();
      } catch (_) {
        status.textContent = "Could not attach the photo. Cancel and choose an image file instead.";
      }
    }, "image/jpeg", 0.9);
  });
})();
