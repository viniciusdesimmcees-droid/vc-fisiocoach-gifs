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

from flask import (
    Flask, request, render_template, url_for, send_from_directory, Response, abort,
    redirect,
)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)
sys.path.insert(0, HERE)

from calibration import Calibration  # noqa: E402
from ball_tracker import BallTracker  # noqa: E402
from speed_estimator import estimate  # noqa: E402
import report  # noqa: E402
import history  # noqa: E402
import reportpro  # noqa: E402
import insights  # noqa: E402
import didactic  # noqa: E402
import references  # noqa: E402
import engine  # noqa: E402
import strokes  # noqa: E402
import posture  # noqa: E402
import ballcal  # noqa: E402
import confidence  # noqa: E402
import preflight  # noqa: E402
import validation  # noqa: E402
import benchmark  # noqa: E402
import metrics  # noqa: E402
import ballpath  # noqa: E402
import storage  # noqa: E402

history.init_db()

RESULTS_DIR = os.path.join(HERE, "static", "results")
UPLOADS_DIR = os.path.join(HERE, "uploads")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

# Largura máxima de processamento no servidor: reduz vídeos grandes (1080p+)
# para caber na memória/tempo de planos pequenos (ex.: Render free, 512 MB).
PROC_MAX_WIDTH = int(os.environ.get("PROC_MAX_WIDTH", "540"))
# Limite de quadros processados (evita estourar o tempo em vídeos longos).
PROC_MAX_FRAMES = int(os.environ.get("PROC_MAX_FRAMES", "900"))
# Gerar o MP4 anotado (passada extra, cara em CPU fraca). Por padrão só o GIF.
MAKE_MP4 = os.environ.get("MAKE_MP4", "0") == "1"
# Pose (biomecânica): reduz resolução e limita quadros. Com mais CPU (plano
# pago) dá para processar mais quadros — o teto sobe para 240.
POSE_MAX_WIDTH = int(os.environ.get("POSE_MAX_WIDTH", "640"))
POSE_MAX_FRAMES = min(int(os.environ.get("POSE_MAX_FRAMES", "150")), 240)

# Deep learning (detector YOLOv8 + biomecânica) só está disponível se torch e
# ultralytics estiverem instalados — não estão no plano grátis. Detectamos uma
# vez para esconder as opções na tela e cair no clássico automaticamente.
import importlib.util as _ilu

DL_AVAILABLE = (
    _ilu.find_spec("torch") is not None and _ilu.find_spec("ultralytics") is not None
)


def _f(name: str, default: float) -> float:
    try:
        return float(request.form.get(name, default))
    except (TypeError, ValueError):
        return default


STATIC = os.path.join(HERE, "static")


# ---------- histórico do atleta ----------
@app.route("/historico")
def historico():
    return render_template("historico.html", athletes=history.list_athletes(),
                           persist=storage.status())


@app.route("/persistencia")
def persistencia():
    return render_template("persistencia.html", persist=storage.status())


@app.route("/historico/<athlete>")
def historico_atleta(athlete):
    h = history.get_history(athlete)
    profile = history.get_profile(athlete)
    posturas = history.get_posture_history(athlete)
    if not h and not profile and not posturas:
        abort(404)
    return render_template(
        "atleta.html",
        athlete=athlete,
        stats=history.athlete_stats(athlete) if h else {},
        rows=list(reversed(h)),  # mais recentes primeiro na tabela
        posturas=list(reversed(posturas)),
        profile=profile,
        age=history.age_from_birthdate(profile.get("birthdate")) if profile else None,
        imc=history.bmi(profile.get("height_cm"), profile.get("weight_kg")) if profile else None,
    )


@app.route("/atleta/<athlete>/ficha", methods=["GET", "POST"])
def ficha_atleta(athlete):
    if request.method == "POST":
        data = {f: (request.form.get(f) or None) for f in history.ATHLETE_FIELDS}
        history.save_profile(athlete, data)
        return redirect(url_for("historico_atleta", athlete=athlete))
    return render_template(
        "ficha.html", athlete=athlete, profile=history.get_profile(athlete) or {}
    )


@app.route("/analise/<int:analysis_id>/excluir", methods=["POST"])
def excluir_analise(analysis_id):
    athlete = request.form.get("athlete", "")
    history.delete_analysis(analysis_id)
    return redirect(url_for("historico_atleta", athlete=athlete)
                    if athlete else url_for("historico"))


@app.route("/analise/<int:analysis_id>/editar", methods=["POST"])
def editar_analise(analysis_id):
    athlete = request.form.get("athlete", "")
    history.update_analysis(
        analysis_id,
        peak_kmh=request.form.get("peak_kmh") or None,
        mean_kmh=request.form.get("mean_kmh") or None,
        created_at=request.form.get("created_at") or None,
    )
    return redirect(url_for("historico_atleta", athlete=athlete)
                    if athlete else url_for("historico"))


@app.route("/postura/<int:assessment_id>/imagem.png")
def postura_imagem(assessment_id):
    data = history.get_posture_image(assessment_id)
    if not data:
        abort(404)
    return Response(data, mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.route("/postura/<int:assessment_id>/excluir", methods=["POST"])
def excluir_postura(assessment_id):
    athlete = request.form.get("athlete", "")
    history.delete_posture(assessment_id)
    return redirect(url_for("historico_atleta", athlete=athlete)
                    if athlete else url_for("historico"))


@app.route("/atleta/<athlete>/renomear", methods=["POST"])
def renomear_atleta(athlete):
    novo = (request.form.get("novo_nome") or "").strip()
    if novo and novo != athlete:
        history.rename_athlete(athlete, novo)
        return redirect(url_for("historico_atleta", athlete=novo))
    return redirect(url_for("historico_atleta", athlete=athlete))


@app.route("/atleta/<athlete>/excluir", methods=["POST"])
def excluir_atleta(athlete):
    history.delete_athlete(athlete)
    return redirect(url_for("historico"))


@app.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    if request.method == "POST":
        # as marcadas para PARTICIPAR vêm no form; as ausentes ficam excluídas
        incluidas = set(request.form.getlist("metrica"))
        excluidas = [k for k, _ in metrics.METRIC_REGISTRY if k not in incluidas]
        history.set_excluded_metrics(excluidas)
        return redirect(url_for("configuracoes", salvo=1))
    excluidas = history.get_excluded_metrics()
    return render_template(
        "configuracoes.html",
        metricas=metrics.METRIC_REGISTRY,
        excluidas=excluidas,
        salvo=request.args.get("salvo"),
    )


def _montar_objetivo(profile, inteligencia):
    """Texto de objetivo para o atleta: metas da ficha + foco do plano."""
    partes = []
    if profile and profile.get("goals"):
        partes.append(f"Meta do atleta: {profile['goals']}.")
    if inteligencia and inteligencia.get("treino"):
        partes.append(inteligencia["treino"])
    if inteligencia and inteligencia.get("musculos"):
        grupos = ", ".join(m["grupo"].replace("_", " ")
                           for m in inteligencia["musculos"][:3])
        partes.append(f"Prioridade física da fase: {grupos}.")
    if not partes:
        partes.append("Evoluir a técnica e a potência do saque com consistência e "
                      "prevenção de lesões, acompanhando a evolução ao longo do tempo.")
    return " ".join(partes)


def _build_dossier_bytes(athlete, profile, h, posturas):
    """Gera o PDF do laudo consolidado e devolve os bytes."""
    import tempfile

    stats = history.athlete_stats(athlete) if h else {}
    serve_png = history.evolution_png(athlete) if h else None
    posture_png = history.posture_evolution_png(athlete) if posturas else None
    last_post = posturas[-1] if posturas else None
    golpe, inteligencia = history.latest_extras(athlete)

    tmp_imgs = []

    def _img_tmp(assessment_id):
        b = history.get_posture_image(assessment_id)
        if not b:
            return None
        fd_i, p_i = tempfile.mkstemp(suffix=".png")
        with os.fdopen(fd_i, "wb") as f:
            f.write(b)
        tmp_imgs.append(p_i)
        return p_i

    com_foto = [p for p in posturas if p.get("tem_imagem")]
    first_img = _img_tmp(com_foto[0]["id"]) if com_foto else None
    last_img = _img_tmp(com_foto[-1]["id"]) if com_foto else None
    all_serves = [
        {"data": (a.get("created_at") or "")[:10], "peak": a.get("peak_kmh"),
         "nivel": reportpro.classify(a.get("peak_kmh") or 0)["nivel"]}
        for a in h
    ]
    objetivo = _montar_objetivo(profile, inteligencia)

    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        reportpro.write_athlete_dossier_pdf(
            tmp, athlete, profile,
            history.age_from_birthdate(profile.get("birthdate")) if profile else None,
            history.bmi(profile.get("height_cm"), profile.get("weight_kg")) if profile else None,
            stats, serve_png, posture_png, last_post, last_img,
            golpe=golpe, inteligencia=inteligencia,
            all_serves=all_serves, posture_first_img=first_img,
            posturas=posturas, objetivo=objetivo,
        )
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        for p_i in tmp_imgs + [tmp]:
            try:
                os.remove(p_i)
            except OSError:
                pass


@app.route("/historico/<athlete>/laudo.pdf")
def laudo_atleta(athlete):
    profile = history.get_profile(athlete)
    h = history.get_history(athlete)
    posturas = history.get_posture_history(athlete)
    if not h and not profile and not posturas:
        abort(404)
    data = _build_dossier_bytes(athlete, profile, h, posturas)
    return Response(
        data, mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="laudo_{athlete}.pdf"'},
    )


@app.route("/analise/<int:analysis_id>/percurso.png")
def analise_percurso(analysis_id):
    data = history.get_analysis_traj(analysis_id)
    if not data:
        abort(404)
    return Response(data, mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.route("/historico/<athlete>/exportar.zip")
def exportar_atleta(athlete):
    """Livro de dados do atleta: PDF completo + JSON + todas as fotos + percursos."""
    import io
    import json as _json
    import zipfile

    profile = history.get_profile(athlete)
    h = history.get_history(athlete)
    posturas = history.get_posture_history(athlete)
    if not h and not profile and not posturas:
        abort(404)

    def _safe(s):
        return "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in str(s))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # 1) laudo consolidado (PDF completo)
        try:
            z.writestr(f"{_safe(athlete)}/laudo_completo.pdf",
                       _build_dossier_bytes(athlete, profile, h, posturas))
        except Exception:
            traceback.print_exc()
        # 2) dados brutos (JSON)
        z.writestr(f"{_safe(athlete)}/dados.json",
                   _json.dumps(history.export_data(athlete), ensure_ascii=False,
                               indent=2, default=str))
        # 3) gráficos de evolução
        if h:
            z.writestr(f"{_safe(athlete)}/graficos/evolucao_saque.png",
                       history.evolution_png(athlete))
        if posturas:
            z.writestr(f"{_safe(athlete)}/graficos/evolucao_postural.png",
                       history.posture_evolution_png(athlete))
        # 4) fotos das avaliações posturais
        for p in posturas:
            img = history.get_posture_image(p["id"]) if p.get("tem_imagem") else None
            if img:
                d = (p.get("created_at") or "")[:10]
                z.writestr(f"{_safe(athlete)}/fotos_avaliacao/{d}_id{p['id']}.png", img)
        # 5) percursos da bola (print do scanner) de cada saque
        for a in h:
            tb = history.get_analysis_traj(a["id"]) if a.get("tem_percurso") else None
            if tb:
                d = (a.get("created_at") or "")[:10]
                z.writestr(f"{_safe(athlete)}/percurso_bola/{d}_id{a['id']}_"
                           f"{(a.get('peak_kmh') or 0):.0f}kmh.png", tb)
        # 6) leia-me
        z.writestr(f"{_safe(athlete)}/LEIA-ME.txt",
                   "Livro de dados do atleta — VF Tenis Scanner\n"
                   "Sistema criado e desenvolvido por Vinicius Camargos da Fonseca.\n\n"
                   "Conteudo:\n"
                   "- laudo_completo.pdf: relatorio consolidado (ficha, saque, golpe, "
                   "postura, plano, historico e objetivo)\n"
                   "- dados.json: todos os dados brutos do atleta\n"
                   "- graficos/: evolucao do saque e da postura\n"
                   "- fotos_avaliacao/: fotos anotadas de cada avaliacao postural\n"
                   "- percurso_bola/: o caminho da bola rastreado pelo scanner em cada saque\n")

    return Response(
        buf.getvalue(), mimetype="application/zip",
        headers={"Content-Disposition":
                 f'attachment; filename="livro_dados_{_safe(athlete)}.zip"'},
    )


@app.route("/chart/evolucao/<athlete>.png")
def chart_evolucao(athlete):
    return Response(history.evolution_png(athlete), mimetype="image/png")


@app.route("/chart/postura/<athlete>.png")
def chart_postura(athlete):
    return Response(history.posture_evolution_png(athlete), mimetype="image/png")


@app.route("/chart/comparacao.png")
def chart_comparacao():
    return Response(history.comparison_png(), mimetype="image/png")


@app.errorhandler(413)
def too_large(_e):
    return render_template(
        "index.html",
        error="Vídeo muito grande (máx. 200 MB). Envie um clipe curto do saque.",
    ), 413


@app.errorhandler(500)
def server_error(_e):
    return render_template(
        "index.html",
        error="Algo deu errado ao processar o vídeo. Tente um clipe mais curto "
        "ou confira a calibração. Se persistir, me avise.",
    ), 500


@app.route("/")
def index():
    return render_template("index.html", dl_available=DL_AVAILABLE)


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _downscale_bgr(img, max_width):
    import cv2

    h, w = img.shape[:2]
    if max_width and w > max_width:
        s = max_width / w
        img = cv2.resize(img, (round(w * s), round(h * s)))
    return img


def _best_pose_frame(path):
    """Extrai o quadro com a melhor pose (corpo inteiro) de uma foto ou vídeo.
    Retorna (imagem_bgr, keypoints) ou (None, None)."""
    import cv2
    from pose_estimator import PoseEstimator

    pose = PoseEstimator(model_path="yolov8n-pose.pt")
    ext = os.path.splitext(path)[1].lower()

    if ext in IMAGE_EXTS:
        img = cv2.imread(path)
        if img is None:
            return None, None
        img = _downscale_bgr(img, POSE_MAX_WIDTH)
        return img, pose.estimate_frame(img)

    # vídeo: amostra alguns quadros e escolhe o de pose mais completa
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None, None
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    idxs = (list(range(0, n, max(1, n // 8)))[:8] if n > 0 else list(range(0, 8)))
    trunk = [posture.L_SH, posture.R_SH, posture.L_HIP, posture.R_HIP,
             posture.L_KNEE, posture.R_KNEE, posture.L_ANK, posture.R_ANK]
    best_img, best_kp, best_score = None, None, -1.0
    for i in idxs:
        if n > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            continue
        frame = _downscale_bgr(frame, POSE_MAX_WIDTH)
        kp = pose.estimate_frame(frame)
        if kp is None:
            continue
        score = float(sum(kp[j][2] for j in trunk))
        if score > best_score:
            best_img, best_kp, best_score = frame, kp, score
    cap.release()
    return best_img, best_kp


@app.route("/postura")
def postura():
    return render_template("postura.html", dl_available=DL_AVAILABLE)


@app.route("/postura/analisar", methods=["POST"])
def postura_analisar():
    if not DL_AVAILABLE:
        return render_template(
            "postura.html", dl_available=False,
            error="A avaliação postural usa detecção de pose (deep learning), "
            "indisponível neste ambiente.",
        ), 400

    media = request.files.get("media")
    if not media or media.filename == "":
        return render_template(
            "postura.html", dl_available=True,
            error="Envie uma foto ou vídeo do atleta (de frente, costas ou lado).",
        ), 400

    athlete = request.form.get("athlete", "Atleta").strip() or "Atleta"
    view = request.form.get("view", "frente")

    job = uuid.uuid4().hex[:10]
    job_dir = os.path.join(RESULTS_DIR, job)
    os.makedirs(job_dir, exist_ok=True)
    in_path = os.path.join(UPLOADS_DIR, f"post_{job}_{media.filename}")
    media.save(in_path)

    try:
        import cv2

        img, kp = _best_pose_frame(in_path)
        if kp is None or img is None:
            return render_template(
                "postura.html", dl_available=True,
                error="Não consegui identificar a pessoa. Use boa luz, corpo "
                "inteiro no quadro e fundo limpo (de frente, costas ou lado).",
            ), 400

        resultado = posture.analyze(kp, view)
        if not resultado:
            return render_template(
                "postura.html", dl_available=True,
                error="Pose insuficiente para medir. Garanta o corpo inteiro "
                "visível e ereto no quadro.",
            ), 400

        annotated = posture.annotate(img, kp, view)
        annot_path = os.path.join(job_dir, "postura_anotada.png")
        cv2.imwrite(annot_path, annotated)
        img_url = url_for("static", filename=f"results/{job}/postura_anotada.png")
        # bytes da foto anotada para guardar no banco (permanente / comparativo)
        ok_enc, buf_png = cv2.imencode(".png", annotated)
        img_bytes = buf_png.tobytes() if ok_enc else None

        # salva no histórico do atleta (evolução postural ao longo do tempo)
        assessment_id = None
        try:
            assessment_id = history.record_posture(
                athlete, view, resultado, img_url, image_bytes=img_bytes
            )
        except Exception:
            traceback.print_exc()  # histórico não pode derrubar o resultado
        # usa a imagem permanente do banco quando disponível
        if assessment_id:
            img_url = url_for("postura_imagem", assessment_id=assessment_id)

        pdf_ok = True
        try:
            reportpro.write_posture_pdf(
                os.path.join(job_dir, "postura_laudo.pdf"),
                athlete, resultado, annot_path,
            )
        except Exception:
            traceback.print_exc()
            pdf_ok = False

        return render_template(
            "postura_result.html",
            athlete=athlete,
            resultado=resultado,
            view_label={"frente": "de frente", "costas": "de costas",
                        "lado": "de lado", "lateral": "de lado"}.get(view, view),
            imagem=img_url,
            pdf=url_for("static", filename=f"results/{job}/postura_laudo.pdf") if pdf_ok else None,
            history_url=url_for("historico_atleta", athlete=athlete),
        )
    except Exception as e:
        traceback.print_exc()
        return render_template(
            "postura.html", dl_available=True,
            error=f"Falha na avaliação postural: {e}",
        ), 500
    finally:
        try:
            os.remove(in_path)
        except OSError:
            pass


@app.route("/protocolo")
def protocolo():
    return render_template("protocolo.html")


@app.route("/validacao")
def validacao():
    return render_template(
        "validacao.html",
        spec=validation.accuracy_spec(),
        drops=validation.drop_table(),
        ref_speeds=validation.REF_SPEEDS,
        metodologia=validation.METODOLOGIA,
    )


@app.route("/validacao/ficha.pdf")
def ficha_tecnica():
    import tempfile

    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        reportpro.write_spec_pdf(
            tmp, validation.accuracy_spec(), validation.drop_table(),
            validation.REF_SPEEDS, validation.METODOLOGIA,
        )
        with open(tmp, "rb") as f:
            data = f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return Response(
        data, mimetype="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ficha_tecnica_acuracia.pdf"'},
    )


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

    # CALIBRAÇÃO. Prioridade: 2 pontos na quadra > manual (px) > automática
    # pela bola (6,7 cm). A escala da bola também CRUZA com a manual para
    # confirmar a medição. A falta de calibração só falha se a bola também não
    # puder calibrar (decidido após o rastreio).
    ref_m = ref_px = None
    cal_dist = _f("calib_dist_m", 0.0)
    p1x, p1y = _f("calib_p1x", -1), _f("calib_p1y", -1)
    p2x, p2y = _f("calib_p2x", -1), _f("calib_p2y", -1)
    if cal_dist > 0 and min(p1x, p1y, p2x, p2y) >= 0:
        px = ((p2x - p1x) ** 2 + (p2y - p1y) ** 2) ** 0.5
        if px > 1:
            ref_px, ref_m = px, cal_dist
    if ref_px is None:
        m_in, px_in = _f("ref_length_m", 0.0), _f("ref_length_px", 0.0)
        if m_in > 0 and px_in > 0:
            ref_m, ref_px = m_in, px_in

    ball_d_cm = _f("ball_diameter_cm", 6.7)
    ball_d_m = ball_d_cm / 100.0 if ball_d_cm > 0 else ballcal.BALL_DIAMETER_M

    fps_override = _f("fps", 0.0)
    detector = request.form.get("detector", "classic")
    run_biomech = request.form.get("biomech") == "on"
    golpe_manual = request.form.get("stroke", "auto")  # auto/saque/forehand/backhand

    # Deep learning indisponível (plano grátis): cai no clássico em vez de falhar.
    if detector == "dl" and not DL_AVAILABLE:
        detector = "classic"

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
        # Reduz vídeos grandes no servidor (memória/tempo em planos pequenos).
        trajectory, meta = tracker.track(
            in_path, max_width=PROC_MAX_WIDTH, max_frames=PROC_MAX_FRAMES
        )
        scale = meta.get("scale", 1.0)

        fps = fps_override if fps_override > 0 else meta["fps"]
        if not fps or fps <= 0:
            raise ValueError(
                "fps inválido. Informe o fps real da captura no formulário."
            )

        # escala automática pela bola (régua independente, mesmo plano de voo)
        ball_global = ballcal.ball_scale(trajectory, ball_d_m)

        # decide a calibração: manual quando houver; senão, pela bola
        if ref_px is not None and ref_m is not None:
            # A referência foi medida na resolução original; ajusta para a escala
            # reduzida em que o rastreio rodou (mantém a velocidade correta).
            calib = Calibration.from_reference(ref_m, ref_px * scale, fps)
            calib_mode = "manual"
        elif ball_global:
            calib = Calibration(meters_per_pixel=ball_global["mpp"], fps=fps)
            calib_mode = "ball"
        else:
            try:
                os.remove(in_path)
            except OSError:
                pass
            return render_template(
                "index.html",
                error="Não foi possível calibrar: a bola não foi detectada o "
                "suficiente para a calibração automática. Calibre tocando em 2 "
                "pontos de uma medida conhecida na quadra (ex.: altura da rede = "
                "0,914 m) e informe a distância.",
            ), 400

        result = estimate(trajectory, calib)

        # cruzamento de escalas (confiabilidade): mede a bola no plano do impacto
        ball_impact = ballcal.ball_scale(
            trajectory, ball_d_m, impact_frame=result.impact_frame
        ) or ball_global
        calib_cross = None
        if calib_mode == "manual" and ball_impact:
            calib_cross = ballcal.cross_check(
                calib.meters_per_pixel, ball_impact["mpp"], result.peak_kmh
            )
        calibracao = {
            "modo": calib_mode,
            "bola": ball_impact,
            "cross": calib_cross,
            "ball_diameter_cm": round(ball_d_m * 100, 1),
        }

        # ---- avisos automáticos de confiabilidade ----
        avisos = []
        if calib_mode == "ball":
            avisos.append(
                f"Calibração automática pela bola ({calibracao['ball_diameter_cm']:.1f} cm). "
                "Funciona bem com a bola nítida e de lado; para máxima precisão, "
                "calibre também tocando em 2 pontos na quadra (uma confirma a outra)."
            )
        if calib_cross and calib_cross["nivel"] == "baixa":
            avisos.append(
                f"{calib_cross['verdict']}. A bola (6,7 cm) sugere ~"
                f"{calib_cross['ball_peak_kmh']:.0f} km/h. Refaça a calibração da "
                "quadra: provavelmente os 2 pontos ou a distância informada estão errados."
            )
        elif calib_cross and calib_cross["nivel"] == "media":
            avisos.append(
                f"{calib_cross['verdict']} (diferença de {calib_cross['abs_pct']:.0f}% "
                f"entre a quadra e a bola; a bola sugere ~{calib_cross['ball_peak_kmh']:.0f} km/h)."
            )
        file_fps = meta.get("fps") or 0
        if fps < 100:
            avisos.append(
                f"fps baixo ({fps:.0f}). Saques rápidos (150+ km/h) exigem câmera "
                "lenta de 120–240 fps. Com fps baixo, a velocidade fica imprecisa."
            )
        elif file_fps and abs(file_fps - fps) > 5:
            avisos.append(
                f"O arquivo informa {file_fps:.0f} fps, mas você usou {fps:.0f}. "
                "Confirme o fps real da câmera lenta — isso afeta diretamente a velocidade."
            )
        if meta.get("detections", 0) < 8:
            avisos.append(
                "Poucas detecções da bola — confira iluminação, contraste da bola e "
                "o enquadramento (câmera lateral, bola visível)."
            )

        # selo de confiança da medição (fps + calibração cruzada + rastreio)
        conf = confidence.evaluate(result, meta, fps, file_fps, calibracao)
        # pré-voo: qualidade da captura (lixo entra, lixo sai)
        captura = preflight.check(trajectory, meta, result, calib, calibracao)

        base = os.path.join(job_dir, "saque")
        report.write_trajectory_csv(base + "_trajetoria.csv", trajectory)
        report.write_speed_plot(base + "_velocidade.png", result, athlete)
        summary = report.write_summary_json(
            base + "_resumo.json", athlete, result, meta, calib.meters_per_pixel
        )
        # ---- biomecânica (opcional) — roda ANTES do PDF para entrar nele ----
        biomech = None
        if run_biomech and DL_AVAILABLE:
            try:
                biomech = _run_biomech(in_path, job_dir, job, athlete, fps)
            except Exception:
                traceback.print_exc()  # biomecânica é extra: não derruba o resultado

        # avaliação técnica (nota + recomendações)
        bio_summary = biomech.get("summary") if biomech else None
        evalu = insights.evaluate(summary, bio_summary)

        # ---- golpe (auto pela pose + escolha manual do profissional) ----
        stroke_auto = biomech.get("stroke_auto") if biomech else None
        if golpe_manual and golpe_manual != "auto":
            golpe = strokes.manual(golpe_manual)
            if golpe and stroke_auto and stroke_auto.get("golpe") != golpe_manual:
                golpe["sugestao_auto"] = stroke_auto  # mostra divergência
        else:
            golpe = stroke_auto

        # relatório profissional: classificação + velocímetro + PDF
        cls = reportpro.classify(result.peak_kmh)
        # camada didática (linguagem simples para o aluno)
        didatico = didactic.student_summary(summary, evalu, cls["nivel"])
        glossario = didactic.glossario(bool(biomech))
        # métricas que o operador marcou para não participar da leitura
        try:
            excluded_metrics = history.get_excluded_metrics()
        except Exception:
            excluded_metrics = set()
        # comparação com referências científicas
        referencias = references.compare(summary, bio_summary, excluded_metrics)
        # motor inteligente: risco de lesão + músculos + treino (usa a ficha)
        try:
            profile = history.get_profile(athlete)
        except Exception:
            profile = None
        inteligencia = engine.evaluate(summary, bio_summary, profile)

        # benchmark vs. profissional (percentil + radar + o que falta para o pro)
        bench = benchmark.evaluate(summary, bio_summary, excluded_metrics)
        radar_url = None
        if bench and bench.get("tem_radar"):
            try:
                with open(base + "_radar.png", "wb") as _rf:
                    _rf.write(benchmark.radar_png(bench["metricas"]))
                radar_url = url_for("static", filename=f"results/{job}/saque_radar.png")
            except Exception:
                traceback.print_exc()

        # percurso da bola (o 'print' do caminho rastreado) — guardado no banco
        try:
            traj_bytes = ballpath.trajectory_png(trajectory, meta, result)
        except Exception:
            traceback.print_exc()
            traj_bytes = None

        # registra no histórico do atleta (com golpe + plano + percurso do dia)
        if result.peak_kmh > 0:
            try:
                history.record_analysis(
                    athlete, result.peak_kmh, result.mean_kmh, fps, detector,
                    stroke=golpe, intel=inteligencia, traj_bytes=traj_bytes,
                )
            except Exception:
                traceback.print_exc()  # histórico não pode derrubar o resultado

        reportpro.write_gauge_png(base + "_gauge.png", result.peak_kmh, cls)
        try:
            reportpro.write_report_pdf(
                base + "_relatorio.pdf", athlete, summary, cls,
                base + "_velocidade.png",
                biomech=bio_summary,
                biomech_png=biomech.get("plot_path") if biomech else None,
                evalu=evalu,
                didatico_texto=didactic.plain_text(summary, evalu),
                referencias=referencias,
                glossario=glossario,
                inteligencia=inteligencia,
                golpe=golpe,
                calibracao=calibracao,
                confianca=conf,
                captura=captura,
                benchmark=bench,
                radar_png=base + "_radar.png" if radar_url else None,
            )
            pdf_ok = True
        except Exception:
            traceback.print_exc()
            pdf_ok = False

        report.write_annotated_gif(
            in_path, base + "_anotado.gif", trajectory, result, proc_scale=scale,
            max_width=420, max_frames=50, fps_out=15.0,
        )
        mp4_url = None
        if MAKE_MP4:
            report.write_annotated_video(
                in_path, base + "_anotado.mp4", trajectory, result, proc_scale=scale
            )
            mp4_url = url_for("static", filename=f"results/{job}/saque_anotado.mp4")

        ctx = {
            "athlete": athlete,
            "summary": summary,
            "detector": detector,
            "cls": cls,
            "evalu": evalu,
            "avisos": avisos,
            "didatico": didatico,
            "glossario": glossario,
            "referencias": referencias,
            "inteligencia": inteligencia,
            "golpe": golpe,
            "calibracao": calibracao,
            "confianca": conf,
            "captura": captura,
            "benchmark": bench,
            "radar": radar_url,
            "bands": reportpro.BANDS,
            "history_url": url_for("historico_atleta", athlete=athlete),
            "gauge": url_for("static", filename=f"results/{job}/saque_gauge.png"),
            "pdf": url_for("static", filename=f"results/{job}/saque_relatorio.pdf") if pdf_ok else None,
            "gif": url_for("static", filename=f"results/{job}/saque_anotado.gif"),
            "mp4": mp4_url,
            "plot": url_for("static", filename=f"results/{job}/saque_velocidade.png"),
            "csv": url_for("static", filename=f"results/{job}/saque_trajetoria.csv"),
            "json": url_for("static", filename=f"results/{job}/saque_resumo.json"),
            "biomech": biomech,
        }

        return render_template("result.html", **ctx)

    except Exception as e:  # mostra o erro de forma amigável
        traceback.print_exc()
        return render_template("index.html", error=f"Falha na análise: {e}"), 500
    finally:
        # libera o vídeo enviado (poupa disco no servidor)
        try:
            if os.path.exists(in_path):
                os.remove(in_path)
        except OSError:
            pass


def _run_biomech(in_path, job_dir, job, athlete, fps):
    from pose_estimator import PoseEstimator
    from biomechanics import (
        choose_serve_side, compute_angles, segment_phases, kinematic_sequence,
        deep_metrics,
    )
    import biomech_report as br

    pose = PoseEstimator(model_path="yolov8n-pose.pt")
    # pose em CPU é pesada: reduz resolução (ângulos não mudam) e limita quadros
    frames, pmeta = pose.estimate_video(
        in_path, max_width=POSE_MAX_WIDTH, max_frames=POSE_MAX_FRAMES
    )
    # reconhecimento automático do golpe (usa a sequência de pose)
    try:
        stroke_auto = strokes.classify(frames, fps)
    except Exception:
        traceback.print_exc()
        stroke_auto = None

    side = choose_serve_side(frames)
    angles = compute_angles(frames, side)
    phases = segment_phases(angles)
    chain = kinematic_sequence(angles, fps)
    deep = deep_metrics(frames, angles, phases, fps, side)

    b = os.path.join(job_dir, "biomech")
    br.write_angles_plot(b + "_angulos.png", angles, phases, fps, athlete)
    bsummary = br.write_summary_json(
        b + "_resumo.json", athlete, side, angles, phases, chain,
        {**pmeta, "fps": fps},
    )
    bsummary["metricas_avancadas"] = deep
    return {
        "summary": bsummary,
        "stroke_auto": stroke_auto,
        "plot_path": b + "_angulos.png",
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
