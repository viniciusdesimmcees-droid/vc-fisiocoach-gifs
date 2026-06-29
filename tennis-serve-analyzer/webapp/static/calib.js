/* Calibração pela quadra: extrai um quadro do vídeo escolhido (upload ou
   gravação), o usuário toca em 2 pontos de uma medida conhecida e o app calcula
   quantos pixels valem aquela distância — em RESOLUÇÃO NATIVA do vídeo. Os
   pontos vão para campos ocultos e a conta final (px) é feita no servidor. */

(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };

  var canvas, ctx, frameData = null;
  var nativeW = 0, nativeH = 0;
  var pts = [];

  function setStatus(msg) { var s = $("calib-status"); if (s) s.textContent = msg; }

  function currentVideoFile() {
    var inp = $("video");
    return inp && inp.files && inp.files[0] ? inp.files[0] : null;
  }

  function openCalib() {
    var f = currentVideoFile();
    if (!f) {
      setStatus("");
      alert("Primeiro selecione um vídeo (aba 'Enviar vídeo') ou grave um na aba 'Gravar agora'.");
      return;
    }
    $("calib-panel").style.display = "block";
    setStatus("Carregando quadro do vídeo…");

    var url = URL.createObjectURL(f);
    var v = document.createElement("video");
    v.preload = "auto"; v.muted = true; v.playsInline = true; v.src = url;

    v.addEventListener("loadeddata", function () {
      nativeW = v.videoWidth; nativeH = v.videoHeight;
      var t = Math.min(0.6, (v.duration || 1) / 3);
      try { v.currentTime = t; } catch (e) { drawFrame(v, url); }
    });
    v.addEventListener("seeked", function () { drawFrame(v, url); });
    v.addEventListener("error", function () {
      setStatus("Não foi possível ler o vídeo para calibrar. Tente a calibração manual (avançado).");
      URL.revokeObjectURL(url);
    });
  }

  function drawFrame(v, url) {
    canvas = $("calib-canvas");
    ctx = canvas.getContext("2d");
    canvas.width = nativeW;   // resolução interna = nativa → coords nativas
    canvas.height = nativeH;
    // largura de exibição responsiva
    var dispW = Math.min(canvas.parentElement.clientWidth || 340, 360);
    canvas.style.width = dispW + "px";
    canvas.style.height = (dispW * nativeH / nativeW) + "px";
    try { ctx.drawImage(v, 0, 0, nativeW, nativeH); } catch (e) {}
    try { frameData = ctx.getImageData(0, 0, nativeW, nativeH); } catch (e) { frameData = null; }
    pts = [];
    setStatus("Toque em 2 pontos da medida conhecida (ex.: base e topo da rede).");
    if (url) URL.revokeObjectURL(url);
  }

  function redrawFrame() {
    if (frameData) ctx.putImageData(frameData, 0, 0);
  }

  function marker(x, y, n) {
    ctx.fillStyle = "#22c55e";
    ctx.strokeStyle = "#06250f";
    ctx.lineWidth = Math.max(2, nativeW / 250);
    var r = Math.max(5, nativeW / 90);
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#fff";
    ctx.font = "bold " + Math.max(12, nativeW / 45) + "px sans-serif";
    ctx.fillText(String(n), x + r, y - r);
  }

  function onClick(e) {
    if (!ctx) return;
    var rect = canvas.getBoundingClientRect();
    var nx = (e.clientX - rect.left) * (canvas.width / rect.width);
    var ny = (e.clientY - rect.top) * (canvas.height / rect.height);
    if (pts.length >= 2) { redrawFrame(); pts = []; }
    pts.push([nx, ny]);
    marker(nx, ny, pts.length);
    if (pts.length === 2) {
      ctx.strokeStyle = "#22c55e";
      ctx.lineWidth = Math.max(2, nativeW / 250);
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      ctx.lineTo(pts[1][0], pts[1][1]);
      ctx.stroke();
      finalize();
    }
  }

  function finalize() {
    var dx = pts[1][0] - pts[0][0], dy = pts[1][1] - pts[0][1];
    var px = Math.sqrt(dx * dx + dy * dy);
    $("calib_p1x").value = pts[0][0].toFixed(1);
    $("calib_p1y").value = pts[0][1].toFixed(1);
    $("calib_p2x").value = pts[1][0].toFixed(1);
    $("calib_p2y").value = pts[1][1].toFixed(1);
    updateDist();
    setStatus("✓ Calibrado: " + px.toFixed(0) + " px = " +
      ($("calib_dist_m").value || "?") + " m. Pode analisar!");
  }

  function updateDist() {
    var preset = $("calib-preset").value;
    var d = preset === "custom" ? parseFloat($("calib-dist").value || "0") : parseFloat(preset);
    $("calib_dist_m").value = d > 0 ? d : "";
  }

  function onPreset() {
    var custom = $("calib-preset").value === "custom";
    $("calib-dist").style.display = custom ? "block" : "none";
    updateDist();
    if (pts.length === 2) finalize();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var b = $("btn-calib"); if (b) b.addEventListener("click", openCalib);
    var c = $("calib-canvas"); if (c) c.addEventListener("click", onClick);
    var p = $("calib-preset"); if (p) p.addEventListener("change", onPreset);
    var cd = $("calib-dist"); if (cd) cd.addEventListener("input", function () { updateDist(); if (pts.length === 2) finalize(); });
    var r = $("calib-reset"); if (r) r.addEventListener("click", function () { redrawFrame(); pts = []; setStatus("Toque em 2 pontos da medida conhecida."); });
  });
})();
