/* Capture is local. Only an explicitly accepted still joins the inspection upload. */
(() => {
  const el = (id) => document.getElementById(id);
  const video = el("camera-video");
  let stream = null, mediaUrl = null, stillUrl = null, pending = null;
  let source = "", sourceName = "", generation = 0, capturing = false;

  function message(text, error = false) {
    el("camera-status").textContent = text;
    el("camera-status").classList.toggle("camera-error", error);
  }

  function clearStill() {
    if (stillUrl) URL.revokeObjectURL(stillUrl);
    stillUrl = null;
    pending = null;
    el("camera-still").removeAttribute("src");
    el("camera-still").hidden = true;
    el("camera-review").hidden = true;
    video.hidden = false;
    el("camera-capture").hidden = false;
    el("camera-kind").disabled = source === "demo";
  }

  function stop() {
    generation++;
    capturing = false;
    // Invalidate pending permission requests before releasing active tracks.
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.pause();
    video.srcObject = null;
    video.removeAttribute("src");
    video.load();
    if (mediaUrl) URL.revokeObjectURL(mediaUrl);
    mediaUrl = null;
    source = "";
    clearStill();
    el("camera-workspace").hidden = true;
    el("camera-device-wrap").hidden = true;
    el("camera-capture").disabled = true;
    el("camera-start").disabled = false;
    el("camera-credit").hidden = true;
  }

  function chooseMode(camera) {
    if (!camera) stop();
    else if (!source) message("Preview stays on this device. Only photos you add are uploaded when you run the inspection.");
    el("camera-panel").hidden = !camera;
    el("photo-upload-panel").hidden = camera;
    el("source-upload").setAttribute("aria-pressed", String(!camera));
    el("source-camera").setAttribute("aria-pressed", String(camera));
  }

  function showSource(kind, name) {
    source = kind;
    sourceName = name;
    el("camera-workspace").hidden = false;
    el("camera-source-label").textContent = kind === "camera" ? "Live camera" : kind === "demo" ? "Demo video · recorded" : "Your video · recorded";
    el("camera-credit").hidden = kind !== "demo";
    video.controls = kind !== "camera";
    el("camera-kind").disabled = kind === "demo";
    if (kind === "demo") el("camera-kind").value = "frames";
    message(kind === "camera" ? "Camera connected. Capture a frame when the image is sharp." : "Recorded video. Pause or scrub to choose a frame, then capture it.");
  }

  function cameraError(error) {
    const messages = {
      NotAllowedError: "Camera access was not granted. Allow it in your browser settings, or use Upload photos.",
      NotFoundError: "No camera found. Connect a camera, open a video, or use Upload photos.",
      NotReadableError: "The camera is busy or unavailable. Close other camera apps and try again.",
      OverconstrainedError: "That camera is unavailable. Try Use camera again.",
      SecurityError: "Camera access is blocked by this browser. Use Upload photos instead.",
    };
    return messages[error.name] || "Could not start the camera. Try again or use Upload photos.";
  }

  async function startCamera(deviceId) {
    stop();
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      message("Camera access needs HTTPS or localhost and a supported browser. You can still upload photos or open a video.", true);
      return;
    }
    const token = generation;
    el("camera-start").disabled = true;
    message("Waiting for camera access. Allow the request in your browser, or switch to Upload photos.");
    try {
      const acquired = await navigator.mediaDevices.getUserMedia({ audio: false, video: {
        ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: { ideal: "environment" } }),
        width: { ideal: 3840 }, height: { ideal: 2160 }, frameRate: { ideal: 15, max: 30 },
      } });
      if (token !== generation) {
        acquired.getTracks().forEach((track) => track.stop());
        return;
      }
      stream = acquired;
      showSource("camera", acquired.getVideoTracks()[0]?.label || "Camera");
      video.srcObject = acquired;
      await video.play();
      if (token !== generation) return;
      acquired.getVideoTracks()[0]?.addEventListener("ended", () => {
        if (token !== generation) return;
        stop();
        message("Camera disconnected. Reconnect it and select Use camera.", true);
      });
      // Device names become available only after camera permission is granted.
      try {
        const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
        if (token !== generation) return;
        const select = el("camera-device");
        select.replaceChildren(...devices.map((d, i) => new Option(d.label || `Camera ${i + 1}`, d.deviceId)));
        select.value = acquired.getVideoTracks()[0]?.getSettings().deviceId || "";
        el("camera-device-wrap").hidden = devices.length < 2;
      } catch { /* Device switching is optional; the active camera still works. */ }
    } catch (error) {
      if (token !== generation) return;
      stop();
      message(cameraError(error), true);
    } finally {
      if (token === generation) el("camera-start").disabled = false;
    }
  }

  function openVideo(file) {
    stop();
    if (file && !file.type.startsWith("video/")) {
      message("Choose a video file supported by your browser, such as MP4 or WebM.", true);
      return;
    }
    if (file) mediaUrl = URL.createObjectURL(file);
    showSource(file ? "video" : "demo", file ? file.name : "Queen honey bee laying eggs — Ask a Biologist (ASU), CC BY-SA 3.0");
    video.src = mediaUrl || "/static/comb-demo.mp4";
    video.load();
    message("Loading video…");
    const token = generation;
    video.play().catch(() => {
      if (token === generation && !video.error) message("Press play in the video, then capture a sharp frame.");
    });
  }

  function ready() {
    el("camera-capture").disabled = !source || capturing || video.readyState < 2 || video.seeking || !video.videoWidth;
  }

  async function capture() {
    if (capturing || !source || video.readyState < 2 || video.seeking || !video.videoWidth) return;
    const token = generation;
    capturing = true;
    ready();
    const at = new Date().toISOString();
    const kind = el("camera-kind").value;
    const seconds = source === "camera" ? null : video.currentTime;
    video.pause();
    try {
      const canvas = document.createElement("canvas");
      // Bound allocation for very large videos; retain native pixels up to 4K.
      const scale = Math.min(1, 4096 / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.95));
      if (token !== generation) return;
      if (!blob) throw new Error("Could not capture this frame. Try another frame or upload a photo.");
      const file = new File([blob], `${source}-${kind}-${at.replace(/[:.]/g, "-")}.jpg`, { type: "image/jpeg" });
      pending = { file, kind, metadata: { source, name: sourceName.slice(0, 200), captured_at: at,
        width: canvas.width, height: canvas.height, video_seconds: seconds } };
      stillUrl = URL.createObjectURL(blob);
      el("camera-still").src = stillUrl;
      el("camera-still").hidden = false;
      video.hidden = true;
      el("camera-capture").hidden = true;
      el("camera-kind").disabled = true;
      el("camera-review").hidden = false;
      el("camera-capture-detail").textContent = `${canvas.width} × ${canvas.height} px · ${new Date(at).toLocaleTimeString()}${seconds === null ? "" : ` · video ${seconds.toFixed(1)}s`}`;
      el("camera-add-hint").textContent = kind === "board"
        ? "Adding this photo replaces any selected sticky-board photo. Tiny mites need a sharp, detailed image."
        : source === "demo" ? "Saved as a demo analysis. It will appear in history, but will not change your hive's status or trends." : "Make sure the entire frame side is visible and in focus.";
      message("Frame captured. Check it before adding; analysis starts only when you run the inspection.");
      el("camera-add").focus();
    } catch (error) {
      if (token === generation) message(error.message || "Capture failed. Try again.", true);
    } finally {
      if (token === generation) { capturing = false; ready(); }
    }
  }

  el("source-upload").addEventListener("click", () => chooseMode(false));
  el("source-camera").addEventListener("click", () => chooseMode(true));
  el("camera-start").addEventListener("click", () => startCamera());
  el("camera-device").addEventListener("change", (e) => startCamera(e.target.value));
  el("camera-demo").addEventListener("click", () => openVideo());
  el("camera-file").addEventListener("change", (e) => {
    if (e.target.files[0]) openVideo(e.target.files[0]);
    e.target.value = "";
  });
  el("camera-stop").addEventListener("click", () => { stop(); message("Source closed. Choose a camera or video to capture another photo."); });
  el("camera-capture").addEventListener("click", capture);
  el("camera-retake").addEventListener("click", () => {
    clearStill();
    video.play().catch(() => message("Use the video controls to resume playback."));
    ready();
    el("camera-capture").focus();
  });
  el("camera-add").addEventListener("click", () => {
    if (!pending) return;
    const { file, kind, metadata } = pending;
    captureSources.set(file, metadata);
    if (!setFiles(kind, [file])) { captureSources.delete(file); return; }
    chooseMode(false);
    toast("Captured photo added. Review the hive and date, then run the inspection.");
    el("source-camera").focus();
  });
  for (const event of ["loadeddata", "canplay", "seeking", "seeked", "emptied"]) video.addEventListener(event, ready);
  video.addEventListener("loadeddata", () => { if (source && source !== "camera") message("Recorded video ready. Pause or scrub to choose a frame, then capture it."); });
  video.addEventListener("error", () => {
    if (!source) return;
    stop();
    message("This video could not be loaded or decoded. Try an MP4 file or upload a photo.", true);
  });
  window.addEventListener("hashchange", () => { if (location.hash !== "#inspect") { stop(); message("Source closed when you left the inspection."); } });
  window.addEventListener("pagehide", stop);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) return;
    if (stream || el("camera-start").disabled) { stop(); message("Camera stopped while this tab was hidden. Select Use camera to reconnect."); }
    else video.pause();
  });
})();
