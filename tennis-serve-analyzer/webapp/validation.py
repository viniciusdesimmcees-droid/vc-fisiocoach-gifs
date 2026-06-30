"""Validação científica: especificação de acurácia + autoteste por física.

Duas peças de credibilidade:

1) FICHA TÉCNICA DE ACURÁCIA — documenta o método (velocidade = px/quadro × fps
   × m/px), as fontes de erro e a acurácia ESPERADA sob protocolo, derivada do
   mesmo modelo de incerteza usado no selo de confiança (coerência interna).

2) AUTOTESTE POR QUEDA LIVRE — um teste que QUALQUER pessoa pode reproduzir,
   sem radar: solte uma bola de uma altura medida H; pela física, a velocidade
   no momento do impacto é v = sqrt(2·g·H) (resistência do ar desprezível para
   quedas curtas). Filme a queda, meça no app e compare. É uma referência de
   velocidade CONHECIDA e independente para checar toda a cadeia de medição.

Honestidade: os números de acurácia vêm de um modelo de engenharia (não de
certificação de laboratório). O autoteste valida a cadeia em BAIXA velocidade;
para alta velocidade, o fator decisivo é fps adequado (verificado no pré-voo).
"""

from __future__ import annotations

import math

G = 9.81  # m/s²


def expected_drop_speed(height_m: float) -> dict:
    """Velocidade teórica de impacto de uma bola solta da altura H (queda livre)."""
    h = max(0.0, float(height_m))
    v_ms = math.sqrt(2 * G * h)
    return {
        "altura_m": round(h, 2),
        "v_ms": round(v_ms, 2),
        "v_kmh": round(v_ms * 3.6, 1),
        "formula": "v = √(2 · g · H), g = 9,81 m/s²",
    }


def drop_table(heights=(0.5, 1.0, 1.5, 2.0, 2.5, 3.0)) -> list[dict]:
    return [expected_drop_speed(h) for h in heights]


def compare_drop(height_m: float, measured_kmh: float) -> dict:
    """Compara a medição do app com a física, para o autoteste."""
    exp = expected_drop_speed(height_m)
    ev = exp["v_kmh"]
    err = (measured_kmh - ev)
    err_pct = (err / ev * 100.0) if ev else 0.0
    a = abs(err_pct)
    if a <= 7:
        veredito, cor = "Excelente — dentro da margem esperada", "#15803d"
    elif a <= 15:
        veredito, cor = "Bom — pequena diferença, aceitável", "#d97706"
    else:
        veredito, cor = "Fora da margem — revise calibração/fps/captura", "#dc2626"
    return {
        "altura_m": exp["altura_m"],
        "esperado_kmh": ev,
        "medido_kmh": round(float(measured_kmh), 1),
        "erro_kmh": round(err, 1),
        "erro_pct": round(err_pct, 1),
        "veredito": veredito,
        "cor": cor,
    }


# ---- especificação de acurácia (derivada do modelo de incerteza) ----
# rel = sqrt(fps² + calibração² + rastreio²)
_SCENARIOS = [
    {"nome": "Ideal (laudo pericial)",
     "cond": "240 fps · calibração confirmada pela bola · captura Boa",
     "fps": 0.015, "cal": 0.03, "trk": 0.022},
    {"nome": "Recomendado",
     "cond": "120 fps · calibração da quadra + bola · captura Boa",
     "fps": 0.04, "cal": 0.035, "trk": 0.03},
    {"nome": "Mínimo aceitável",
     "cond": "60 fps · calibração simples · captura Regular",
     "fps": 0.08, "cal": 0.06, "trk": 0.05},
]

_REF_SPEEDS = (120, 150, 180, 200)


def accuracy_spec() -> list[dict]:
    rows = []
    for s in _SCENARIOS:
        rel = math.sqrt(s["fps"] ** 2 + s["cal"] ** 2 + s["trk"] ** 2)
        rows.append({
            "nome": s["nome"],
            "cond": s["cond"],
            "erro_pct": round(rel * 100, 1),
            "margens": {v: round(v * rel) for v in _REF_SPEEDS},
        })
    return rows


REF_SPEEDS = _REF_SPEEDS


# ---- blocos de metodologia (texto reutilizado na página e no PDF) ----
METODOLOGIA = [
    ("Como a velocidade é medida",
     "A bola é rastreada quadro a quadro. A velocidade é o deslocamento entre "
     "quadros convertido para metros (pela calibração) e dividido pelo tempo "
     "entre quadros (1/fps): velocidade = pixels/quadro × fps × metros/pixel. "
     "Reportamos o pico como a maior MEDIANA de uma janela sustentada, não um "
     "quadro isolado — assim um ruído pontual não vira 'recorde'."),
    ("As três fontes de erro",
     "1) fps: define a precisão do tempo; saques rápidos exigem 120–240 fps. "
     "2) Calibração: a escala metros/pixel; conferida de forma independente pelo "
     "tamanho da bola (6,7 cm). 3) Rastreio: continuidade e nitidez da bola. "
     "As incertezas se somam em quadratura e viram a margem (± km/h) e o nível "
     "de confiança de cada análise."),
    ("Verificações automáticas",
     "Cada análise passa pelo pré-voo (câmera lateral, fps × velocidade, bola "
     "visível, calibração plausível, desfoque) e pelo cruzamento quadra × bola. "
     "O número só ganha 'Confiança Alta' quando essas verificações passam."),
    ("Limitações (honestidade técnica)",
     "É uma medição 2D por vídeo de celular — não é radar Doppler. A escala vale "
     "no plano de voo da bola; ângulos muito oblíquos introduzem erro. As faixas "
     "biomecânicas e de referência são aproximadas, da literatura. Use como "
     "instrumento de acompanhamento e apoio à decisão, não como diagnóstico médico."),
]
