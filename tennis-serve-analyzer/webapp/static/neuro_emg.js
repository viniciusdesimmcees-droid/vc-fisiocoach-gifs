/* NeuroFES — treinador "EMG-triggered" por vídeo (biofeedback de movimento).
 *
 * Honestidade: NÃO é eletromiografia de superfície. Mede a ENERGIA DE MOVIMENTO
 * numa região de interesse (ROI) sobre o membro, como PROXY da tentativa ativa.
 * Serve para (1) cuear o disparo da estimulação no momento do esforço voluntário,
 * (2) quantificar o esforço e (3) contar repetições durante a prática da tarefa.
 * Quando houver um aparelho EMG/FES real, use o gatilho nativo dele; este modo
 * é o análogo de baixo custo, que roda no navegador e offline.
 *
 * Tudo client-side, sem dependências externas.
 */
(function () {
  "use strict";
  function $(id) { return document.getElementById(id); }

  var video, stream, facing = "user";
  var proc, pctx;            // canvas de processamento (reduzido)
  var overlay, octx;         // canvas de sobreposição (ROI + HUD)
  var PW = 160, PH = 120;    // resolução de processamento
  var prevGray = null;
  var roi = { cx: 0.5, cy: 0.5, w: 0.35, h: 0.45 }; // fração do quadro
  var effort = 0, effortEMA = 0;
  var gain = 6.0;            // ganho de exibição do esforço
  var noiseFloor = 2.0;      // ruído de repouso (calibrável)
  var threshold = 25;        // limiar de disparo (0–100)
  var peakThisRep = 0;

  // estado da máquina: idle -> armed -> on -> rest -> armed ...
  var state = "idle";
  var onSecs = 6, restSecs = 12;
  var phaseEnd = 0;          // timestamp fim da fase atual
  var reps = 0, peaks = [], running = false, refractoryUntil = 0;
  var calibrating = 0;       // ms restantes de calibração de repouso
  var calibSamples = [];

  var audioCtx = null;

  function beep(freq, ms, type) {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      var o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.type = type || "sine"; o.frequency.value = freq || 880;
      o.connect(g); g.connect(audioCtx.destination);
      g.gain.setValueAtTime(0.001, audioCtx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.25, audioCtx.currentTime + 0.01);
      g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + (ms || 150) / 1000);
      o.start(); o.stop(audioCtx.currentTime + (ms || 150) / 1000 + 0.02);
    } catch (e) { /* silêncio */ }
  }

  function secureContextOK() {
    return window.isSecureContext || location.hostname === "localhost" ||
      location.hostname === "127.0.0.1";
  }

  function setStatus(msg) { if ($("emg-status")) $("emg-status").textContent = msg; }

  async function start() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Câmera não suportada neste navegador."); return;
    }
    if (!secureContextOK()) {
      setStatus("A câmera exige HTTPS no celular. Abra o app por https://."); return;
    }
    stop();
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: facing, width: { ideal: 640 }, height: { ideal: 480 } }
      });
    } catch (e) { setStatus("Não foi possível abrir a câmera: " + e.message); return; }
    video.srcObject = stream; video.play();
    running = true; state = "armed"; prevGray = null;
    setStatus("Câmera ativa. Posicione a ROI sobre a mão/punho e calibre o repouso.");
    $("btn-emg-start").disabled = true;
    $("btn-emg-stop").disabled = false;
    requestAnimationFrame(loop);
  }

  function stop() {
    running = false;
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    if ($("btn-emg-start")) $("btn-emg-start").disabled = false;
    if ($("btn-emg-stop")) $("btn-emg-stop").disabled = true;
  }

  function grayFrame() {
    pctx.drawImage(video, 0, 0, PW, PH);
    return pctx.getImageData(0, 0, PW, PH);
  }

  function computeEffort() {
    if (!video.videoWidth) return 0;
    var img;
    try { img = grayFrame(); } catch (e) { return effort; }
    var d = img.data;
    var x0 = Math.floor((roi.cx - roi.w / 2) * PW), x1 = Math.floor((roi.cx + roi.w / 2) * PW);
    var y0 = Math.floor((roi.cy - roi.h / 2) * PH), y1 = Math.floor((roi.cy + roi.h / 2) * PH);
    x0 = Math.max(0, x0); y0 = Math.max(0, y0); x1 = Math.min(PW, x1); y1 = Math.min(PH, y1);
    var gray = new Float32Array(PW * PH);
    var i, p;
    for (var y = y0; y < y1; y++) {
      for (var x = x0; x < x1; x++) {
        i = y * PW + x; p = i * 4;
        gray[i] = 0.299 * d[p] + 0.587 * d[p + 1] + 0.114 * d[p + 2];
      }
    }
    var acc = 0, n = 0;
    if (prevGray) {
      for (var yy = y0; yy < y1; yy++) {
        for (var xx = x0; xx < x1; xx++) {
          i = yy * PW + xx;
          acc += Math.abs(gray[i] - prevGray[i]); n++;
        }
      }
    }
    prevGray = gray;
    return n ? acc / n : 0;
  }

  function loop(ts) {
    if (!running) return;
    var raw = computeEffort();
    // esforço em 0–100 (subtrai ruído de repouso, aplica ganho)
    effort = Math.max(0, (raw - noiseFloor)) * gain;
    effort = Math.min(100, effort);
    effortEMA = effortEMA * 0.7 + effort * 0.3;

    if (calibrating > 0) {
      calibSamples.push(raw);
      calibrating -= 16;
      if (calibrating <= 0) finishCalib();
    }

    tick(ts || performance.now());
    draw();
    requestAnimationFrame(loop);
  }

  function finishCalib() {
    if (calibSamples.length) {
      var m = calibSamples.reduce(function (a, b) { return a + b; }, 0) / calibSamples.length;
      var mx = Math.max.apply(null, calibSamples);
      noiseFloor = mx + (mx - m) * 0.5 + 0.5; // acima do pico de ruído
      setStatus("Repouso calibrado. Peça a tentativa máxima e ajuste o limiar.");
      beep(660, 120);
    }
    calibSamples = [];
  }

  function tick(now) {
    if (state === "on" && now >= phaseEnd) {
      state = "rest"; phaseEnd = now + restSecs * 1000; beep(440, 200, "triangle");
    } else if (state === "rest" && now >= phaseEnd) {
      state = "armed"; refractoryUntil = 0;
    } else if (state === "armed") {
      if (effortEMA >= threshold && now >= refractoryUntil) {
        // disparo!
        reps++; peakThisRep = effortEMA;
        state = "on"; phaseEnd = now + onSecs * 1000;
        beep(1040, 220, "sawtooth");
        if (navigator.vibrate) navigator.vibrate(120);
      }
    }
    if (state === "on") peakThisRep = Math.max(peakThisRep, effortEMA);
    if (state === "rest" && peakThisRep > 0) { peaks.push(peakThisRep); peakThisRep = 0; }
    updateHUD(now);
  }

  function updateHUD(now) {
    $("emg-reps").textContent = reps;
    var mean = peaks.length ? Math.round(peaks.reduce(function (a, b) { return a + b; }, 0) / peaks.length) : 0;
    $("emg-mean").textContent = mean;
    $("emg-best").textContent = peaks.length ? Math.round(Math.max.apply(null, peaks)) : 0;
    $("f-reps").value = reps;
    $("f-mean").value = mean;

    var bar = $("emg-bar");
    bar.style.width = Math.round(effortEMA) + "%";
    bar.style.background = effortEMA >= threshold ? "#22c55e" : "#38bdf8";
    $("emg-thline").style.left = threshold + "%";

    var badge = $("emg-phase"), cd = "";
    if (state === "on") {
      cd = Math.ceil((phaseEnd - now) / 1000);
      badge.textContent = "ESTIMULAR AGORA — " + cd + "s";
      badge.className = "emg-phase on";
    } else if (state === "rest") {
      cd = Math.ceil((phaseEnd - now) / 1000);
      badge.textContent = "Descanso — " + cd + "s";
      badge.className = "emg-phase rest";
    } else if (state === "armed") {
      badge.textContent = "Pronto — tente o movimento";
      badge.className = "emg-phase armed";
    } else {
      badge.textContent = "Parado";
      badge.className = "emg-phase";
    }
  }

  function draw() {
    if (!octx) return;
    var W = overlay.width, H = overlay.height;
    octx.clearRect(0, 0, W, H);
    var bx = (roi.cx - roi.w / 2) * W, by = (roi.cy - roi.h / 2) * H;
    var bw = roi.w * W, bh = roi.h * H;
    octx.lineWidth = 3;
    octx.strokeStyle = state === "on" ? "#22c55e" : (effortEMA >= threshold ? "#a3e635" : "#38bdf8");
    octx.strokeRect(bx, by, bw, bh);
    octx.fillStyle = "rgba(255,255,255,.85)";
    octx.font = "13px sans-serif";
    octx.fillText("ROI (alvo)", bx + 6, by + 18);
  }

  function bindROIControls() {
    ["roi-x", "roi-y", "roi-w", "roi-h"].forEach(function (id) {
      var el = $(id); if (!el) return;
      el.addEventListener("input", function () {
        roi.cx = +$("roi-x").value / 100;
        roi.cy = +$("roi-y").value / 100;
        roi.w = +$("roi-w").value / 100;
        roi.h = +$("roi-h").value / 100;
      });
    });
    // clique/toque no vídeo reposiciona o centro da ROI
    overlay.addEventListener("click", function (ev) {
      var r = overlay.getBoundingClientRect();
      roi.cx = Math.min(0.95, Math.max(0.05, (ev.clientX - r.left) / r.width));
      roi.cy = Math.min(0.95, Math.max(0.05, (ev.clientY - r.top) / r.height));
      $("roi-x").value = Math.round(roi.cx * 100);
      $("roi-y").value = Math.round(roi.cy * 100);
    });
  }

  window.addEventListener("DOMContentLoaded", function () {
    video = $("emg-video");
    overlay = $("emg-overlay"); octx = overlay.getContext("2d");
    proc = document.createElement("canvas"); proc.width = PW; proc.height = PH;
    pctx = proc.getContext("2d", { willReadFrequently: true });

    $("btn-emg-start").addEventListener("click", start);
    $("btn-emg-stop").addEventListener("click", stop);
    $("btn-emg-switch").addEventListener("click", function () {
      facing = facing === "user" ? "environment" : "user"; start();
    });
    $("btn-emg-calib").addEventListener("click", function () {
      calibSamples = []; calibrating = 2000;
      setStatus("Calibrando repouso — mantenha o membro parado por 2 s…");
    });
    $("btn-emg-reset").addEventListener("click", function () {
      reps = 0; peaks = []; peakThisRep = 0; state = running ? "armed" : "idle";
    });

    $("thr").addEventListener("input", function () {
      threshold = +this.value; $("thr-val").textContent = threshold;
    });
    $("gain").addEventListener("input", function () {
      gain = +this.value; $("gain-val").textContent = gain.toFixed(1);
    });
    $("on-secs").addEventListener("input", function () {
      onSecs = +this.value; $("on-val").textContent = onSecs;
    });
    $("rest-secs").addEventListener("input", function () {
      restSecs = +this.value; $("rest-val").textContent = restSecs;
    });

    bindROIControls();
  });
})();
