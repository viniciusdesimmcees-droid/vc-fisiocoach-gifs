"""Avaliação postural a partir de uma foto/quadro (keypoints COCO).

Mede assimetrias e desalinhamentos a partir da pose:
- vista frontal/costas: inclinação de ombros, cabeça, pélvis (quadril) e joelhos,
  e desvio lateral do tronco;
- vista lateral: cabeça anteriorizada e inclinação do tronco (sagital).

É uma triagem por GEOMETRIA transparente (mostra os valores) — apoio à avaliação
do profissional, NÃO diagnóstico médico. Estimativas 2D têm margem; dependem do
enquadramento (atleta de frente/costas/lado, ereto, corpo inteiro no quadro).
"""

from __future__ import annotations

import math

import numpy as np

# índices COCO
NOSE = 0
L_EYE, R_EYE = 1, 2
L_EAR, R_EAR = 3, 4
L_SH, R_SH = 5, 6
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANK, R_ANK = 15, 16

_CONF = 0.3

# limiares (graus) de magnitude para inclinações: simétrico / leve / observar
_OK, _LEVE = 2.0, 4.0


def _p(kp, i):
    if kp is None:
        return None
    x, y, c = kp[i]
    if c < _CONF:
        return None
    return np.array([float(x), float(y)], dtype=np.float64)


def _mid(a, b):
    if a is None or b is None:
        return None
    return (a + b) / 2.0


def _tilt_from_horizontal(pa, pb):
    """Magnitude (graus) da inclinação da reta pa-pb em relação à horizontal."""
    dx = abs(pa[0] - pb[0])
    dy = abs(pa[1] - pb[1])
    return math.degrees(math.atan2(dy, max(dx, 1e-6)))


def _classify(graus, ok=_OK, leve=_LEVE):
    g = abs(graus)
    if g <= ok:
        return "Simétrico", "#15803d", "✅"
    if g <= leve:
        return "Assimetria leve", "#d97706", "⚠️"
    return "Assimetria a observar", "#dc2626", "🔺"


def _row(chave, nome, graus, detalhe, explicacao, para, **kw):
    sit, cor, ic = _classify(graus, **kw)
    return {
        "chave": chave, "nome": nome,
        "valor": f"{abs(graus):.1f}°",
        "graus": round(graus, 1),
        "detalhe": detalhe,
        "situacao": sit, "cor": cor, "icone": ic,
        "explicacao": explicacao, "para": para,
    }


def _higher_side(p_left, p_right):
    """Qual keypoint está mais alto (y menor = mais alto). Usa os rótulos
    anatômicos do modelo (esquerdo/direito do atleta)."""
    if p_left[1] < p_right[1]:
        return "esquerdo"
    return "direito"


def analyze(kp, view: str = "frente") -> dict | None:
    """Retorna {view, medidas:[...], alertas:int, resumo} ou None se a pose for
    insuficiente."""
    if kp is None:
        return None
    view = (view or "frente").lower()

    medidas: list[dict] = []
    if view in ("lado", "lateral"):
        medidas = _analyze_side(kp)
    else:
        medidas = _analyze_front(kp, view)

    if not medidas:
        return None

    alertas = sum(1 for m in medidas if m["icone"] in ("⚠️", "🔺"))
    graves = sum(1 for m in medidas if m["icone"] == "🔺")
    if graves:
        resumo = (f"Encontramos {graves} ponto(s) de maior atenção e "
                  f"{alertas - graves} desvio(s) leve(s). Vale uma avaliação "
                  "postural presencial para confirmar.")
    elif alertas:
        resumo = (f"{alertas} desvio(s) leve(s) — comuns e geralmente ajustáveis "
                  "com trabalho de mobilidade e fortalecimento.")
    else:
        resumo = "Postura simétrica nos pontos avaliados. Bom alinhamento geral."

    return {"view": view, "medidas": medidas, "alertas": alertas,
            "graves": graves, "resumo": resumo}


def _analyze_front(kp, view: str) -> list[dict]:
    medidas = []
    lsh, rsh = _p(kp, L_SH), _p(kp, R_SH)
    lhip, rhip = _p(kp, L_HIP), _p(kp, R_HIP)
    leye, reye = _p(kp, L_EYE), _p(kp, R_EYE)
    lear, rear = _p(kp, L_EAR), _p(kp, R_EAR)
    lkn, rkn = _p(kp, L_KNEE), _p(kp, R_KNEE)

    # ombros
    if lsh is not None and rsh is not None:
        g = _tilt_from_horizontal(lsh, rsh)
        alto = _higher_side(lsh, rsh)
        medidas.append(_row(
            "ombros", "Linha dos ombros", g,
            f"Ombro {alto} mais alto." if g > _OK else "Ombros nivelados.",
            "Mede se um ombro está mais alto que o outro.",
            "Assimetria de ombro pode sobrecarregar o lado do saque e o pescoço."))

    # cabeça (olhos; se faltar, orelhas)
    pa, pb = (leye, reye) if (leye is not None and reye is not None) else (lear, rear)
    if pa is not None and pb is not None:
        g = _tilt_from_horizontal(pa, pb)
        lado = _higher_side(pa, pb)
        medidas.append(_row(
            "cabeca", "Inclinação da cabeça", g,
            f"Cabeça inclinada para o lado {('direito' if lado=='esquerdo' else 'esquerdo')}."
            if g > _OK else "Cabeça centrada.",
            "Mede a inclinação lateral da cabeça.",
            "Inclinação constante tensiona o trapézio e a cervical."))

    # pélvis / quadril
    if lhip is not None and rhip is not None:
        g = _tilt_from_horizontal(lhip, rhip)
        alto = _higher_side(lhip, rhip)
        medidas.append(_row(
            "pelvis", "Nivelamento da pélvis", g,
            f"Quadril {alto} mais alto." if g > _OK else "Pélvis nivelada.",
            "Mede se um lado do quadril está mais alto (báscula pélvica).",
            "Desnível pélvico muda a base do saque e pode sobrecarregar a lombar."))

    # desvio lateral do tronco (ombros vs quadris)
    msh, mhip = _mid(lsh, rsh), _mid(lhip, rhip)
    if msh is not None and mhip is not None:
        lateral = msh[0] - mhip[0]
        vertical = max(mhip[1] - msh[1], 1e-6)
        g = math.degrees(math.atan2(lateral, vertical))
        # mapeia direção da imagem -> lado anatômico conforme a vista
        img_dir = "direita" if lateral > 0 else "esquerda"
        if view in ("costas", "tras"):
            anat = img_dir
        else:  # frente: imagem-direita = lado esquerdo do atleta
            anat = "esquerda" if img_dir == "direita" else "direita"
        medidas.append(_row(
            "tronco", "Alinhamento do tronco", g,
            f"Tronco deslocado para a {anat}." if abs(g) > _OK else "Tronco centrado sobre o quadril.",
            "Mede se a linha dos ombros está deslocada lateralmente sobre o quadril.",
            "Desvio lateral indica compensação muscular e carga assimétrica."))

    # joelhos (nível) — base de apoio
    if lkn is not None and rkn is not None:
        g = _tilt_from_horizontal(lkn, rkn)
        alto = _higher_side(lkn, rkn)
        medidas.append(_row(
            "joelhos", "Nível dos joelhos", g,
            f"Joelho {alto} mais alto." if g > _OK else "Joelhos nivelados.",
            "Mede o nivelamento da linha dos joelhos (base de apoio).",
            "Diferença pode refletir desnível de quadril ou apoio assimétrico."))

    return medidas


def _analyze_side(kp) -> list[dict]:
    """Vista lateral: escolhe o lado mais visível e mede cabeça anteriorizada
    e inclinação sagital do tronco."""
    def side_conf(idxs):
        s = 0.0
        for i in idxs:
            if kp[i][2] >= _CONF:
                s += float(kp[i][2])
        return s

    left = side_conf([L_EAR, L_SH, L_HIP, L_KNEE, L_ANK])
    right = side_conf([R_EAR, R_SH, R_HIP, R_KNEE, R_ANK])
    if right >= left:
        ear, sh, hip = _p(kp, R_EAR), _p(kp, R_SH), _p(kp, R_HIP)
    else:
        ear, sh, hip = _p(kp, L_EAR), _p(kp, L_SH), _p(kp, L_HIP)
    if sh is None or hip is None:
        return []

    medidas = []
    torso = max(np.linalg.norm(sh - hip), 1e-6)

    # cabeça anteriorizada: deslocamento horizontal orelha-ombro / tronco
    if ear is not None:
        offset = abs(ear[0] - sh[0]) / torso  # fração do tronco
        graus = offset * 45.0  # converte para uma escala em "graus" comparável
        sit, cor, ic = _classify(graus, ok=4.0, leve=9.0)
        medidas.append({
            "chave": "cabeca_ant", "nome": "Cabeça anteriorizada",
            "valor": f"{offset*100:.0f}% do tronco",
            "graus": round(graus, 1),
            "detalhe": ("Cabeça projetada à frente dos ombros."
                        if graus > 4 else "Cabeça alinhada sobre os ombros."),
            "situacao": sit, "cor": cor, "icone": ic,
            "explicacao": "Mede o quanto a orelha está à frente da linha do ombro.",
            "para": "Cabeça à frente sobrecarrega a cervical e o trapézio."})

    # inclinação sagital do tronco (em relação à vertical)
    lateral = sh[0] - hip[0]
    vertical = max(hip[1] - sh[1], 1e-6)
    g = math.degrees(math.atan2(lateral, vertical))
    sit, cor, ic = _classify(g, ok=5.0, leve=12.0)
    medidas.append({
        "chave": "tronco_sag", "nome": "Inclinação do tronco (perfil)",
        "valor": f"{abs(g):.1f}°",
        "graus": round(g, 1),
        "detalhe": ("Tronco inclinado para a frente." if g > 0 else
                    "Tronco inclinado para trás.") if abs(g) > 5 else "Tronco ereto.",
        "situacao": sit, "cor": cor, "icone": ic,
        "explicacao": "Mede o quanto o tronco se inclina à frente/atrás no perfil.",
        "para": "Inclinação excessiva muda o centro de gravidade e carrega a lombar."})

    return medidas


# ---------------- anotação da imagem ----------------
_COCO_EDGES = [
    (L_SH, R_SH), (L_SH, L_HIP), (R_SH, R_HIP), (L_HIP, R_HIP),
    (L_SH, L_KNEE), (R_SH, R_KNEE),  # apenas referência visual leve
    (L_HIP, L_KNEE), (R_HIP, R_KNEE), (L_KNEE, L_ANK), (R_KNEE, R_ANK),
]


def annotate(img, kp, view: str = "frente"):
    """Desenha o esqueleto + linhas de referência (ombros, quadril, prumo).
    Recebe e devolve imagem BGR (OpenCV)."""
    import cv2

    out = img.copy()
    h, w = out.shape[:2]
    thick = max(2, round(w / 400))
    rad = max(3, round(w / 250))

    def pt(i):
        if kp[i][2] < _CONF:
            return None
        return (int(round(kp[i][0])), int(round(kp[i][1])))

    # esqueleto leve
    for a, b in _COCO_EDGES:
        pa, pb = pt(a), pt(b)
        if pa and pb:
            cv2.line(out, pa, pb, (90, 90, 90), max(1, thick - 1), cv2.LINE_AA)
    for i in range(17):
        p = pt(i)
        if p:
            cv2.circle(out, p, rad, (60, 200, 90), -1, cv2.LINE_AA)

    green, amber = (60, 200, 90), (10, 160, 230)

    def hline(a, b):
        pa, pb = pt(a), pt(b)
        if pa and pb:
            g = _tilt_from_horizontal(np.array(pa, float), np.array(pb, float))
            col = green if abs(g) <= _OK else amber
            cv2.line(out, pa, pb, col, thick, cv2.LINE_AA)

    if view in ("lado", "lateral"):
        # prumo a partir do ombro mais visível
        for sh_i, hip_i in ((R_SH, R_HIP), (L_SH, L_HIP)):
            ps, ph = pt(sh_i), pt(hip_i)
            if ps and ph:
                cv2.line(out, (ps[0], 0), (ps[0], h), (200, 160, 60), 1, cv2.LINE_AA)
                cv2.line(out, ps, ph, green, thick, cv2.LINE_AA)
                break
    else:
        hline(L_SH, R_SH)
        hline(L_HIP, R_HIP)
        hline(L_KNEE, R_KNEE)
        # prumo central (do meio dos ombros para baixo)
        msh, mhip = pt(L_SH), pt(R_SH)
        if msh and mhip:
            cx = (msh[0] + mhip[0]) // 2
            cv2.line(out, (cx, 0), (cx, h), (200, 160, 60), 1, cv2.LINE_AA)
    return out
