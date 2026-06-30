"""Pré-voo: validação automática da qualidade da captura.

Antes de confiar no número, o app checa se o VÍDEO permite uma boa medição —
o princípio "lixo entra, lixo sai". Cada checagem usa só dados que já temos
(trajetória da bola, metadados, calibração) e devolve status + como corrigir.

Checagens:
  1. Câmera lateral      — a bola rápida deve cruzar a tela na horizontal.
  2. fps x velocidade    — deslocamento por quadro não pode ser grande demais.
  3. Bola visível        — taxa de detecção e buracos no rastreio.
  4. Calibração plausível— a escala deve implicar uma bola de ~6,7 cm.
  5. Desfoque (blur)     — a bola não pode "esticar" demais nos quadros rápidos.

Honestidade: são heurísticas de engenharia para pegar erros grosseiros de
captura — não substituem o bom senso de filmar de lado, com luz e slow-motion.
"""

from __future__ import annotations

import math
import statistics


def _steps(trajectory):
    """Passos consecutivos com (dframes, dx, dy, vpx, det_destino)."""
    out = []
    for a, b in zip(trajectory, trajectory[1:]):
        df = b.frame - a.frame
        if df <= 0:
            continue
        dx, dy = b.x - a.x, b.y - a.y
        vpx = math.hypot(dx, dy) / df
        out.append((df, dx, dy, vpx, b))
    return out


def _item(chave, nome, status, valor, mensagem, corrigir):
    cor = {"ok": "#15803d", "aviso": "#d97706", "grave": "#dc2626"}[status]
    ic = {"ok": "✅", "aviso": "⚠️", "grave": "🔺"}[status]
    return {"chave": chave, "nome": nome, "status": status, "cor": cor,
            "icone": ic, "valor": valor, "mensagem": mensagem, "corrigir": corrigir}


def check(trajectory, meta: dict, result, calib, calibracao: dict | None) -> dict:
    itens = []
    scale = meta.get("scale", 1.0) or 1.0
    proc_w = max(1.0, (meta.get("width", 0) or 0) * scale)
    steps = _steps(trajectory)
    peak_vpx = max((s[3] for s in steps), default=0.0)

    # ---------- 1) câmera lateral ----------
    if steps and peak_vpx > 0:
        fast = [s for s in steps if s[3] >= 0.6 * peak_vpx]
        sdx = sum(abs(s[1]) for s in fast)
        sdy = sum(abs(s[2]) for s in fast)
        hf = sdx / (sdx + sdy) if (sdx + sdy) > 0 else 0.0
        if hf >= 0.55:
            itens.append(_item("lateral", "Câmera lateral", "ok",
                               f"{hf*100:.0f}% horizontal",
                               "A bola cruza a tela na horizontal — ângulo bom.", ""))
        elif hf >= 0.40:
            itens.append(_item("lateral", "Câmera lateral", "aviso",
                               f"{hf*100:.0f}% horizontal",
                               "O ângulo parece um pouco oblíquo.",
                               "Posicione a câmera de lado, na linha do saque, parada."))
        else:
            itens.append(_item("lateral", "Câmera lateral", "grave",
                               f"{hf*100:.0f}% horizontal",
                               "A bola se move mais na vertical que na horizontal — "
                               "a câmera provavelmente não está de lado.",
                               "Filme de LADO (perpendicular ao saque): a bola deve "
                               "atravessar a tela na horizontal."))

    # ---------- 2) fps x velocidade (aliasing) ----------
    if peak_vpx > 0 and proc_w > 1:
        frac = peak_vpx / proc_w
        if frac <= 0.15:
            itens.append(_item("fps", "fps x velocidade", "ok",
                               f"{frac*100:.0f}% da tela/quadro",
                               "A bola anda pouco por quadro — amostragem boa.", ""))
        elif frac <= 0.25:
            itens.append(_item("fps", "fps x velocidade", "aviso",
                               f"{frac*100:.0f}% da tela/quadro",
                               "A bola anda bastante por quadro para este fps.",
                               "Use mais fps (120–240) para esta velocidade."))
        else:
            itens.append(_item("fps", "fps x velocidade", "grave",
                               f"{frac*100:.0f}% da tela/quadro",
                               "A bola 'pula' muito entre quadros — risco de medida "
                               "imprecisa (aliasing).",
                               "Grave em slow-motion (240 fps) e mais perto do plano "
                               "do saque."))

    # ---------- 3) bola visível ----------
    frames = meta.get("frames", 0) or 0
    dets = meta.get("detections", len(trajectory)) or len(trajectory)
    rate = dets / frames if frames else 0.0
    max_gap = max((s[0] for s in steps), default=0)
    if dets < 8:
        itens.append(_item("visivel", "Bola visível", "grave",
                           f"{dets} detecções",
                           "A bola foi detectada pouquíssimas vezes.",
                           "Melhore a luz e o contraste (bola amarela, fundo limpo) "
                           "e mantenha a bola no quadro."))
    elif rate < 0.3 or max_gap > 6:
        itens.append(_item("visivel", "Bola visível", "aviso",
                           f"{rate*100:.0f}% dos quadros · maior buraco {max_gap}q",
                           "A bola some por trechos do vídeo.",
                           "Mais luz e contraste; evite que a bola saia do quadro "
                           "ou fique encoberta."))
    else:
        itens.append(_item("visivel", "Bola visível", "ok",
                           f"{rate*100:.0f}% dos quadros",
                           "A bola foi rastreada de forma contínua.", ""))

    # ---------- 4) calibração plausível (tamanho implícito da bola) ----------
    bola = (calibracao or {}).get("bola") or {}
    diam_px = bola.get("diameter_px")
    mpp = getattr(calib, "meters_per_pixel", None)
    if diam_px and mpp:
        implied_cm = diam_px * mpp * 100.0
        if 5.5 <= implied_cm <= 8.0:
            itens.append(_item("calib", "Calibração plausível", "ok",
                               f"bola implícita ≈ {implied_cm:.1f} cm",
                               "A escala implica uma bola de tamanho realista.", ""))
        elif 4.0 <= implied_cm <= 11.0:
            itens.append(_item("calib", "Calibração plausível", "aviso",
                               f"bola implícita ≈ {implied_cm:.1f} cm",
                               "A escala implica uma bola um pouco fora do normal "
                               "(o ideal é ~6,7 cm).",
                               "Confira os 2 pontos e a distância informada na "
                               "calibração da quadra."))
        else:
            itens.append(_item("calib", "Calibração plausível", "grave",
                               f"bola implícita ≈ {implied_cm:.1f} cm",
                               "A escala implica uma bola de tamanho irreal — a "
                               "calibração quase certamente está errada.",
                               "Refaça a calibração: toque exatamente nos 2 pontos e "
                               "confirme a distância real em metros."))

    # ---------- 5) desfoque de movimento (blur) ----------
    if steps and peak_vpx > 0:
        fast_r = [s[4].radius for s in steps if s[3] >= 0.6 * peak_vpx and s[4].radius > 0]
        slow_r = [s[4].radius for s in steps if s[3] <= 0.3 * peak_vpx and s[4].radius > 0]
        if len(fast_r) >= 2 and len(slow_r) >= 2:
            ratio = statistics.median(fast_r) / max(1e-6, statistics.median(slow_r))
            if ratio <= 1.3:
                itens.append(_item("blur", "Desfoque no impacto", "ok",
                                   f"{ratio:.1f}× o tamanho parado",
                                   "Pouco arrasto de movimento na bola.", ""))
            elif ratio <= 1.6:
                itens.append(_item("blur", "Desfoque no impacto", "aviso",
                                   f"{ratio:.1f}× o tamanho parado",
                                   "A bola estica um pouco nos quadros rápidos (blur).",
                                   "Aumente o fps e a velocidade do obturador; mais luz."))
            else:
                itens.append(_item("blur", "Desfoque no impacto", "grave",
                                   f"{ratio:.1f}× o tamanho parado",
                                   "A bola borra bastante no impacto — prejudica o "
                                   "tamanho e a posição detectados.",
                                   "Grave com obturador rápido / mais luz / 240 fps."))

    # ---------- nota geral ----------
    n_grave = sum(1 for i in itens if i["status"] == "grave")
    n_aviso = sum(1 for i in itens if i["status"] == "aviso")
    nota = max(0, 100 - 30 * n_grave - 12 * n_aviso)
    if n_grave:  # um problema sério já derruba a nota para a faixa "Ruim"
        nota = min(nota, 55)
    if n_grave:
        nivel, cor = "Ruim", "#dc2626"
    elif n_aviso:
        nivel, cor = "Regular", "#d97706"
    else:
        nivel, cor = "Boa", "#15803d"
    if n_grave:
        resumo = (f"{n_grave} problema(s) sério(s) na captura podem ter distorcido a "
                  "medição. Vale regravar seguindo as dicas e medir de novo.")
    elif n_aviso:
        resumo = (f"{n_aviso} ponto(s) de atenção na captura. A medição é utilizável, "
                  "mas dá para deixá-la mais precisa.")
    else:
        resumo = "Captura dentro do protocolo — boas condições para uma medição confiável."

    return {"nota": nota, "nivel": nivel, "cor": cor, "itens": itens,
            "n_graves": n_grave, "n_avisos": n_aviso, "resumo": resumo}
