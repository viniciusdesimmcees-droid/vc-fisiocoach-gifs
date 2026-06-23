/* Gravação pela câmera do navegador + alternância com upload.
   Honestidade técnica: o navegador NÃO acessa o modo câmera-lenta nativo do
   celular; pedimos o maior fps possível e mostramos o fps REAL entregue. Para
   240 fps de verdade, grave no app de câmera nativo e use a aba "Enviar vídeo". */

(function () {
  "use strict";

  var stream = null;
  var recorder = null;
  var chunks = [];
  var facing = "environment"; // traseira por padrão
  var recordedFps = 0;

  var $ = function (id) { return document.getElementById(id); };

  // ---- abas ----
  function showTab(name) {
    $("tab-record").classList.toggle("active", name === "record");
    $("tab-upload").classList.toggle("active", name === "upload");
    $("pane-record").style.display = name === "record" ? "block" : "none";
    $("pane-upload").style.display = name === "upload" ? "block" : "none";
  }

  function secureContextOK() {
    return window.isSecureContext ||
      location.hostname === "localhost" ||
      location.hostname === "127.0.0.1";
  }

  function setStatus(msg) { $("cam-status").textContent = msg; }

  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Câmera não suportada neste navegador.");
      return;
    }
    if (!secureContextOK()) {
      setStatus("A câmera exige HTTPS no celular. Rode o app com --https " +
        "ou use a aba 'Enviar vídeo'.");
      return;
    }
    stopStream();
    var constraints = {
      audio: false,
      video: { facingMode: facing, frameRate: { ideal: 240, min: 30 },
               width: { ideal: 1920 }, height: { ideal: 1080 } }
    };
    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (e) {
      setStatus("Não foi possível abrir a câmera: " + e.message);
      return;
    }
    var v = $("preview");
    v.srcObject = stream;
    v.play();
    var track = stream.getVideoTracks()[0];
    var s = track.getSettings ? track.getSettings() : {};
    recordedFps = Math.round(s.frameRate || 0);
    setStatus("Câmera ativa — fps real: " + (recordedFps || "?") +
      (recordedFps && recordedFps < 100
        ? "  (para câmera lenta de verdade, grave no app nativo e envie o vídeo)"
        : ""));
    $("btn-record").disabled = false;
    $("btn-switch").disabled = false;
  }

  function stopStream() {
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
  }

  function pickMime() {
    var prefs = ["video/mp4", "video/webm;codecs=vp9", "video/webm;codecs=vp8",
                 "video/webm"];
    for (var i = 0; i < prefs.length; i++) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(prefs[i]))
        return prefs[i];
    }
    return "";
  }

  function startRecording() {
    if (!stream) { setStatus("Abra a câmera primeiro."); return; }
    chunks = [];
    var mime = pickMime();
    try {
      recorder = mime ? new MediaRecorder(stream, { mimeType: mime })
                      : new MediaRecorder(stream);
    } catch (e) {
      setStatus("Gravação não suportada: " + e.message);
      return;
    }
    recorder.ondataavailable = function (ev) {
      if (ev.data && ev.data.size > 0) chunks.push(ev.data);
    };
    recorder.onstop = onRecordingStop;
    recorder.start();
    $("btn-record").textContent = "■ Parar";
    $("btn-record").classList.add("rec");
    setStatus("Gravando… capture o saque e clique em Parar.");
  }

  function onRecordingStop() {
    var type = (recorder && recorder.mimeType) || "video/webm";
    var ext = type.indexOf("mp4") >= 0 ? "mp4" : "webm";
    var blob = new Blob(chunks, { type: type });
    var file = new File([blob], "gravacao." + ext, { type: type });

    // injeta o arquivo gravado no input do formulário
    var dt = new DataTransfer();
    dt.items.add(file);
    $("video").files = dt.files;

    // prévia
    var url = URL.createObjectURL(blob);
    $("recorded").src = url;
    $("recorded-wrap").style.display = "block";

    // se o usuário deixou fps em automático/0, preenche com o fps medido
    var fpsField = $("fps");
    if (recordedFps && (!fpsField.value || fpsField.value === "0"))
      fpsField.value = recordedFps;

    setStatus("Gravação pronta ✓ — revise abaixo e clique em 'Analisar saque'.");
  }

  function toggleRecord() {
    if (recorder && recorder.state === "recording") {
      recorder.stop();
      $("btn-record").textContent = "● Gravar";
      $("btn-record").classList.remove("rec");
    } else {
      startRecording();
    }
  }

  function switchCamera() {
    facing = facing === "environment" ? "user" : "environment";
    startCamera();
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("tab-record").addEventListener("click", function () { showTab("record"); });
    $("tab-upload").addEventListener("click", function () { showTab("upload"); });
    $("btn-camera").addEventListener("click", startCamera);
    $("btn-record").addEventListener("click", toggleRecord);
    $("btn-switch").addEventListener("click", switchCamera);
    window.addEventListener("pagehide", stopStream);
  });
})();
