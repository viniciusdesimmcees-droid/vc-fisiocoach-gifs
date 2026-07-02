"""Mapa corporal para o PDF: boneco (frente + costas) com os pontos da
avaliação marcados em cores — versão estática do boneco 3D interativo.

Usa os mesmos `pontos` do avatar (avaliação postural + plano inteligente).
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Ellipse, Polygon

BODY = "#d9e3dd"
EDGE = "#b9c9bf"

# posição 2D de cada região por vista (x, y); atleta de FRENTE: direita = x<0
FRONT_POS = {
    "cabeca": [(0, 1.66)],
    "ombros": [(0.26, 1.38), (-0.26, 1.38)],
    "ombro_dir": [(-0.26, 1.38)], "ombro_esq": [(0.26, 1.38)],
    "peito": [(0, 1.27)],
    "tronco": [(0, 1.15)],
    "abdomen": [(0, 1.04)],
    "braco_dir": [(-0.33, 1.14)], "braco_esq": [(0.33, 1.14)],
    "antebraco_dir": [(-0.40, 0.90)], "antebraco_esq": [(0.40, 0.90)],
    "pelvis": [(0, 0.94)],
    "coxas": [(0.12, 0.64), (-0.12, 0.64)],
    "joelhos": [(0.12, 0.46), (-0.12, 0.46)],
}
BACK_POS = {
    "trapezio": [(0.12, 1.44), (-0.12, 1.44)],
    "costas": [(0, 1.22)],
    "lombar": [(0, 1.00)],
    "gluteos": [(0.10, 0.88), (-0.10, 0.88)],
    "panturrilhas": [(0.12, 0.28), (-0.12, 0.28)],
}


def _draw_body(ax):
    """Silhueta simples do corpo (frente/costas são iguais no esquema)."""
    def line(p1, p2, lw):
        ax.add_line(Line2D([p1[0], p2[0]], [p1[1], p2[1]], lw=lw, color=BODY,
                           solid_capstyle="round", zorder=1))

    ax.add_patch(Circle((0, 1.62), 0.115, fc=BODY, ec=EDGE, zorder=1))
    line((0, 1.46), (0, 1.54), 9)                    # pescoço
    ax.add_patch(Polygon([(-0.23, 1.41), (0.23, 1.41), (0.16, 0.97),
                          (-0.16, 0.97)], closed=True, fc=BODY, ec=EDGE, zorder=1))
    ax.add_patch(Ellipse((0, 0.93), 0.36, 0.20, fc=BODY, ec=EDGE, zorder=1))
    for s in (1, -1):
        line((s * 0.23, 1.39), (s * 0.32, 1.10), 8)   # braço
        line((s * 0.32, 1.10), (s * 0.39, 0.85), 7)   # antebraço
        ax.add_patch(Circle((s * 0.40, 0.81), 0.05, fc=BODY, ec=EDGE, zorder=1))
        line((s * 0.11, 0.92), (s * 0.12, 0.50), 12)  # coxa
        line((s * 0.12, 0.50), (s * 0.13, 0.10), 9)   # perna
        line((s * 0.13, 0.08), (s * 0.16, 0.05), 8)   # pé

    ax.set_xlim(-0.62, 0.62)
    ax.set_ylim(-0.02, 1.86)
    ax.set_aspect("equal")
    ax.axis("off")


def _draw_markers(ax, pontos, positions):
    count: dict[tuple, int] = {}
    for p in pontos:
        for (x, y) in positions.get(p.get("regiao"), []):
            key = (round(x, 2), round(y, 2))
            n = count[key] = count.get(key, 0) + 1
            ax.scatter([x], [y + (n - 1) * 0.085], s=200,
                       c=p.get("cor", "#94a3b8"), edgecolors="white",
                       linewidths=1.6, zorder=5)


def render_compare_png(antes_pontos, agora_pontos,
                       data_antes: str = "", data_agora: str = "") -> bytes:
    """Dois bonecos lado a lado: primeira × última avaliação postural."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 5.2))
    for ax, pontos, titulo in ((ax1, antes_pontos, f"Antes · {data_antes}"),
                               (ax2, agora_pontos, f"Agora · {data_agora}")):
        _draw_body(ax)
        ax.set_title(titulo, fontsize=11, color="#334155")
        _draw_markers(ax, pontos, FRONT_POS)

    handles = [
        Line2D([], [], marker="o", ls="", ms=10, mfc="#22c55e", mec="white",
               label="Simétrico"),
        Line2D([], [], marker="o", ls="", ms=10, mfc="#f59e0b", mec="white",
               label="Assimetria leve"),
        Line2D([], [], marker="o", ls="", ms=10, mfc="#ef4444", mec="white",
               label="Assimetria a observar"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               fontsize=9)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=115, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def render_png(pontos: list, risco: dict | None = None) -> bytes:
    """Boneco frente + costas com os pontos coloridos. Retorna PNG bytes."""
    fig, (axf, axb) = plt.subplots(1, 2, figsize=(7.6, 5.4))
    _draw_body(axf)
    _draw_body(axb)
    axf.set_title("Frente", fontsize=11, color="#334155")
    axb.set_title("Costas", fontsize=11, color="#334155")

    count: dict[tuple, int] = {}
    for p in pontos:
        reg = p.get("regiao")
        for view, positions, ax in (("f", FRONT_POS, axf), ("b", BACK_POS, axb)):
            for (x, y) in positions.get(reg, []):
                key = (view, round(x, 2), round(y, 2))
                n = count[key] = count.get(key, 0) + 1
                yy = y + (n - 1) * 0.085          # empilha marcadores no mesmo lugar
                ax.scatter([x], [yy], s=200, c=p.get("cor", "#94a3b8"),
                           edgecolors="white", linewidths=1.6, zorder=5)

    handles = [
        Line2D([], [], marker="o", ls="", ms=10, mfc="#22c55e", mec="white",
               label="Ponto positivo"),
        Line2D([], [], marker="o", ls="", ms=10, mfc="#f59e0b", mec="white",
               label="Atenção / trabalhar"),
        Line2D([], [], marker="o", ls="", ms=10, mfc="#ef4444", mec="white",
               label="Atenção maior"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               fontsize=9)
    if risco:
        fig.suptitle(f"Risco de lesão: {risco.get('nivel', '—')}",
                     fontsize=12, fontweight="bold",
                     color=risco.get("cor", "#334155"))

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=115, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
