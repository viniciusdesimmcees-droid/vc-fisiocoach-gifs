"""App web do Analisador de Saque de Tênis.

Interface no navegador por cima do motor (src/): você envia o vídeo do saque,
informa a calibração e vê na tela o GIF anotado, a velocidade, os gráficos e o
relatório — no celular ou no computador.

Rodar:
    pip install -r requirements.txt -r requirements-dl.txt   # (DL opcional)
    pip install flask
    python webapp/app.py
    # abra http://localhost:5000

Por padrão usa o detector clássico (rápido, sem dependências pesadas). O
detector por deep learning e a biomecânica são opcionais (exigem torch/ultralytics).
"""

from __future__ import annotations

import os
import sys
import uuid
import traceback

from flask import Flask, request, render_template, url_for, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)

from calibration import Calibration  # noqa: E402
from ball_tracker import BallTracker  # noqa: E402
from speed_estimator import estimate  # noqa: E402
import report  # noqa: E402

RESULTS_DIR = os.path.join(HERE, "static", "results")
UPLOADS_DIR = os.path.join(HERE, "uploads")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # 300 MB


def _f(name: str, default: float) -> float:
    try:
        return float(request.form.get(name, default))
    except (TypeError, ValueError):
        return default


STATIC = os.path.join(HERE, "static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(
        STATIC, "manifest.webmanifest", mimetype="application/manifest+json"
    )


@app.route("/sw.js")
def service_worker():
    # servido a partir da raiz para controlar todo o app (escopo "/")
    resp = send_from_directory(STATIC, "sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.route("/analyze", methods=["POST"])
def analyze():
    video = request.files.get("video")
    if not video or video.filename == "":
        return render_template("index.html", error="Selecione um vídeo do saque."), 400

    job = uuid.uuid4().hex[:10]
    job_dir = os.path.join(RESULTS_DIR, job)
    os.makedirs(job_dir, exist_ok=True)
    in_path = os.path.join(UPLOADS_DIR, f"{job}_{video.filename}")
    video.save(in_path)

    athlete = request.form.get("athlete", "Atleta").strip() or "Atleta"
    ref_m = _f("ref_length_m", 1.0)
    ref_px = _f("ref_length_px", 200.0)
    fps_override = _f("fps", 0.0)
    detector = request.form.get("detector", "classic")
    run_biomech = request.form.get("biomech") == "on"

    try:
        # ---- rastreio da bola ----
        if detector == "dl":
            from detector_dl import DLBallDetector

            ball_class = int(_f("ball_class", 32))
            tracker = DLBallDetector(
                model_path=request.form.get("model", "yolov8n.pt") or "yolov8n.pt",
                conf=_f("conf", 0.10),
                classes=(ball_class,),
            )
        else:
            tracker = BallTracker()
        trajectory, meta = tracker.track(in_path)

        fps = fps_override if fps_override > 0 else meta["fps"]
        if not fps or fps <= 0:
            raise ValueError(
                "fps inválido. Informe o fps real da captura no formulário."
            )

        calib = Calibration.from_reference(ref_m, ref_px, fps)
        result = estimate(trajectory, calib)

        base = os.path.join(job_dir, "saque")
        report.write_trajectory_csv(base + "_trajetoria.csv", trajectory)
        report.write_speed_plot(base + "_velocidade.png", result, athlete)
        summary = report.write_summary_json(
            base + "_resumo.json", athlete, result, meta, calib.meters_per_pixel
        )
        report.write_annotated_gif(in_path, base + "_anotado.gif", trajectory, result)
        report.write_annotated_video(in_path, base + "_anotado.mp4", trajectory, result)

        ctx = {
            "athlete": athlete,
            "summary": summary,
            "detector": detector,
            "gif": url_for("static", filename=f"results/{job}/saque_anotado.gif"),
            "mp4": url_for("static", filename=f"results/{job}/saque_anotado.mp4"),
            "plot": url_for("static", filename=f"results/{job}/saque_velocidade.png"),
            "csv": url_for("static", filename=f"results/{job}/saque_trajetoria.csv"),
            "json": url_for("static", filename=f"results/{job}/saque_resumo.json"),
            "biomech": None,
        }

        # ---- biomecânica (opcional) ----
        if run_biomech:
            ctx["biomech"] = _run_biomech(in_path, job_dir, job, athlete, fps)

        return render_template("result.html", **ctx)

    except Exception as e:  # mostra o erro de forma amigável
        traceback.print_exc()
        return render_template("index.html", error=f"Falha na análise: {e}"), 500


def _run_biomech(in_path, job_dir, job, athlete, fps):
    from pose_estimator import PoseEstimator
    from biomechanics import (
        choose_serve_side, compute_angles, segment_phases, kinematic_sequence,
    )
    import biomech_report as br

    pose = PoseEstimator(model_path="yolov8n-pose.pt")
    frames, pmeta = pose.estimate_video(in_path)
    side = choose_serve_side(frames)
    angles = compute_angles(frames, side)
    phases = segment_phases(angles)
    chain = kinematic_sequence(angles, fps)

    b = os.path.join(job_dir, "biomech")
    br.write_angles_plot(b + "_angulos.png", angles, phases, fps, athlete)
    bsummary = br.write_summary_json(
        b + "_resumo.json", athlete, side, angles, phases, chain,
        {**pmeta, "fps": fps},
    )
    return {
        "summary": bsummary,
        "plot": url_for("static", filename=f"results/{job}/biomech_angulos.png"),
        "json": url_for("static", filename=f"results/{job}/biomech_resumo.json"),
    }


def _self_signed_cert():
    """Gera (uma vez) um certificado autoassinado via openssl e retorna
    (cert, key). Usa o módulo ssl puro do Python — não depende de 'cryptography'.
    Cai para 'adhoc' se o openssl não estiver disponível."""
    import subprocess

    cert_dir = os.path.join(HERE, "certs")
    os.makedirs(cert_dir, exist_ok=True)
    cert = os.path.join(cert_dir, "cert.pem")
    key = os.path.join(cert_dir, "key.pem")
    if not (os.path.exists(cert) and os.path.exists(key)):
        try:
            subprocess.run(
                ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", key, "-out", cert, "-days", "365",
                 "-subj", "/CN=fisiocoach.local"],
                check=True, capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            print("openssl indisponível; usando ssl_context='adhoc'.")
            return "adhoc"
    return (cert, key)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="App web do Analisador de Saque")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument(
        "--https",
        action="store_true",
        help="HTTPS com certificado autoassinado (necessário p/ câmera no celular)",
    )
    args = ap.parse_args()

    ssl_ctx = None
    if args.https:
        ssl_ctx = _self_signed_cert()
        print("HTTPS ligado (certificado autoassinado) — o navegador vai pedir "
              "para confiar no certificado na primeira vez. Necessário para usar "
              "a câmera do celular.")
    app.run(host=args.host, port=args.port, debug=False, ssl_context=ssl_ctx)
