"""Índice de confiança da medição + margem de erro (selo de credibilidade).

Junta as TRÊS fontes reais de incerteza da fórmula
    velocidade = pixels/quadro × fps × metros/pixel
num único selo por análise, ex.: "180 ± 6 km/h · Confiança Alta".

As incertezas relativas se somam em quadratura (independentes):
    erro_total = sqrt(erro_fps² + erro_calibração² + erro_rastreio²)
e a margem em km/h = pico × erro_total.

Tudo é transparente: devolve a contribuição de cada fator e uma explicação.
Honestidade: são estimativas de engenharia (não um certificado de laboratório),
mas calibradas para refletir o que realmente degrada a medição.
"""

from __future__ import annotations

import math
import statistics


def _level(total_rel: float):
    if total_rel <= 0.05:
        return "Alta", "#15803d", 0
    if total_rel <= 0.12:
        return "Média", "#d97706", 1
    return "Baixa", "#dc2626", 2


def evaluate(result, meta: dict, fps: float, file_fps: float,
             calibracao: dict | None) -> dict:
    peak = float(getattr(result, "peak_kmh", 0.0) or 0.0)
    factors = []

    # ---------- 1) fps (amostragem temporal) ----------
    if fps >= 200:
        fps_rel, fps_txt = 0.015, "Excelente (slow-motion alta)."
    elif fps >= 150:
        fps_rel, fps_txt = 0.025, "Muito boa."
    elif fps >= 100:
        fps_rel, fps_txt = 0.04, "Adequada para saque."
    elif fps >= 60:
        fps_rel, fps_txt = 0.08, "Limitada — saques rápidos perdem precisão."
    else:
        fps_rel, fps_txt = 0.16, "Baixa — velocidade vira estimativa grosseira."
    if file_fps and abs(file_fps - fps) > 5:
        fps_rel += 0.06
        fps_txt += (f" O arquivo indica {file_fps:.0f} fps, mas usou {fps:.0f}: "
                    "confirme o fps real.")
    factors.append({
        "nome": "Taxa de quadros (fps)",
        "valor": f"{fps:.0f} fps",
        "contrib_pct": round(fps_rel * 100, 1),
        "texto": fps_txt,
    })

    # ---------- 2) calibração (escala metros/pixel) ----------
    cross = (calibracao or {}).get("cross")
    modo = (calibracao or {}).get("modo")
    if cross:
        ap = cross.get("abs_pct", 0) / 100.0
        if cross.get("nivel") == "alta":
            cal_rel = max(0.03, ap)
            cal_txt = "Quadra e bola batem — escala confirmada."
        elif cross.get("nivel") == "media":
            cal_rel = max(0.06, ap * 0.7)
            cal_txt = f"Quadra e bola diferem {cross.get('abs_pct', 0):.0f}% — confira a calibração."
        else:
            cal_rel = max(0.15, ap)
            cal_txt = (f"Quadra e bola divergem {cross.get('abs_pct', 0):.0f}% — "
                       "calibração provavelmente incorreta.")
        cal_val = f"manual + bola (Δ {cross.get('abs_pct', 0):.0f}%)"
    elif modo == "ball":
        cal_rel = 0.08
        cal_txt = "Calibração automática pela bola (sem confirmação da quadra)."
        cal_val = "automática (bola)"
    else:
        cal_rel = 0.06
        cal_txt = "Calibração da quadra, sem cruzamento com a bola."
        cal_val = "manual (quadra)"
    factors.append({
        "nome": "Calibração (escala)",
        "valor": cal_val,
        "contrib_pct": round(cal_rel * 100, 1),
        "texto": cal_txt,
    })

    # ---------- 3) rastreio da bola (qualidade do pico) ----------
    samples = list(getattr(result, "samples", []) or [])
    high = [s.speed_kmh for s in samples if peak > 0 and s.speed_kmh >= 0.85 * peak]
    n_high = len(high)
    if n_high >= 2:
        mean_h = statistics.mean(high)
        cv = (statistics.pstdev(high) / mean_h) if mean_h else 0.06
    else:
        cv = 0.06
    track_rel = 0.02 + min(cv, 0.12)
    track_txt = "Pico sustentado e estável."
    if n_high < 3:
        track_rel += 0.04
        track_txt = "Pico pouco sustentado (poucos quadros de alta velocidade)."
    dets = meta.get("detections", 0)
    if dets < 10:
        track_rel += 0.03
        track_txt += f" Poucas detecções da bola ({dets})."
    track_rel = min(track_rel, 0.20)
    factors.append({
        "nome": "Rastreio da bola",
        "valor": f"{n_high} quadro(s) de pico · {dets} detecções",
        "contrib_pct": round(track_rel * 100, 1),
        "texto": track_txt,
    })

    # ---------- total ----------
    total_rel = math.sqrt(fps_rel ** 2 + cal_rel ** 2 + track_rel ** 2)
    margin = round(peak * total_rel) if peak > 0 else 0
    nivel, cor, _ = _level(total_rel)
    score = max(1, round(100 * (1 - min(total_rel / 0.25, 1.0))))

    low = max(0, round(peak - margin))
    high_v = round(peak + margin)
    return {
        "pico_kmh": round(peak),
        "margem_kmh": margin,
        "faixa": f"{low}–{high_v} km/h",
        "headline": f"{round(peak)} ± {margin} km/h",
        "nivel": nivel,
        "cor": cor,
        "score": score,
        "erro_rel_pct": round(total_rel * 100, 1),
        "fatores": factors,
        "resumo": _resumo(nivel, margin),
    }


def _resumo(nivel: str, margin: int) -> str:
    if nivel == "Alta":
        return (f"Medição confiável: a velocidade real deve estar a no máximo "
                f"±{margin} km/h do valor exibido.")
    if nivel == "Média":
        return (f"Medição razoável (±{margin} km/h). Dá para melhorar com mais fps, "
                "calibração confirmada pela bola e bola bem rastreada.")
    return (f"Confiança baixa (±{margin} km/h). Trate o número como aproximado e "
            "refaça a captura (slow-motion, câmera lateral, calibração correta).")
