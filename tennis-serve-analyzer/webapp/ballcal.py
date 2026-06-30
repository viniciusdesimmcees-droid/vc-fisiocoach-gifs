"""Calibração e verificação de escala pela BOLA.

Uma bola de tênis tem diâmetro conhecido e padronizado (ITF: 6,54–6,86 cm;
usamos 6,7 cm). Como o detector já enxerga a bola em pixels, dá para derivar
quantos metros vale cada pixel **no próprio plano de voo da bola** — exatamente
onde a velocidade é medida.

Isso serve para dois ganhos de confiabilidade:
  1. CRUZAR com a calibração manual (rede/linha): se as duas escalas batem, a
     medição é confiável; se divergem muito, a calibração manual provavelmente
     está errada (foi a causa do antigo 153 km/h num saque de 180).
  2. CALIBRAR automaticamente quando não há referência manual (a bola é a
     própria régua).

Honestidade: o raio detectado tem ruído e o desfoque de movimento (motion blur)
infla a bola nos quadros mais rápidos. Por isso usamos a MEDIANA robusta de
vários quadros, de preferência perto do impacto (mesmo plano da velocidade),
e tratamos o resultado como verificação — não como verdade absoluta.
"""

from __future__ import annotations

# diâmetro oficial da bola de tênis (m). ITF: 6,54–6,86 cm.
BALL_DIAMETER_M = 0.067


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def ball_scale(trajectory, ball_diameter_m: float = BALL_DIAMETER_M,
               impact_frame: int | None = None, window: int = 8,
               score_min: float = 0.0) -> dict | None:
    """Estima metros-por-pixel a partir do tamanho aparente da bola.

    Usa a mediana robusta do raio das detecções (em pixels de processamento).
    Se `impact_frame` é dado, prioriza os quadros perto do impacto (mesmo plano
    da medição de velocidade). Retorna None se não houver detecções suficientes.
    """
    dets = [d for d in trajectory
            if getattr(d, "radius", 0) and d.radius > 0
            and getattr(d, "score", 1.0) >= score_min]
    if len(dets) < 3:
        return None

    used = dets
    if impact_frame is not None:
        near = [d for d in dets if abs(d.frame - impact_frame) <= window]
        if len(near) >= 3:
            used = near

    radii = sorted(d.radius for d in used)
    n = len(radii)
    # apara 10% das pontas (outliers de blur / falsos positivos)
    trim = n // 10
    core = radii[trim:n - trim] if n - 2 * trim >= 3 else radii
    med_r = _median(core)
    if not med_r or med_r <= 0:
        return None

    diameter_px = 2.0 * med_r
    return {
        "mpp": ball_diameter_m / diameter_px,
        "radius_px": round(med_r, 2),
        "diameter_px": round(diameter_px, 2),
        "n": len(used),
        "ball_diameter_cm": round(ball_diameter_m * 100, 1),
    }


def cross_check(manual_mpp: float, ball_mpp: float, peak_kmh: float) -> dict:
    """Compara a escala manual com a escala derivada da bola."""
    if not manual_mpp or manual_mpp <= 0:
        return {}
    diff = (ball_mpp - manual_mpp) / manual_mpp * 100.0
    a = abs(diff)
    ball_peak = peak_kmh * (ball_mpp / manual_mpp)
    if a <= 12:
        verdict = "Calibração confirmada pela bola"
        cor, ic, nivel = "#15803d", "✅", "alta"
    elif a <= 25:
        verdict = "Pequena divergência — vale conferir a calibração"
        cor, ic, nivel = "#d97706", "⚠️", "media"
    else:
        verdict = "Divergência relevante — a calibração manual provavelmente está incorreta"
        cor, ic, nivel = "#dc2626", "🔺", "baixa"
    return {
        "diff_pct": round(diff, 1),
        "abs_pct": round(a, 1),
        "ball_peak_kmh": round(ball_peak, 1),
        "verdict": verdict,
        "cor": cor,
        "icone": ic,
        "nivel": nivel,
    }
