"""Avaliação técnica do saque: nota (0–100), pontos fortes/atenção e
recomendações personalizadas.

Combina a potência (velocidade) com a qualidade biomecânica (quando disponível).
Tudo transparente e explicável — nada de "caixa-preta".
"""

from __future__ import annotations


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _score_color(score: float) -> str:
    if score >= 80:
        return "#15803d"
    if score >= 60:
        return "#22c55e"
    if score >= 40:
        return "#f59e0b"
    return "#ef4444"


def evaluate(summary: dict, biomech: dict | None) -> dict:
    r = summary.get("resultado", {})
    peak = float(r.get("velocidade_pico_kmh", 0) or 0)

    breakdown: list[tuple[str, float, float]] = []
    fortes: list[str] = []
    atencao: list[str] = []
    recs: list[str] = []

    # ---- Potência (velocidade) ----
    pot_ratio = _clamp(peak / 210.0, 0.0, 1.0)
    tem_bio = bool(biomech and biomech.get("angulos_no_contato"))
    pot_max = 40.0 if tem_bio else 100.0
    pot_pts = round(pot_ratio * pot_max, 1)
    breakdown.append(("Potência (velocidade)", pot_pts, pot_max))
    if peak >= 170:
        fortes.append(f"Excelente potência: {peak:.0f} km/h.")
    elif peak >= 130:
        fortes.append(f"Boa geração de velocidade: {peak:.0f} km/h.")
    else:
        recs.append("Ganhe potência com mais impulsão de pernas e rotação de tronco "
                    "antes de soltar o braço.")

    # ---- Biomecânica (quando há pose) ----
    if tem_bio:
        ang_c = biomech.get("angulos_no_contato") or {}
        ang_l = biomech.get("angulos_no_loading") or {}
        chain = biomech.get("cadeia_cinetica") or {}

        # Cadeia cinética proximal -> distal (0–25)
        if chain.get("proximal_para_distal"):
            breakdown.append(("Cadeia cinética", 25.0, 25.0))
            fortes.append("Cadeia cinética eficiente (proximal → distal preservada).")
        else:
            breakdown.append(("Cadeia cinética", 9.0, 25.0))
            atencao.append("Sequência da cadeia cinética quebrada.")
            recs.append("Treine a ordem de ativação: pernas → quadril → tronco → "
                        "ombro → cotovelo/punho, sem antecipar o braço.")

        # Uso das pernas: flexão de joelho no carregamento (0–20)
        joelho_load = ang_l.get("joelho")
        if joelho_load is not None:
            # quanto mais flexionado (ângulo menor), melhor a carga (ideal ~110–140°)
            flex = _clamp((175 - joelho_load) / (175 - 120), 0.0, 1.0)
            pts = round(flex * 20, 1)
            breakdown.append(("Uso das pernas (carga)", pts, 20.0))
            if joelho_load <= 150:
                fortes.append(f"Boa flexão de joelhos no carregamento ({joelho_load:.0f}°).")
            else:
                atencao.append(f"Pouca flexão de joelhos no carregamento ({joelho_load:.0f}°).")
                recs.append("Flexione mais os joelhos antes do impacto para usar a "
                            "força das pernas (impulsão).")
        else:
            breakdown.append(("Uso das pernas (carga)", 10.0, 20.0))

        # Extensão do braço no impacto: cotovelo (0–15)
        cot = ang_c.get("cotovelo")
        if cot is not None:
            ext = _clamp((cot - 120) / (165 - 120), 0.0, 1.0)
            pts = round(ext * 15, 1)
            breakdown.append(("Extensão do braço no impacto", pts, 15.0))
            if cot >= 150:
                fortes.append(f"Braço bem estendido no impacto ({cot:.0f}°).")
            else:
                atencao.append(f"Cotovelo flexionado no impacto ({cot:.0f}°).")
                recs.append("Busque acertar a bola com o braço mais estendido, no "
                            "ponto mais alto possível.")
        else:
            breakdown.append(("Extensão do braço no impacto", 7.5, 15.0))
        # indicadores de risco (das métricas avançadas)
        for f in (biomech.get("metricas_avancadas", {}) or {}).get("indicadores_risco", []):
            if f.get("nivel") == "atenção":
                atencao.append("Risco — " + f.get("texto", ""))
    else:
        recs.append("Ative a análise biomecânica (marque a opção e filme o atleta "
                    "de corpo inteiro, câmera lateral) para uma avaliação completa.")

    score = round(sum(p for _, p, _ in breakdown), 0)
    total_max = sum(m for _, _, m in breakdown)
    score = round(score / total_max * 100, 0) if total_max else 0.0

    nivel = ("Elite" if score >= 85 else "Avançado" if score >= 70
             else "Intermediário" if score >= 50 else "Em evolução")

    if not recs:
        recs.append("Gesto sólido — mantenha a consistência e a regularidade do saque.")

    return {
        "score": score,
        "cor": _score_color(score),
        "nivel": nivel,
        "breakdown": breakdown,
        "fortes": fortes,
        "atencao": atencao,
        "recomendacoes": recs,
        "tem_biomecanica": tem_bio,
    }
