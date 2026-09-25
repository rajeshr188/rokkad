(() => {
    const form = document.getElementById("party-photo-form");
    const panel = document.getElementById("party-camera-panel");
    const video = document.getElementById("party-camera-video");
    const canvas = document.getElementById("party-camera-canvas");
    const imageDataInput = document.getElementById("party-photo-image-data");
    const fileInput = form?.querySelector("input[type=file]");
    const startButton = document.getElementById("party-camera-start");
    const captureButton = document.getElementById("party-camera-capture");
    const retakeButton = document.getElementById("party-camera-retake");
    const stopButton = document.getElementById("party-camera-stop");

    if (!form || !panel || !video || !canvas || !imageDataInput || !startButton || !captureButton || !retakeButton || !stopButton) {
        return;
    }

    const choice = document.getElementById("party-camera-choice");
    let stream = null, generation = 0;

    function stopCamera() {
        generation++;
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }
        video.srcObject = null;
        captureButton.disabled = true;
        retakeButton.disabled = !imageDataInput.value;
        stopButton.disabled = true;
        startButton.disabled = false;
    }

    function resetPanel(message) {
        panel.innerHTML = "";
        const span = document.createElement("span");
        span.className = "text-muted";
        span.textContent = message;
        panel.appendChild(span);
    }

    async function startCamera() {
        stopCamera();
        if (!navigator.mediaDevices?.getUserMedia) {
            resetPanel("Camera is not available. Use file upload instead.");
            return;
        }
        const request = generation;
        startButton.disabled = true;
        stopButton.disabled = false;
        resetPanel("Waiting for camera access...");
        try {
            const acquired = await navigator.mediaDevices.getUserMedia(window.RokkadCameraSelection.constraints(choice, "user"));
            if (request !== generation) { acquired.getTracks().forEach(track => track.stop()); return; }
            stream = acquired;
            video.srcObject = stream;
            panel.innerHTML = "";
            panel.appendChild(video);
            video.classList.remove("d-none");
            await video.play();
            if (request !== generation) return;
            captureButton.disabled = false;
            retakeButton.disabled = true;
            window.RokkadCameraSelection.refresh(choice, stream, () => request === generation);
        } catch (_) {
            if (request !== generation) return;
            stopCamera();
            resetPanel("Could not access this camera. Choose another camera or use file upload.");
        }
    }
    startButton.addEventListener("click", startCamera);
    choice.addEventListener("change", () => {
        if (stream || startButton.disabled) startCamera();
    });

    captureButton.addEventListener("click", () => {
        if (!stream || !video.videoWidth || !video.videoHeight) return;
        const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        const context = canvas.getContext("2d");
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = canvas.toDataURL("image/jpeg", 0.9);
        imageDataInput.value = imageData;
        if (fileInput) {
            fileInput.value = "";
        }
        panel.innerHTML = "";
        const img = document.createElement("img");
        img.src = imageData;
        img.alt = "Captured profile photo";
        img.className = "img-fluid rounded";
        img.style.maxHeight = "220px";
        panel.appendChild(img);
        stopCamera();
        retakeButton.disabled = false;
    });

    retakeButton.addEventListener("click", () => {
        imageDataInput.value = "";
        resetPanel("Camera preview");
        startButton.click();
    });

    stopButton.addEventListener("click", () => {
        stopCamera();
        resetPanel("Camera stopped");
    });

    if (fileInput) {
        fileInput.addEventListener("change", () => {
            if (fileInput.files.length) {
                imageDataInput.value = "";
                stopCamera();
            }
        });
    }

    form.addEventListener("submit", (event) => {
        stopCamera();
        const hasCapture = Boolean(imageDataInput.value);
        const hasFile = Boolean(fileInput && fileInput.files.length);
        if (!hasCapture && !hasFile) {
            event.preventDefault();
            resetPanel("Capture a photo or choose an image file.");
        }
    });

    window.addEventListener("pagehide", stopCamera);
    document.addEventListener("visibilitychange", () => { if (document.hidden) stopCamera(); });
})();
