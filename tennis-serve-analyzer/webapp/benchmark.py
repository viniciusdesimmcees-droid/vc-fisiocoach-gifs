"""Benchmark contra padrão profissional.

Posiciona cada métrica do atleta numa escala de nível
(Iniciante → Recreativo → Avançado → Competitivo → Profissional) e calcula:
  - o nível atual da métrica,
  - um percentil rumo ao PRO (0–100, quão perto do padrão profissional),
  - o que falta para chegar ao nível pro + uma dica de treino.

Gera ainda um gráfico RADAR (atleta × pro) e um índice geral de nível.

Honestidade: as faixas são APROXIMADAS, compiladas da literatura de biomecânica
do tênis e de medições típicas por faixa de jogo. Métricas 2D têm margem. Serve
como guia de desenvolvimento e meta — não como avaliação oficial de ranking.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NIVEIS = ["Iniciante", "Recreativo", "Avançado", "Competitivo", "Profissional"]
CRED = "Sistema criado e desenvolvido por Vinícius Camargos da Fonseca."


def _g(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


# Cada métrica: como obter o valor + faixas por nível.
# dir="maior" (quanto maior melhor) ou "menor" (quanto menor melhor).
# bands = limiares para [Recreativo, Avançado, Competitivo, Profissional].
# floor = valor de "0%"; pro_ref = valor que conta como 100% (padrão pro).
REFS = [
    {"chave": "velocidade", "nome": "Velocidade de pico", "short": "Velocidade",
     "unid": "km/h", "dir": "maior", "bands": [120, 150, 170, 190],
     "floor": 90, "pro_ref": 195,
     "dica": "Potência de pernas + timing do chicote (ombro→cotovelo→punho).",
     "get": lambda s, b: _g(s, "resultado", "velocidade_pico_kmh")},
    {"chave": "cotovelo", "nome": "Extensão do cotovelo no impacto", "short": "Cotovelo",
     "unid": "°", "dir": "maior", "bands": [135, 145, 155, 162],
     "floor": 115, "pro_ref": 165,
     "dica": "Bater com o braço quase reto, no ponto mais alto.",
     "get": lambda s, b: _g(b, "angulos_no_contato", "cotovelo")},
    {"chave": "joelho", "nome": "Flexão de joelho no carregamento", "short": "Joelhos",
     "unid": "°", "dir": "menor", "bands": [150, 140, 130, 122],
     "floor": 170, "pro_ref": 115,
     "dica": "Dobrar mais os joelhos para carregar e explodir para cima.",
     "get": lambda s, b: _g(b, "angulos_no_loading", "joelho")},
    {"chave": "xfactor", "nome": "X-Factor (ombro–quadril)", "short": "X-Factor",
     "unid": "°", "dir": "maior", "bands": [25, 33, 40, 45],
     "floor": 12, "pro_ref": 48,
     "dica": "Coiling: separar ombros do quadril para armazenar energia elástica.",
     "get": lambda s, b: _g(b, "metricas_avancadas", "x_factor", "separacao_max_graus")},
    {"chave": "av_ombro", "nome": "Velocidade angular do ombro", "short": "Vel. ombro",
     "unid": "°/s", "dir": "maior", "bands": [600, 800, 1000, 1150],
     "floor": 400, "pro_ref": 1150,
     "dica": "Explosão da rotação do ombro na fase de aceleração.",
     "get": lambda s, b: _g(b, "metricas_avancadas", "velocidades_angulares_max", "ombro")},
    {"chave": "av_cotovelo", "nome": "Velocidade angular do cotovelo", "short": "Vel. cotovelo",
     "unid": "°/s", "dir": "maior", "bands": [750, 950, 1150, 1250],
     "floor": 500, "pro_ref": 1250,
     "dica": "Extensão rápida do cotovelo na raquetada (chicote).",
     "get": lambda s, b: _g(b, "metricas_avancadas", "velocidades_angulares_max", "cotovelo")},
]


def _nivel_idx(v, bands, direction):
    """Índice de nível 0..4 a partir das faixas."""
    if direction == "maior":
        idx = 0
        for i, t in enumerate(bands):
            if v >= t:
                idx = i + 1
        return idx
    else:  # menor é melhor
        idx = 0
        for i, t in enumerate(bands):
            if v <= t:
                idx = i + 1
        return idx


def _percentil(v, floor, pro_ref, direction):
    if direction == "maior":
        p = (v - floor) / (pro_ref - floor) * 100.0
    else:
        p = (floor - v) / (floor - pro_ref) * 100.0
    return max(0.0, min(100.0, p))


def _gap_txt(v, pro_ref, direction, unid):
    if direction == "maior":
        if v >= pro_ref:
            return "No nível profissional."
        return f"Faltam ~{pro_ref - v:.0f} {unid} para o padrão pro."
    else:
        if v <= pro_ref:
            return "No nível profissional."
        return f"Reduzir ~{v - pro_ref:.0f} {unid} para o padrão pro."


def evaluate(summary: dict, biomech: dict | None, excluded=None) -> dict | None:
    excluded = excluded or set()
    metricas = []
    for r in REFS:
        if r["chave"] in excluded:
            continue
        v = r["get"](summary, biomech)
        if v is None:
            continue
        v = float(v)
        idx = _nivel_idx(v, r["bands"], r["dir"])
        perc = _percentil(v, r["floor"], r["pro_ref"], r["dir"])
        metricas.append({
            "chave": r["chave"], "nome": r["nome"], "short": r["short"],
            "valor": f"{v:.0f} {r['unid']}", "valor_num": v,
            "nivel": NIVEIS[idx], "nivel_idx": idx,
            "percentil": round(perc),
            "pro_ref": f"{r['pro_ref']:.0f} {r['unid']}",
            "gap": _gap_txt(v, r["pro_ref"], r["dir"], r["unid"]),
            "no_pro": (v >= r["pro_ref"]) if r["dir"] == "maior" else (v <= r["pro_ref"]),
            "dica": r["dica"],
        })
    if not metricas:
        return None

    indice = round(sum(m["percentil"] for m in metricas) / len(metricas))
    if indice < 30:
        nivel, cor = "Iniciante", "#64748b"
    elif indice < 50:
        nivel, cor = "Recreativo", "#0ea5e9"
    elif indice < 70:
        nivel, cor = "Avançado", "#15803d"
    elif indice < 85:
        nivel, cor = "Competitivo", "#d97706"
    else:
        nivel, cor = "Nível profissional", "#dc2626"

    # o que falta: métricas mais distantes do pro (com espaço para crescer)
    faltam = sorted([m for m in metricas if not m["no_pro"]],
                    key=lambda m: m["percentil"])[:3]

    if faltam:
        resumo = (f"Índice de nível {indice}/100 ({nivel}). As maiores oportunidades "
                  "estão em: " + ", ".join(m["short"] for m in faltam) + ".")
    else:
        resumo = (f"Índice de nível {indice}/100 ({nivel}). Métricas avaliadas já no "
                  "padrão profissional — excelente!")

    return {
        "indice": indice, "nivel": nivel, "cor": cor,
        "metricas": metricas, "faltam": faltam, "resumo": resumo,
        "tem_radar": len(metricas) >= 3,
    }


def radar_png(metricas: list) -> bytes:
    """Gráfico radar: percentil do atleta (rumo ao pro) × linha do pro (100%)."""
    labels = [m["short"] for m in metricas]
    vals = [m["percentil"] for m in metricas]
    n = len(labels)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    vals_c = vals + vals[:1]
    ang_c = ang + ang[:1]

    fig, ax = plt.subplots(figsize=(6.2, 6.2), subplot_kw={"polar": True})
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    # linha do padrão pro (100%)
    ax.plot(ang_c, [100] * len(ang_c), "--", color="#dc2626", lw=1.5,
            label="Padrão profissional")
    ax.fill(ang_c, [100] * len(ang_c), color="#dc2626", alpha=0.05)
    # atleta
    ax.plot(ang_c, vals_c, "-o", color="#15803d", lw=2, ms=5, label="Atleta")
    ax.fill(ang_c, vals_c, color="#22c55e", alpha=0.25)
    ax.set_xticks(ang)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100 (pro)"], fontsize=8, color="#64748b")
    ax.set_title("Benchmark vs. profissional — % rumo ao padrão pro",
                 fontsize=12, pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.10), fontsize=9)
    fig.text(0.5, 0.02, CRED, ha="center", fontsize=7, color="#9aa39c")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
