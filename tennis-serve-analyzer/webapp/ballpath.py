"""Imagem do PERCURSO DA BOLA — o 'print' do caminho que o scanner rastreou.

Desenha a trajetória detectada (x, y por quadro), colorida pela ordem dos
quadros, marcando o início e o quadro de impacto. É uma prova visual do que o
sistema mediu, guardada no banco e incluída no livro de dados do atleta.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CRED = "Sistema criado e desenvolvido por Vinícius Camargos da Fonseca."


def trajectory_png(trajectory, meta: dict, result) -> bytes | None:
    """Gera o PNG do percurso da bola. Retorna bytes ou None se não houver dados."""
    pts = [d for d in trajectory if getattr(d, "x", None) is not None]
    if len(pts) < 3:
        return None
    xs = [d.x for d in pts]
    ys = [d.y for d in pts]
    n = len(pts)

    scale = meta.get("scale", 1.0) or 1.0
    w = (meta.get("width", 0) or 0) * scale
    h = (meta.get("height", 0) or 0) * scale

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(xs, ys, "-", color="#94a3b8", lw=1.2, alpha=0.6, zorder=1)
    sc = ax.scatter(xs, ys, c=range(n), cmap="viridis", s=22, zorder=2)

    # início
    ax.scatter([xs[0]], [ys[0]], c="#15803d", s=90, marker="o",
               edgecolors="white", linewidths=1.5, label="Início", zorder=5)
    # impacto
    impact = getattr(result, "impact_frame", None)
    if impact is not None:
        for d in pts:
            if d.frame == impact:
                ax.scatter([d.x], [d.y], c="#dc2626", s=140, marker="X",
                           edgecolors="white", linewidths=1.5, label="Impacto", zorder=6)
                break

    ax.set_xlim(0, w if w > 1 else max(xs) * 1.1)
    ax.set_ylim(h if h > 1 else max(ys) * 1.1, 0)  # y invertido (coords de imagem)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("Percurso da bola rastreado pelo scanner", fontsize=12)
    ax.set_xlabel("x (pixels)", fontsize=9)
    ax.set_ylabel("y (pixels)", fontsize=9)
    peak = getattr(result, "peak_kmh", 0) or 0
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)
    fig.text(0.5, 0.01, f"Pico {peak:.0f} km/h · {n} pontos rastreados · {CRED}",
             ha="center", fontsize=7, color="#9aa39c")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
