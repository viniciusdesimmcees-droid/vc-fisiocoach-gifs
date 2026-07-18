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
import avatar  # noqa: E402
import bodymap  # noqa: E402
import manual  # noqa: E402
import movetests  # noqa: E402
import neuro  # noqa: E402

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

# Deep learning (detector YOLOv8 + biomecânica): além de conferir se torch e
# ultralytics estão instalados, TESTA de verdade o torchvision (um par
# torch/torchvision incompatível quebra com "operator torchvision::nms does
# not exist"). Se o teste falhar, o app esconde as opções de DL e segue
# medindo velocidade com o detector clássico — nunca derruba a análise.
import importlib.util as _ilu


def _dl_available() -> bool:
    if _ilu.find_spec("torch") is None or _ilu.find_spec("ultralytics") is None:
        return False
    try:
        import torch
        from torchvision.ops import nms

        nms(torch.tensor([[0.0, 0.0, 1.0, 1.0]]), torch.tensor([0.9]), 0.5)
        return True
    except Exception as e:  # ex.: torchvision::nms does not exist
        print(f"[dl] deep learning DESATIVADO (torch/torchvision quebrados): {e}")
        return False


DL_AVAILABLE = _dl_available()


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
    # mostra TODAS as análises (inclusive as fora do laudo) para o operador
    h = history.get_history(athlete, only_included=False)
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
        sessoes=avatar.sessions(posturas),
        pares_foto=avatar.photo_pairs(posturas),
        testes_mov=list(reversed(history.get_movement_tests(athlete))),
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


def _frame_at(path: str, idx: int, max_width: int):
    """Lê o quadro `idx` do vídeo (na mesma escala usada na pose)."""
    import cv2

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return _downscale_bgr(frame, max_width)


@app.route("/testes")
def testes():
    return render_template("testes.html", testes=movetests.TESTES,
                           dl_available=DL_AVAILABLE)


@app.route("/testes/analisar", methods=["POST"])
def testes_analisar():
    if not DL_AVAILABLE:
        return render_template(
            "testes.html", testes=movetests.TESTES, dl_available=False,
            error="Os testes de movimento usam detecção de pose (deep learning), "
            "indisponível neste ambiente.",
        ), 400
    media = request.files.get("media")
    teste = request.form.get("teste", "agachamento")
    if not media or media.filename == "":
        return render_template(
            "testes.html", testes=movetests.TESTES, dl_available=True,
            error="Envie o vídeo do teste (corpo inteiro, 2–3 repetições).",
        ), 400
    if teste not in movetests.TESTES:
        abort(400)
    athlete = request.form.get("athlete", "Atleta").strip() or "Atleta"

    job = uuid.uuid4().hex[:10]
    in_path = os.path.join(UPLOADS_DIR, f"teste_{job}_{media.filename}")
    media.save(in_path)
    try:
        import cv2
        from pose_estimator import PoseEstimator

        pose = PoseEstimator(model_path="yolov8n-pose.pt")
        frames, _meta = pose.estimate_video(
            in_path, max_width=POSE_MAX_WIDTH, max_frames=POSE_MAX_FRAMES
        )
        resultado = movetests.analyze(teste, frames)
        if not resultado:
            return render_template(
                "testes.html", testes=movetests.TESTES, dl_available=True,
                error="Não consegui medir o movimento. Garanta corpo inteiro no "
                "quadro, boa luz e a vista certa (veja as instruções do teste).",
            ), 400

        # músculos com déficit -> exercícios da biblioteca VC Fisiocoach
        exercicios = []
        for d in resultado["deficits"]:
            exercicios.extend(engine._pick(d["grupo"], n=2))

        # quadro-chave anotado (o fundo do movimento)
        img_bytes = None
        img = _frame_at(in_path, resultado["frame_idx"], POSE_MAX_WIDTH)
        kp = frames[resultado["frame_idx"]]
        if img is not None and kp is not None:
            vista = "lado" if teste == "agachamento" else "frente"
            ann = posture.annotate(img, kp, vista)
            ok_enc, buf = cv2.imencode(".png", ann)
            img_bytes = buf.tobytes() if ok_enc else None

        test_id = None
        try:
            test_id = history.record_movement_test(
                athlete, resultado, exercicios, img_bytes
            )
        except Exception:
            traceback.print_exc()

        return render_template(
            "testes_result.html", athlete=athlete, resultado=resultado,
            exercicios=exercicios, test_id=test_id,
            imagem=(url_for("teste_imagem", test_id=test_id)
                    if (test_id and img_bytes) else None),
            history_url=url_for("historico_atleta", athlete=athlete),
        )
    except Exception as e:
        traceback.print_exc()
        return render_template(
            "testes.html", testes=movetests.TESTES, dl_available=True,
            error=f"Falha no teste de movimento: {e}",
        ), 500
    finally:
        try:
            os.remove(in_path)
        except OSError:
            pass


@app.route("/teste/<int:test_id>/imagem.png")
def teste_imagem(test_id):
    data = history.get_movement_image(test_id)
    if not data:
        abort(404)
    return Response(data, mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.route("/teste/<int:test_id>/excluir", methods=["POST"])
def excluir_teste(test_id):
    athlete = request.form.get("athlete", "")
    history.delete_movement_test(test_id)
    return redirect(url_for("historico_atleta", athlete=athlete)
                    if athlete else url_for("historico"))


@app.route("/atleta/<athlete>/boneco")
def boneco_atleta(athlete):
    profile = history.get_profile(athlete)
    posturas = history.get_posture_history(athlete)
    _golpe, intel = history.latest_extras(athlete)
    if not profile and not posturas and not intel:
        abort(404)
    pontos, risco = avatar.build(profile, posturas, intel)
    return render_template("boneco.html", athlete=athlete, pontos=pontos, risco=risco)


@app.route("/atleta/<athlete>/saque3d")
def saque3d_atleta(athlete):
    def _g(d, *keys):
        for k in keys:
            if not isinstance(d, dict):
                return None
            d = d.get(k)
        return d

    profile = history.get_profile(athlete)
    bio, data_iso = history.latest_biomech(athlete)
    joelho = _g(bio, "angulos_no_loading", "joelho")
    cotovelo = _g(bio, "angulos_no_contato", "cotovelo")
    tronco = _g(bio, "angulos_no_contato", "inclinacao_tronco")
    medido = bio is not None and any(v is not None for v in (joelho, cotovelo, tronco))
    anim = {
        "joelho": round(float(joelho), 0) if joelho is not None else 140,
        "cotovelo": round(float(cotovelo), 0) if cotovelo is not None else 155,
        "tronco": round(float(tronco), 0) if tronco is not None else 25,
        "joelho_medido": joelho is not None,
        "cotovelo_medido": cotovelo is not None,
        "tronco_medido": tronco is not None,
        "dom": "esq" if ((profile or {}).get("dominant_hand") or "").lower().startswith("e") else "dir",
    }
    data_br = ""
    if data_iso:
        d = data_iso[:10]
        data_br = f"{d[8:10]}/{d[5:7]}/{d[0:4]}"
    return render_template("saque3d.html", athlete=athlete, anim=anim,
                           medido=medido, data=data_br)


@app.route("/atleta/<athlete>/boneco/comparar")
def boneco_comparar(athlete):
    posturas = history.get_posture_history(athlete)
    comp = avatar.compare(posturas)
    return render_template("boneco_comparar.html", athlete=athlete, comp=comp)


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


PREF_LABELS = [
    ("usar_bola", "Verificação/calibração automática pelo tamanho da bola",
     "Usa a bola (diâmetro conhecido) como régua independente para confirmar a calibração."),
    ("previoo", "Pré-voo: checagem da qualidade da captura",
     "Avisa sobre câmera não-lateral, fps baixo, bola pouco visível, desfoque."),
    ("confianca", "Selo de confiança com margem de erro (± km/h)",
     "Ferramenta interna do operador. Desligado, o resultado mostra só a "
     "velocidade — recomendado ao apresentar para atletas."),
    ("didatico", "Resumo didático (em palavras simples para o aluno)", ""),
    ("glossario", "Glossário de termos", ""),
    ("referencias", "Comparação com referências científicas", ""),
    ("benchmark", "Benchmark vs. profissional (radar + percentil)", ""),
    ("plano", "Plano inteligente (risco de lesão + músculos + treino)", ""),
]


@app.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    if request.method == "POST":
        # as marcadas para PARTICIPAR vêm no form; as ausentes ficam excluídas
        incluidas = set(request.form.getlist("metrica"))
        excluidas = [k for k, _ in metrics.METRIC_REGISTRY if k not in incluidas]
        history.set_excluded_metrics(excluidas)
        # como a análise é feita
        prefs = {k: (k in set(request.form.getlist("pref")))
                 for k, _l, _d in PREF_LABELS}
        try:
            prefs["ball_diameter_cm"] = float(
                request.form.get("ball_diameter_cm") or 6.7)
        except (TypeError, ValueError):
            prefs["ball_diameter_cm"] = 6.7
        history.set_analysis_prefs(prefs)
        return redirect(url_for("configuracoes", salvo=1))
    excluidas = history.get_excluded_metrics()
    return render_template(
        "configuracoes.html",
        metricas=metrics.METRIC_REGISTRY,
        excluidas=excluidas,
        prefs=history.get_analysis_prefs(),
        pref_labels=PREF_LABELS,
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


def _build_dossier_bytes(athlete, profile, h, posturas, secoes=None,
                         analise_ids=None):
    """Gera o PDF do laudo (completo ou personalizado) e devolve os bytes.
    `secoes`: conjunto de seções a incluir (None = todas).
    `analise_ids`: análises individuais para anexar o relatório completo."""
    import tempfile

    def S(k):
        return secoes is None or k in secoes

    stats = history.athlete_stats(athlete) if h else {}
    serve_png = history.evolution_png(athlete) if (h and S("saque")) else None
    posture_png = (history.posture_evolution_png(athlete)
                   if (posturas and S("postura")) else None)
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

    # par de fotos da MESMA vista (frontal com frontal etc.)
    pares = avatar.photo_pairs(posturas)
    if pares:
        first_img = _img_tmp(pares[0]["antes"]["id"])
        last_img = _img_tmp(pares[0]["agora"]["id"])
    else:
        com_foto = [p for p in posturas if p.get("tem_imagem")]
        first_img = None
        last_img = _img_tmp(com_foto[-1]["id"]) if com_foto else None
    all_serves = [
        {"data": (a.get("created_at") or "")[:10], "peak": a.get("peak_kmh"),
         "nivel": reportpro.classify(a.get("peak_kmh") or 0)["nivel"]}
        for a in h
    ]
    objetivo = _montar_objetivo(profile, inteligencia)

    # mapa corporal (boneco com os pontos da avaliação)
    mapa_png = None
    pontos_corpo = []
    if S("mapa"):
        try:
            pontos_corpo, risco_av = avatar.build(profile, posturas, inteligencia)
            if pontos_corpo:
                mapa_png = bodymap.render_png(pontos_corpo, risco_av)
        except Exception:
            traceback.print_exc()

    # comparativo postural (primeira × última, por vista) para o PDF
    comp = None
    compare_png = None
    if S("comparativo"):
        try:
            comp = avatar.compare(posturas)
            if comp:
                compare_png = bodymap.render_compare_png(
                    comp["antes"]["pontos"], comp["agora"]["pontos"],
                    comp["antes"]["data"], comp["agora"]["data"],
                )
        except Exception:
            traceback.print_exc()

    # análises individuais escolhidas para anexar (relatório completo de cada)
    analises = []
    for aid in (analise_ids or []):
        try:
            row = history.get_analysis(aid)
            if row and row.get("athlete") == athlete:
                analises.append((row, history.get_analysis_traj(aid)))
        except Exception:
            traceback.print_exc()

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
            bodymap_png=mapa_png, pontos_corpo=pontos_corpo,
            comp=comp, compare_png=compare_png,
            secoes=secoes, analises=analises,
        )
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        for p_i in tmp_imgs + [tmp]:
            try:
                os.remove(p_i)
            except OSError:
                pass


SECOES_RELATORIO = [
    ("ficha", "Ficha do atleta (idade, IMC, lesões, objetivos)"),
    ("saque", "Evolução do saque (recorde, média, gráfico, golpe)"),
    ("postura", "Avaliação postural (evolução + fotos da mesma vista)"),
    ("comparativo", "Comparativo postural antes × agora"),
    ("mapa", "Mapa corporal (boneco com os pontos)"),
    ("plano", "Plano inteligente (risco + músculos + treino)"),
    ("historico", "Histórico completo + objetivo para o atleta"),
]


@app.route("/atleta/<athlete>/relatorio")
def relatorio_form(athlete):
    """Montar relatório personalizado: marcar seções e análises."""
    profile = history.get_profile(athlete)
    h = history.get_history(athlete, only_included=False)
    posturas = history.get_posture_history(athlete)
    if not h and not profile and not posturas:
        abort(404)
    return render_template(
        "relatorio.html", athlete=athlete, secoes=SECOES_RELATORIO,
        rows=list(reversed(h)), n_posturas=len(posturas),
    )


@app.route("/atleta/<athlete>/relatorio.pdf")
def relatorio_custom(athlete):
    """PDF personalizado: ?sec=ficha&sec=saque…&an=12&an=15"""
    profile = history.get_profile(athlete)
    h = history.get_history(athlete)
    posturas = history.get_posture_history(athlete)
    if not h and not profile and not posturas:
        abort(404)
    secoes = set(request.args.getlist("sec")) or None  # vazio = tudo
    analise_ids = []
    for x in request.args.getlist("an"):
        try:
            analise_ids.append(int(x))
        except (TypeError, ValueError):
            pass
    data = _build_dossier_bytes(athlete, profile, h, posturas,
                                secoes=secoes, analise_ids=analise_ids)
    return Response(
        data, mimetype="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="relatorio_{athlete}.pdf"'},
    )


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


@app.route("/analise/<int:analysis_id>/relatorio.pdf")
def relatorio_analise(analysis_id):
    """Relatório completo de qualquer análise já feita (reconstruído do banco)."""
    row = history.get_analysis(analysis_id)
    if not row:
        abort(404)
    percurso = history.get_analysis_traj(analysis_id)

    import tempfile

    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        reportpro.write_analysis_pdf(tmp, row, percurso)
        with open(tmp, "rb") as f:
            data = f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    d = (row.get("created_at") or "")[:10]
    return Response(
        data, mimetype="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="saque_{row.get("athlete", "atleta")}_{d}.pdf"'},
    )


@app.route("/analise/<int:analysis_id>/incluir", methods=["POST"])
def incluir_analise(analysis_id):
    athlete = request.form.get("athlete", "")
    incluir = request.form.get("incluir") == "1"
    history.set_analysis_included(analysis_id, incluir)
    return redirect(url_for("historico_atleta", athlete=athlete)
                    if athlete else url_for("historico"))


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
        # 5) percursos da bola + relatório completo de CADA análise já feita
        h_all = history.get_history(athlete, only_included=False)
        import tempfile
        for a in h_all:
            d = (a.get("created_at") or "")[:10]
            tb = history.get_analysis_traj(a["id"]) if a.get("tem_percurso") else None
            if tb:
                z.writestr(f"{_safe(athlete)}/percurso_bola/{d}_id{a['id']}_"
                           f"{(a.get('peak_kmh') or 0):.0f}kmh.png", tb)
            try:
                row = history.get_analysis(a["id"])
                fd_r, tmp_r = tempfile.mkstemp(suffix=".pdf")
                os.close(fd_r)
                try:
                    reportpro.write_analysis_pdf(tmp_r, row, tb)
                    with open(tmp_r, "rb") as f_r:
                        z.writestr(f"{_safe(athlete)}/relatorios_saque/{d}_id{a['id']}_"
                                   f"{(a.get('peak_kmh') or 0):.0f}kmh.pdf", f_r.read())
                finally:
                    try:
                        os.remove(tmp_r)
                    except OSError:
                        pass
            except Exception:
                traceback.print_exc()
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
                   "- percurso_bola/: o caminho da bola rastreado pelo scanner em cada saque\n"
                   "- relatorios_saque/: o relatorio completo em PDF de CADA analise ja feita\n")

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
    # visão geral rápida para o painel da home
    resumo = {"alunos": 0, "analises": 0, "recorde": None}
    try:
        atletas = history.list_athletes()
        resumo["alunos"] = len(atletas)
        resumo["analises"] = sum(a.get("n") or 0 for a in atletas)
        melhores = [a["best"] for a in atletas if a.get("best")]
        resumo["recorde"] = max(melhores) if melhores else None
    except Exception:
        pass
    try:
        atividades = history.recent_activity(6)
    except Exception:
        atividades = []
    return render_template("index.html", dl_available=DL_AVAILABLE,
                           resumo=resumo, atividades=atividades)


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
                        "lado": "de lado", "lateral": "de lado",
                        "lado_dir": "de perfil direito",
                        "lado_esq": "de perfil esquerdo"}.get(view, view),
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


@app.route("/manual")
def manual_page():
    return render_template("manual.html", secoes=manual.SECOES, versao=manual.VERSAO)


@app.route("/manual.pdf")
def manual_pdf():
    import tempfile

    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        reportpro.write_manual_pdf(tmp, manual.SECOES, manual.VERSAO)
        with open(tmp, "rb") as f:
            data = f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return Response(
        data, mimetype="application/pdf",
        headers={"Content-Disposition":
                 'attachment; filename="manual_operador_vf_tenis_scanner.pdf"'},
    )


@app.route("/protocolo")
def protocolo():
    return render_template("protocolo.html")


@app.route("/neuro", endpoint="neuro")
def neuro_page():
    return render_template(
        "neuro.html",
        avaliacao=neuro.AVALIACAO,
        absolutas=neuro.CONTRAINDICACOES_ABSOLUTAS,
        relativas=neuro.CONTRAINDICACOES_RELATIVAS,
        modalidades=neuro.MODALIDADES,
        paciente="",
    )


@app.route("/neuro/prescrever", methods=["POST"])
def neuro_prescrever():
    campos = [c for c in neuro.AVALIACAO if not neuro.AVALIACAO[c].get("multiplo")]
    av = {c: request.form.get(c, "") for c in campos}
    # campos de múltipla escolha (checkbox)
    for c, campo in neuro.AVALIACAO.items():
        if campo.get("multiplo"):
            av[c] = request.form.getlist(c)
    flags_contra = request.form.getlist("contra")
    paciente = (request.form.get("paciente") or "").strip()
    resultado = neuro.prescrever(av, flags_contra)
    return render_template("neuro_result.html", r=resultado, paciente=paciente)


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

    # preferências do operador (Configurações): como a análise é feita
    try:
        prefs = history.get_analysis_prefs()
    except Exception:
        prefs = dict(history.DEFAULT_ANALYSIS_PREFS)

    ball_d_cm = _f("ball_diameter_cm", 0.0)
    if ball_d_cm <= 0:
        ball_d_cm = float(prefs.get("ball_diameter_cm") or 6.7)
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
        aviso_dl = None
        trajectory = meta = None
        if detector == "dl":
            # Se o deep learning falhar em execução (ex.: torch/torchvision
            # incompatíveis), cai no detector clássico em vez de perder a análise.
            try:
                from detector_dl import DLBallDetector

                ball_class = int(_f("ball_class", 32))
                tracker = DLBallDetector(
                    model_path=request.form.get("model", "yolov8n.pt") or "yolov8n.pt",
                    conf=_f("conf", 0.10),
                    classes=(ball_class,),
                )
                trajectory, meta = tracker.track(
                    in_path, max_width=PROC_MAX_WIDTH, max_frames=PROC_MAX_FRAMES
                )
            except Exception as e:
                traceback.print_exc()
                detector = "classic"
                trajectory = meta = None
                aviso_dl = (
                    "O detector por deep learning falhou nesta análise "
                    f"({str(e)[:80]}). Usado o detector clássico no lugar."
                )
        if trajectory is None:
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
        ball_global = (ballcal.ball_scale(trajectory, ball_d_m)
                       if prefs.get("usar_bola", True) else None)

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
        ball_impact = (ballcal.ball_scale(
            trajectory, ball_d_m, impact_frame=result.impact_frame
        ) or ball_global) if prefs.get("usar_bola", True) else None
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
        if aviso_dl:
            avisos.append(aviso_dl)
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

        # selo de confiança da medição — ferramenta INTERNA do operador;
        # desligado por padrão para o resultado ficar limpo diante do atleta
        conf = (confidence.evaluate(result, meta, fps, file_fps, calibracao)
                if prefs.get("confianca", False) else None)
        # pré-voo: qualidade da captura (lixo entra, lixo sai)
        captura = (preflight.check(trajectory, meta, result, calib, calibracao)
                   if prefs.get("previoo", True) else None)

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
        didatico = (didactic.student_summary(summary, evalu, cls["nivel"])
                    if prefs.get("didatico", True) else None)
        glossario = (didactic.glossario(bool(biomech))
                     if prefs.get("glossario", True) else None)
        # métricas que o operador marcou para não participar da leitura
        try:
            excluded_metrics = history.get_excluded_metrics()
        except Exception:
            excluded_metrics = set()
        # comparação com referências científicas
        referencias = (references.compare(summary, bio_summary, excluded_metrics)
                       if prefs.get("referencias", True) else None)
        # motor inteligente: risco de lesão + músculos + treino (usa a ficha)
        try:
            profile = history.get_profile(athlete)
        except Exception:
            profile = None
        inteligencia = (engine.evaluate(summary, bio_summary, profile)
                        if prefs.get("plano", True) else None)

        # benchmark vs. profissional (percentil + radar + o que falta para o pro)
        bench = (benchmark.evaluate(summary, bio_summary, excluded_metrics)
                 if prefs.get("benchmark", True) else None)
        radar_url = None
        if bench and bench.get("tem_radar"):
            try:
                with open(base + "_radar.png", "wb") as _rf:
                    _rf.write(benchmark.radar_png(bench["metricas"]))
                radar_url = url_for("static", filename=f"results/{job}/saque_radar.png")
            except Exception:
                traceback.print_exc()

        # percurso da bola (o 'print' do caminho rastreado) — guardado no banco
        # e mostrado no resultado para o operador CONFERIR o que foi medido
        percurso_url = None
        try:
            traj_bytes = ballpath.trajectory_png(trajectory, meta, result)
            if traj_bytes:
                with open(base + "_percurso.png", "wb") as _pf:
                    _pf.write(traj_bytes)
                percurso_url = url_for(
                    "static", filename=f"results/{job}/saque_percurso.png")
        except Exception:
            traceback.print_exc()
            traj_bytes = None

        # registra no histórico do atleta (com golpe + plano + percurso do dia)
        if result.peak_kmh > 0:
            try:
                history.record_analysis(
                    athlete, result.peak_kmh, result.mean_kmh, fps, detector,
                    stroke=golpe, intel=inteligencia, traj_bytes=traj_bytes,
                    biomech=bio_summary,
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
                didatico_texto=(didactic.plain_text(summary, evalu)
                                if prefs.get("didatico", True) else None),
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
            "percurso": percurso_url,
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
