"""Relatório profissional ilustrado: velocímetro, classificação e PDF.

Tudo com matplotlib (já é dependência) — sem libs novas, roda em qualquer host.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
from matplotlib.backends.backend_pdf import PdfPages

CREDIT = "Sistema criado e desenvolvido por Vinícius Camargos da Fonseca."
GAUGE_MAX = 240.0  # fim de escala do velocímetro (km/h)

# Faixas de classificação do saque (km/h). Referências aproximadas de tênis.
BANDS = [
    (0, 100, "Iniciante", "#94a3b8",
     "Base em desenvolvimento — foco em técnica e consistência."),
    (100, 140, "Intermediário", "#38bdf8",
     "Boa geração de velocidade — refine a cadeia cinética."),
    (140, 170, "Avançado", "#22c55e",
     "Saque forte — nível de jogador competitivo regional."),
    (170, 200, "Competitivo", "#f59e0b",
     "Alto rendimento — faixa de nível estadual/nacional."),
    (200, 9999, "Elite", "#ef4444",
     "Faixa profissional — saque de elite."),
]


def classify(peak_kmh: float) -> dict:
    for lo, hi, nome, cor, desc in BANDS:
        if lo <= peak_kmh < hi:
            return {"nivel": nome, "cor": cor, "descricao": desc,
                    "faixa": f"{lo}–{hi if hi < 9999 else '+'} km/h"}
    return {"nivel": "—", "cor": "#94a3b8", "descricao": "", "faixa": ""}


def _v_to_angle(v: float) -> float:
    """km/h -> ângulo do velocímetro (180° em 0, 0° no fim de escala)."""
    v = max(0.0, min(GAUGE_MAX, v))
    return 180.0 - (v / GAUGE_MAX) * 180.0


def draw_gauge(ax, peak_kmh: float, cls: dict) -> None:
    """Desenha um velocímetro semicircular com zonas coloridas e ponteiro."""
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-0.35, 1.25)

    r_out, r_in = 1.0, 0.72
    for lo, hi, _, cor, _ in BANDS:
        a1 = _v_to_angle(min(hi, GAUGE_MAX))
        a2 = _v_to_angle(lo)
        ax.add_patch(Wedge((0, 0), r_out, a1, a2, width=r_out - r_in,
                           facecolor=cor, edgecolor="white", lw=2))

    # marcas de escala
    for v in range(0, int(GAUGE_MAX) + 1, 40):
        import math
        ang = math.radians(_v_to_angle(v))
        x, y = math.cos(ang), math.sin(ang)
        ax.text(x * 1.12, y * 1.12, str(v), ha="center", va="center",
                fontsize=8, color="#64748b")

    # ponteiro
    import math
    ang = math.radians(_v_to_angle(peak_kmh))
    ax.plot([0, math.cos(ang) * (r_in - 0.02)], [0, math.sin(ang) * (r_in - 0.02)],
            color="#0f1714", lw=3, solid_capstyle="round", zorder=5)
    ax.add_patch(plt.Circle((0, 0), 0.05, color="#0f1714", zorder=6))

    # número central + nível
    ax.text(0, 0.30, f"{peak_kmh:.0f}", ha="center", va="center",
            fontsize=34, fontweight="bold", color=cls["cor"])
    ax.text(0, 0.13, "km/h", ha="center", va="center", fontsize=11, color="#64748b")
    ax.text(0, -0.20, cls["nivel"].upper(), ha="center", va="center",
            fontsize=13, fontweight="bold", color=cls["cor"])


def write_gauge_png(path: str, peak_kmh: float, cls: dict) -> None:
    fig, ax = plt.subplots(figsize=(5, 3.3))
    draw_gauge(ax, peak_kmh, cls)
    fig.tight_layout()
    fig.savefig(path, dpi=130, transparent=True)
    plt.close(fig)


def write_report_pdf(
    path: str, athlete: str, summary: dict, cls: dict, speed_png: str,
) -> None:
    """Monta um relatório PDF A4 profissional de uma página."""
    r = summary.get("resultado", {})
    cap = summary.get("captura", {})
    peak = r.get("velocidade_pico_kmh", 0)

    fig = plt.figure(figsize=(8.27, 11.69))  # A4 retrato
    fig.patch.set_facecolor("white")

    # cabeçalho
    fig.text(0.06, 0.955, "VF Tênis Scanner", fontsize=22, fontweight="bold",
             color="#15803d")
    fig.text(0.06, 0.935, "Relatório de Análise do Saque", fontsize=12,
             color="#334155")
    fig.text(0.94, 0.955, athlete, fontsize=13, fontweight="bold",
             color="#0f1714", ha="right")
    fig.text(0.94, 0.937, summary.get("gerado_em", "")[:10], fontsize=10,
             color="#64748b", ha="right")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.922, 0.922], color="#e6ece8", lw=1))

    # velocímetro
    ax_g = fig.add_axes([0.08, 0.62, 0.5, 0.27])
    draw_gauge(ax_g, peak, cls)

    # classificação (texto ao lado)
    fig.text(0.60, 0.85, "Classificação", fontsize=11, color="#64748b")
    fig.text(0.60, 0.815, cls["nivel"], fontsize=20, fontweight="bold",
             color=cls["cor"])
    fig.text(0.60, 0.785, f"Faixa: {cls['faixa']}", fontsize=10, color="#334155")
    ax_desc = fig.add_axes([0.60, 0.66, 0.34, 0.10]); ax_desc.axis("off")
    ax_desc.text(0, 1, cls["descricao"], fontsize=10, color="#334155", va="top",
                 wrap=True, transform=ax_desc.transAxes)

    # métricas-chave
    metrics = [
        ("Velocidade de pico", f"{peak:.0f} km/h"),
        ("Velocidade média", f"{r.get('velocidade_media_kmh', 0):.0f} km/h"),
        ("Quadro do impacto", str(r.get("quadro_impacto", "—"))),
        ("Captura", f"{cap.get('fps', 0):.0f} fps · {cap.get('resolucao', '—')}"),
    ]
    y0 = 0.56
    for i, (k, v) in enumerate(metrics):
        x = 0.06 + (i % 2) * 0.46
        y = y0 - (i // 2) * 0.07
        ax = fig.add_axes([x, y, 0.42, 0.06]); ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                                   facecolor="#f1f6f3", edgecolor="#e6ece8"))
        ax.text(0.04, 0.62, k, fontsize=9, color="#64748b", transform=ax.transAxes)
        ax.text(0.04, 0.22, v, fontsize=14, fontweight="bold", color="#0f1714",
                transform=ax.transAxes)

    # gráfico de velocidade
    if speed_png and os.path.exists(speed_png):
        import matplotlib.image as mpimg
        ax_p = fig.add_axes([0.06, 0.20, 0.88, 0.21]); ax_p.axis("off")
        ax_p.imshow(mpimg.imread(speed_png))

    # explicações
    fig.text(0.06, 0.165, "Como ler este relatório", fontsize=12,
             fontweight="bold", color="#15803d")
    expl = (
        "• Velocidade de pico: maior velocidade da bola logo após o impacto — o "
        "indicador principal de potência do saque.\n"
        "• Velocidade média: média ao longo do trajeto rastreado.\n"
        "• Quadro do impacto: momento em que a raquete acerta a bola.\n"
        "• Para precisão pericial, grave em câmera lenta (120–240 fps), câmera "
        "lateral fixa e com um objeto de referência de tamanho conhecido no plano "
        "do saque (calibração)."
    )
    ax_e = fig.add_axes([0.06, 0.06, 0.88, 0.09]); ax_e.axis("off")
    ax_e.text(0, 1, expl, fontsize=9.5, color="#334155", va="top",
              transform=ax_e.transAxes, linespacing=1.6)

    fig.text(0.5, 0.025, CREDIT, ha="center", fontsize=8, color="#94a3b8")

    with PdfPages(path) as pdf:
        pdf.savefig(fig)
    plt.close(fig)
