"""Testes de MOVIMENTO por vídeo (screening funcional).

Inspirado nos grandes screenings do mundo (padrão FMS/overhead squat): o aluno
executa um movimento filmado, a pose é extraída quadro a quadro e regras
transparentes medem o gesto, apontam DÉFICITS MUSCULARES prováveis e já
encaminham os músculos-foco + exercícios da biblioteca VC Fisiocoach.

Honestidade: é triagem 2D por vídeo — aponta padrões visuais compatíveis com
fraqueza/encurtamento; a confirmação é do profissional (testes clínicos).
"""

from __future__ import annotations

import math

import numpy as np

# índices COCO
NOSE = 0
L_SH, R_SH = 5, 6
L_EL, R_EL = 7, 8
L_WR, R_WR = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANK, R_ANK = 15, 16

_CONF = 0.3

TESTES = {
    "agachamento": {
        "nome": "Agachamento profundo (braços elevados)",
        "icone": "🏋️",
        "vista": "DE LADO (perfil)",
        "instrucoes": [
            "Pés na largura dos ombros, braços esticados acima da cabeça.",
            "Agache o mais fundo que conseguir, devagar (2–3 s descendo).",
            "Filme DE LADO, corpo inteiro no quadro, 2–3 repetições.",
        ],
    },
    "unilateral_dir": {
        "nome": "Agachamento unilateral — perna DIREITA",
        "icone": "🦵",
        "vista": "DE FRENTE",
        "instrucoes": [
            "Em pé na perna DIREITA, a outra à frente sem tocar o chão.",
            "Agache até ~60° de joelho, devagar, sem apoiar a outra perna.",
            "Filme DE FRENTE, corpo inteiro, 3 repetições.",
        ],
    },
    "unilateral_esq": {
        "nome": "Agachamento unilateral — perna ESQUERDA",
        "icone": "🦵",
        "vista": "DE FRENTE",
        "instrucoes": [
            "Em pé na perna ESQUERDA, a outra à frente sem tocar o chão.",
            "Agache até ~60° de joelho, devagar, sem apoiar a outra perna.",
            "Filme DE FRENTE, corpo inteiro, 3 repetições.",
        ],
    },
}


def _pt(f, i):
    if f is None:
        return None
    x, y, c = f[i]
    if c < _CONF:
        return None
    return np.array([float(x), float(y)])


def _ang(a, b, c):
    """Ângulo interno em b (graus)."""
    if a is None or b is None or c is None:
        return None
    v1, v2 = a - b, c - b
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return None
    cos = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1, 1))
    return math.degrees(math.acos(cos))


def _vert_ang(a, b):
    """Inclinação do segmento a->b em relação à VERTICAL (graus)."""
    if a is None or b is None:
        return None
    dx, dy = b[0] - a[0], b[1] - a[1]
    return math.degrees(math.atan2(abs(dx), abs(dy) if abs(dy) > 1e-6 else 1e-6))


def _hip_mid_y(f):
    l, r = _pt(f, L_HIP), _pt(f, R_HIP)
    if l is None or r is None:
        return None
    return (l[1] + r[1]) / 2.0


def _deepest(frames):
    """Índice do quadro mais FUNDO (pélvis mais baixa = maior y)."""
    best, besty = None, -1.0
    for i, f in enumerate(frames):
        y = _hip_mid_y(f)
        if y is not None and y > besty:
            besty, best = y, i
    return best


def _medida(nome, valor, situacao_idx, detalhe, explicacao):
    sit = [("Bom padrão", "#15803d", "✅"), ("Atenção leve", "#d97706", "⚠️"),
           ("Déficit provável", "#dc2626", "🔺")][situacao_idx]
    return {"nome": nome, "valor": valor, "situacao": sit[0], "cor": sit[1],
            "icone": sit[2], "detalhe": detalhe, "explicacao": explicacao}


def analyze(teste: str, frames: list) -> dict | None:
    if teste not in TESTES or not frames:
        return None
    detected = sum(1 for f in frames if f is not None)
    if detected < 8:
        return None
    if teste == "agachamento":
        return _deep_squat(frames)
    return _single_leg(frames, "dir" if teste.endswith("dir") else "esq")


def _finish(teste, frame_idx, medidas, deficits):
    graves = sum(1 for m in medidas if m["icone"] == "🔺")
    leves = sum(1 for m in medidas if m["icone"] == "⚠️")
    if graves:
        resumo = (f"{graves} déficit(s) provável(is) e {leves} ponto(s) leve(s) — "
                  "os músculos abaixo merecem foco no treino.")
    elif leves:
        resumo = f"{leves} ponto(s) de atenção leve — padrões ajustáveis com treino."
    else:
        resumo = "Padrão de movimento dentro do esperado. Excelente base!"
    # deduplica déficits por grupo, mantendo o primeiro motivo
    vistos, dedup = set(), []
    for d in deficits:
        if d["grupo"] not in vistos:
            vistos.add(d["grupo"])
            dedup.append(d)
    return {
        "teste": teste,
        "nome": TESTES[teste]["nome"],
        "frame_idx": frame_idx,
        "medidas": medidas,
        "deficits": dedup,
        "resumo": resumo,
        "alertas": graves + leves,
        "graves": graves,
    }


def _deep_squat(frames) -> dict | None:
    """Agachamento profundo (vista lateral): profundidade, domínio do tronco e
    braços elevados — padrão overhead squat."""
    idx = _deepest(frames)
    if idx is None:
        return None
    f = frames[idx]

    # lado mais visível no quadro mais fundo
    def conf_sum(ids):
        return sum(float(f[i][2]) for i in ids if f[i][2] >= _CONF)

    dir_c = conf_sum([R_SH, R_HIP, R_KNEE, R_ANK])
    esq_c = conf_sum([L_SH, L_HIP, L_KNEE, L_ANK])
    if dir_c >= esq_c:
        SH, EL, WR, HIP, KNEE, ANK = R_SH, R_EL, R_WR, R_HIP, R_KNEE, R_ANK
    else:
        SH, EL, WR, HIP, KNEE, ANK = L_SH, L_EL, L_WR, L_HIP, L_KNEE, L_ANK

    sh, el, wr = _pt(f, SH), _pt(f, EL), _pt(f, WR)
    hip, knee, ank = _pt(f, HIP), _pt(f, KNEE), _pt(f, ANK)

    medidas, deficits = [], []

    # 1) profundidade (ângulo do joelho no fundo)
    joelho = _ang(hip, knee, ank)
    if joelho is not None:
        if joelho <= 95:
            si, det = 0, "Agachou fundo — ótima mobilidade."
        elif joelho <= 115:
            si, det = 1, "Profundidade razoável, dá para ganhar amplitude."
            deficits += [
                {"grupo": "panturrilha", "motivo": "Mobilidade de tornozelo limita a descida do agachamento."},
                {"grupo": "gluteos", "motivo": "Força/mobilidade de quadril para agachar mais fundo."},
            ]
        else:
            si, det = 2, "Profundidade limitada — mobilidade/força restringem o padrão."
            deficits += [
                {"grupo": "panturrilha", "motivo": "Tornozelo rígido é a trava mais comum do agachamento raso."},
                {"grupo": "gluteos", "motivo": "Fraqueza de quadril limita a profundidade com controle."},
                {"grupo": "quadriceps", "motivo": "Força de pernas para sustentar o agachamento completo."},
            ]
        medidas.append(_medida(
            "Profundidade (ângulo do joelho no fundo)", f"{joelho:.0f}°", si, det,
            "≤95° = agachamento profundo · 95–115° = parcial · >115° = limitado."))

    # 2) tronco × tíbia (domínio do tronco)
    tronco = _vert_ang(hip, sh)
    tibia = _vert_ang(ank, knee)
    if tronco is not None and tibia is not None:
        dif = tronco - tibia
        if dif <= 12:
            si, det = 0, "Tronco acompanha a tíbia — bom equilíbrio."
        elif dif <= 25:
            si, det = 1, "Tronco inclina um pouco além da tíbia."
            deficits.append({"grupo": "abdomen", "motivo": "Core para segurar o tronco durante o agachamento."})
        else:
            si, det = 2, "Tronco domina o movimento (inclina demais à frente)."
            deficits += [
                {"grupo": "abdomen", "motivo": "Core fraco deixa o tronco cair à frente no agachamento."},
                {"grupo": "posterior", "motivo": "Cadeia posterior/extensores para sustentar o tronco."},
            ]
        medidas.append(_medida(
            "Tronco × tíbia (paralelismo)", f"{dif:+.0f}°", si, det,
            "No bom padrão o tronco fica quase paralelo à tíbia (dif. ≤12°)."))

    # 3) braços elevados (mobilidade de ombro/dorsal)
    mao = wr if wr is not None else el
    if sh is not None and hip is not None and mao is not None:
        flexao = _ang(hip, sh, mao)  # 180° = braço alinhado com o tronco
        if flexao is not None:
            if flexao >= 150:
                si, det = 0, "Braços seguram acima da cabeça — boa mobilidade."
            elif flexao >= 125:
                si, det = 1, "Braços caem um pouco à frente."
                deficits.append({"grupo": "ombros", "motivo": "Mobilidade/força de ombro para manter os braços elevados."})
            else:
                si, det = 2, "Braços caem bastante — mobilidade de ombro/dorsal limitada."
                deficits += [
                    {"grupo": "ombros", "motivo": "Mobilidade de ombro limitada no padrão overhead."},
                    {"grupo": "costas", "motivo": "Dorsal/torácica rígidas puxam os braços para baixo."},
                ]
            medidas.append(_medida(
                "Braços elevados (flexão de ombro)", f"{flexao:.0f}°", si, det,
                "≥150° = braços firmes acima da cabeça no fundo do agachamento."))

    if not medidas:
        return None
    return _finish("agachamento", idx, medidas, deficits)


def _single_leg(frames, lado: str) -> dict | None:
    """Agachamento unilateral (vista frontal): valgo dinâmico do joelho e queda
    pélvica — sinais clássicos de déficit de glúteo médio/estabilizadores."""
    if lado == "dir":
        HIP, KNEE, ANK, HIP_LIVRE = R_HIP, R_KNEE, R_ANK, L_HIP
        teste = "unilateral_dir"
    else:
        HIP, KNEE, ANK, HIP_LIVRE = L_HIP, L_KNEE, L_ANK, R_HIP
        teste = "unilateral_esq"

    idx = _deepest(frames)
    if idx is None:
        return None
    f = frames[idx]
    hip, knee, ank = _pt(f, HIP), _pt(f, KNEE), _pt(f, ANK)
    hip_livre = _pt(f, HIP_LIVRE)
    if hip is None or knee is None or ank is None:
        return None

    medidas, deficits = [], []

    # 1) valgo dinâmico: desvio do joelho para DENTRO da linha quadril-tornozelo
    seg = ank - hip
    seg_len = float(np.linalg.norm(seg))
    if seg_len > 1:
        t = float(np.dot(knee - hip, seg) / (seg_len ** 2))
        proj = hip + t * seg                    # ponto da linha na altura do joelho
        desvio = knee - proj
        # "para dentro" = na direção do quadril livre (linha média do corpo)
        direcao_medial = 1.0 if (hip_livre is not None and hip_livre[0] > hip[0]) else -1.0
        valgo_px = float(desvio[0]) * direcao_medial
        valgo_pct = max(0.0, valgo_px) / seg_len * 100.0
        if valgo_pct <= 6:
            si, det = 0, "Joelho alinhado com quadril e tornozelo."
        elif valgo_pct <= 12:
            si, det = 1, "Joelho desvia um pouco para dentro (valgo leve)."
            deficits.append({"grupo": "gluteos", "motivo": "Glúteo médio fraco deixa o joelho cair para dentro."})
        else:
            si, det = 2, "Valgo dinâmico marcado — joelho desaba para dentro."
            deficits += [
                {"grupo": "gluteos", "motivo": "Glúteo médio/abdutores fracos — causa nº 1 do valgo dinâmico."},
                {"grupo": "quadriceps", "motivo": "Estabilidade do joelho na descida unilateral."},
            ]
        medidas.append(_medida(
            "Valgo dinâmico do joelho", f"{valgo_pct:.0f}%", si, det,
            "Desvio do joelho para dentro da linha quadril–tornozelo (≤6% = alinhado)."))

    # 2) queda pélvica (Trendelenburg)
    if hip_livre is not None:
        queda = math.degrees(math.atan2(hip_livre[1] - hip[1],
                                        abs(hip_livre[0] - hip[0]) + 1e-6))
        if queda <= 4:
            si, det = 0, "Pélvis nivelada durante o apoio unilateral."
        elif queda <= 9:
            si, det = 1, "Leve queda da pélvis do lado livre."
            deficits.append({"grupo": "gluteos", "motivo": "Glúteo médio do lado de apoio não segura a pélvis nivelada."})
        else:
            si, det = 2, "Queda pélvica marcada (sinal de Trendelenburg)."
            deficits += [
                {"grupo": "gluteos", "motivo": "Glúteo médio fraco no apoio — a pélvis despenca do lado livre."},
                {"grupo": "abdomen", "motivo": "Core lateral (quadrado lombar/oblíquos) para estabilizar a pélvis."},
            ]
        medidas.append(_medida(
            "Queda pélvica (Trendelenburg)", f"{max(0, queda):.0f}°", si, det,
            "Quanto a pélvis do lado livre cai no fundo (≤4° = estável)."))

    # 3) profundidade alcançada (informativa)
    joelho = _ang(hip, knee, ank)
    if joelho is not None:
        si = 0 if joelho <= 135 else 1
        medidas.append(_medida(
            "Profundidade unilateral", f"{joelho:.0f}°", si,
            "Boa amplitude com controle." if si == 0 else
            "Desceu pouco — repita descendo mais (com controle).",
            "Ângulo do joelho no ponto mais fundo do agachamento unilateral."))

    if not medidas:
        return None
    return _finish(teste, idx, medidas, deficits)
