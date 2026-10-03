/* Private collateral browsing. All values are suggestions; the server reviews every operation. */
(() => {
  "use strict";
  const receive = document.querySelector("[data-khata-receive]");
  if (receive) {
    const upload = receive.querySelector('input[type="file"]');
    const preview = receive.querySelector("[data-photo-preview]");
    const controls = receive.querySelector("[data-photo-controls]");
    const panel = controls.querySelector("[data-camera-panel]");
    const video = controls.querySelector("[data-camera-video]");
    const start = controls.querySelector("[data-camera-start]");
    const capture = controls.querySelector("[data-camera-capture]");
    const facing = controls.querySelector("[data-camera-facing]");
    const device = controls.querySelector("[data-camera-device]");
    const clear = controls.querySelector("[data-photo-clear]");
    const status = controls.querySelector("[data-camera-status]");
    const liveSupported = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia;
    let stream;
    let generation = 0;
    let capturing = false;
    let previewURL;
    controls.hidden = false;
    start.disabled = !liveSupported;
    if (!liveSupported) status.textContent = "Live camera is unavailable here. Choose a file or use a phone camera button.";

    function stopCamera() {
      generation += 1;
      stream?.getTracks().forEach(track => track.stop());
      stream = undefined;
      video.srcObject = null;
      panel.hidden = true;
      capture.disabled = true;
      start.disabled = !liveSupported;
    }

    upload.addEventListener("change", () => {
      stopCamera();
      upload.removeAttribute("capture");
      if (previewURL) URL.revokeObjectURL(previewURL);
      preview.hidden = true;
      preview.removeAttribute("src");
      const file = upload.files[0];
      clear.hidden = !file;
      if (file && ["image/jpeg", "image/png"].includes(file.type)) {
        previewURL = URL.createObjectURL(file);
        preview.src = previewURL;
        preview.hidden = false;
        status.textContent = "Photo selected. Check the preview, then save to attach it.";
      } else if (file) {
        status.textContent = "Select a JPEG or PNG photo.";
      } else {
        status.textContent = "No photo selected.";
      }
    });

    async function openCamera() {
      stopCamera();
      const attempt = generation;
      start.disabled = true;
      panel.hidden = false;
      status.textContent = "Waiting for camera permission…";
      try {
        const next = await navigator.mediaDevices.getUserMedia({audio: false, video: {
          ...(device.value ? {deviceId: {exact: device.value}} : {facingMode: {ideal: facing.value}}),
          width: {ideal: 1600}, height: {ideal: 1200}
        }});
        if (attempt !== generation) {
          next.getTracks().forEach(track => track.stop());
          return;
        }
        stream = next;
        video.srcObject = next;
        panel.hidden = false;
        await video.play();
        if (attempt !== generation) return;
        capture.disabled = false;
        start.disabled = false;
        status.textContent = "Camera is live. Position the collateral and take a photo.";
        // Labels become available after permission; multiple desktop webcams can be selected explicitly.
        try {
          const cameras = (await navigator.mediaDevices.enumerateDevices()).filter(entry => entry.kind === "videoinput");
          if (attempt !== generation) return;
          device.replaceChildren(new Option("Use front / rear choice", ""));
          for (const [index, entry] of cameras.entries()) device.add(new Option(entry.label || `Camera ${index + 1}`, entry.deviceId));
          device.value = next.getVideoTracks()[0].getSettings().deviceId || "";
          controls.querySelector("[data-camera-device-label]").hidden = cameras.length < 2;
        } catch (_) { /* Facing choice and capture still work without device enumeration. */ }
      } catch (error) {
        if (attempt !== generation) return;
        stopCamera();
        status.textContent = error.name === "NotAllowedError"
          ? "Camera permission was denied. Allow camera access in your browser, or choose a file / phone camera button."
          : "Camera could not be opened. Check that a camera is connected and available, or choose a file / phone camera button.";
      }
    }

    start.addEventListener("click", openCamera);
    controls.querySelector("[data-camera-stop]").addEventListener("click", () => {
      stopCamera();
      status.textContent = "Camera closed. Your selected photo is unchanged.";
    });
    facing.addEventListener("change", () => {
      device.value = "";
      if (stream || start.disabled && liveSupported) openCamera();
    });
    device.addEventListener("change", () => { if (stream) openCamera(); });
    for (const button of controls.querySelectorAll("[data-camera-native]")) {
      button.addEventListener("click", () => {
        stopCamera();
        upload.setAttribute("capture", button.dataset.cameraNative);
        upload.click();
      });
    }
    upload.addEventListener("cancel", () => upload.removeAttribute("capture"));
    clear.addEventListener("click", () => {
      upload.value = "";
      upload.dispatchEvent(new Event("change", {bubbles: true}));
    });
    capture.addEventListener("click", async () => {
      if (capturing || !video.videoWidth || !video.videoHeight) return;
      const attempt = generation;
      capturing = true;
      capture.disabled = true;
      status.textContent = "Preparing photo…";
      try {
        const canvas = document.createElement("canvas");
        const scale = Math.min(1, 1600 / Math.max(video.videoWidth, video.videoHeight));
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.9));
        if (attempt !== generation) return;
        if (!blob) throw new Error("No photo captured");
        const files = new DataTransfer();
        files.items.add(new File([blob], "collateral-camera.jpg", {type: "image/jpeg"}));
        upload.files = files.files;
        upload.dispatchEvent(new Event("change", {bubbles: true}));
      } catch (_) {
        status.textContent = "Photo could not be captured. Try again or choose a file.";
      } finally {
        capturing = false;
        capture.disabled = !stream;
      }
    });
    receive.addEventListener("submit", event => {
      if (capturing) {
        event.preventDefault();
        status.textContent = "Please wait for the photo preview before saving.";
      } else stopCamera();
    });
    window.addEventListener("pagehide", () => {
      stopCamera();
      if (previewURL) URL.revokeObjectURL(previewURL);
    });
  }

  const form = document.querySelector("[data-khata-exchange], [data-khata-servicing]");
  if (!form) return;
  const servicing = form.hasAttribute("data-khata-servicing");
  const data = JSON.parse(document.getElementById(servicing ? "khata-servicing-data" : "khata-exchange-data").textContent);
  const roles = data.roles || ["outgoing", "incoming"];
  let nativeSelection = false;
  const selected = Object.fromEntries(roles.map(role => [role, new Map((servicing ? data.selected[role] : data[role]).map(item => [item.id, item]))]));
  if (servicing) {
    form.querySelector("[data-servicing-picker]").hidden = false;
    for (const root of form.querySelectorAll("[data-servicing-fallback]")) {
      root.hidden = true;
      root.querySelector("select").disabled = true;
    }
    const native = form.querySelector("[data-servicing-native]");
    native.hidden = false;
    native.addEventListener("click", () => {
      nativeSelection = true;
      for (const role of roles) {
        const choice = form.querySelector(`select[name="${role}"]`);
        for (const option of choice.options) option.selected = selected[role].has(Number(option.value));
        form.querySelector(`[data-hidden-role="${role}"]`).replaceChildren();
        states[role].controller?.abort();
      }
      if (data.handover) {
        form.querySelector('select[name="parent"]').value = [...selected.item.values()][0]?.parent || "";
        form.querySelector("[data-hidden-parent]").replaceChildren();
      }
      for (const root of form.querySelectorAll("[data-servicing-fallback]")) {
        root.hidden = false;
        root.querySelector("select").disabled = false;
      }
      form.querySelector("[data-servicing-picker]").hidden = true;
      native.hidden = true;
    });
  }
  const states = {};
  const money = value => new Intl.NumberFormat("en-IN", {maximumFractionDigits: 2, minimumFractionDigits: 2}).format(value);
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const other = role => role === "outgoing" ? "incoming" : "outgoing";

  function sync() {
    if (nativeSelection) return;
    for (const role of roles) {
      const root = states[role].root;
      const hidden = form.querySelector(`[data-hidden-role="${role}"]`);
      const list = root.querySelector("[data-selected]");
      hidden.replaceChildren();
      list.replaceChildren();
      const totals = new Map();
      for (const item of selected[role].values()) {
        const input = element("input");
        input.type = "hidden"; input.name = role; input.value = item.id;
        hidden.append(input);
        const row = element("li", undefined, "list-group-item px-0");
        if (item.thumbnail) {
          const image = element("img"); image.src = item.thumbnail; image.alt = `Photograph of Item ${item.id}`;
          image.width = 64; image.height = 52; image.className = "img-thumbnail me-2";
          row.append(image);
        }
        row.append(element("span", `Item ${item.id}: ${item.description} · ${item.storage} · ${item.net} g / ${item.purity}%`));
        if (data.handover) row.append(element("div", `Return reservation: Operation ${item.parent}`, "small text-muted"));
        const remove = element("button", `Remove Item ${item.id}`, "btn btn-sm btn-outline-secondary ms-2");
        remove.type = "button";
        remove.addEventListener("click", () => { selected[role].delete(item.id); sync(); });
        row.append(remove); list.append(row);
        const total = totals.get(item.metal) || {count: 0, net: 0, value: 0, complete: true};
        total.count++; total.net += Number(item.net);
        if (item.value === null) total.complete = false;
        else total.value += Number(item.value);
        totals.set(item.metal, total);
      }
      const summaries = [...totals].map(([metal, total]) => `${metal}: ${total.count} item records, ${total.net.toFixed(3)} g net, ${total.complete ? "INR " + money(total.value) : "current valuation unavailable"}`);
      root.querySelector("[data-selected-summary]").textContent = summaries.join("; ") || "No items selected.";
      for (const checkbox of root.querySelectorAll("[data-select-item]")) {
        const id = Number(checkbox.dataset.selectItem);
        checkbox.checked = selected[role].has(id);
        checkbox.disabled = !servicing && selected[other(role)].has(id);
      }
    }
    const link = document.querySelector("[data-receive-replacement]");
    if (data.handover) {
      const parent = form.querySelector("[data-hidden-parent]");
      parent.replaceChildren();
      const item = [...selected.item.values()][0];
      if (item) {
        const input = element("input"); input.type = "hidden"; input.name = "parent"; input.value = item.parent;
        parent.append(input);
      }
    }
    if (!link) return;
    const url = new URL(data.receive, location.origin);
    url.searchParams.set("return_to", "exchange");
    for (const role of roles) for (const id of selected[role].keys()) url.searchParams.append(role, id);
    link.href = url.pathname + url.search;
  }

  function renderRows(role, items) {
    const root = states[role].root;
    const body = root.querySelector("[data-results]");
    body.replaceChildren();
    if (!items.length) {
      const row = element("tr"); const cell = element("td", "No eligible collateral matches.");
      cell.colSpan = 4; row.append(cell); body.append(row);
    }
    for (const item of items) {
      const row = element("tr");
      const choice = element("td");
      const checkbox = element("input");
      checkbox.type = data.single ? "radio" : "checkbox";
      if (data.single) checkbox.name = "pick-" + role; checkbox.className = "form-check-input";
      checkbox.dataset.selectItem = item.id;
      checkbox.setAttribute("aria-label", `Select Item ${item.id}: ${item.description}`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          if (data.single) selected[role].clear();
          selected[role].set(item.id, item);
        }
        else selected[role].delete(item.id);
        sync();
      });
      choice.append(checkbox);
      const identity = element("td");
      const link = element("a", `Item ${item.id}`); link.href = item.scan; link.target = "_blank"; link.rel = "noopener";
      identity.append(link);
      if (item.photo) {
        const image = element("img"); image.src = item.thumbnail; image.alt = `Photograph of Item ${item.id}`;
        image.width = 64; image.height = 52; image.loading = "lazy"; image.className = "img-thumbnail d-block";
        identity.append(image);
      } else identity.append(element("div", "No photo", "small text-muted"));
      const details = element("td");
      details.append(element("div", item.description), element("div", `${item.metal} / quantity ${item.quantity}`, "small"),
        element("div", `${item.gross} g gross / ${item.net} g net / ${item.purity}%`, "small"),
        element("div", `${item.storage} · ${item.received}`, "small text-muted"));
      const value = element("td", item.value === null ? "Unavailable" : "INR " + money(item.value));
      row.append(choice, identity, details, value); body.append(row);
    }
    sync();
  }

  async function load(role, page = 1) {
    if (nativeSelection) return;
    const state = states[role];
    if (state.controller) state.controller.abort();
    const controller = new AbortController();
    state.controller = controller;
    const url = new URL(data.endpoint, location.origin);
    url.searchParams.set("format", "json"); url.searchParams.set("mode", data.mode || role); url.searchParams.set("page", page);
    for (const field of state.root.querySelectorAll("[data-filter]")) url.searchParams.set(field.dataset.filter, field.value);
    const status = state.root.querySelector("[data-results-status]");
    status.textContent = "Loading collateral...";
    // Old results must not be mistaken for the new query, even when the request fails.
    state.root.querySelector("[data-results]").replaceChildren();
    for (const button of state.root.querySelectorAll("[data-page]")) button.disabled = true;
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: "same-origin", headers: {Accept: "application/json"}});
      if (!response.ok || !(response.headers.get("Content-Type") || "").includes("application/json")) throw new Error("Search unavailable. Check filters or sign in again.");
      const result = await response.json();
      if (controller.signal.aborted) return;
      state.page = result.page;
      renderRows(role, result.items);
      status.textContent = `${result.count} eligible item records. Selections remain below when searching or changing pages.`;
      state.root.querySelector("[data-page-label]").textContent = `Page ${result.page} of ${result.pages}`;
      state.root.querySelector('[data-page="previous"]').disabled = !result.previous;
      state.root.querySelector('[data-page="next"]').disabled = !result.next;
    } catch (error) {
      if (error.name !== "AbortError") status.textContent = error.message;
    }
  }

  for (const role of roles) {
    const root = form.querySelector(`[data-picker="${role}"]`);
    states[role] = {root, page: 1};
    let timeout;
    for (const field of root.querySelectorAll("[data-filter]")) field.addEventListener(field.type === "search" ? "input" : "change", () => {
      clearTimeout(timeout); timeout = setTimeout(() => load(role), field.type === "search" ? 250 : 0);
    });
    for (const button of root.querySelectorAll("[data-page]")) button.addEventListener("click", () => load(role, states[role].page + (button.dataset.page === "next" ? 1 : -1)));
  }
  if (data.suggested) {
    states.incoming.root.querySelector('[data-filter="q"]').value = data.suggested;
    const notice = element("p", `Item ${data.suggested} was received. Verify and select it as a replacement; receipt alone does not record an exchange.`, "alert alert-info");
    form.prepend(notice);
  }
  sync();
  for (const role of roles) load(role);
})();
