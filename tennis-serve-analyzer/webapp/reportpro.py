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

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png")
ASSINATURA = "Vinícius Camargos da Fonseca"
RESPONSAVEL = "Responsável técnico · VF Tênis Scanner™"


def _signature(fig) -> None:
    """Selo de assinatura/marca registrada no rodapé de cada página do laudo."""
    # selo (logo) à direita
    try:
        import matplotlib.image as mpimg
        ax_logo = fig.add_axes([0.82, 0.016, 0.12, 0.058]); ax_logo.axis("off")
        ax_logo.imshow(mpimg.imread(LOGO_PATH))
    except Exception:
        pass
    # linha + assinatura à esquerda
    fig.add_artist(plt.Line2D([0.06, 0.40], [0.064, 0.064], color="#94a3b8", lw=1))
    fig.text(0.06, 0.044, ASSINATURA, fontsize=14, fontfamily="serif",
             fontstyle="italic", color="#15803d")
    fig.text(0.06, 0.027, RESPONSAVEL, fontsize=8.5, color="#64748b")
    fig.text(0.5, 0.009, CREDIT, ha="center", fontsize=7.5, color="#aab4ad")

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
    biomech: dict | None = None, biomech_png: str | None = None,
    evalu: dict | None = None, didatico_texto: str | None = None,
    referencias: list | None = None, glossario: list | None = None,
    inteligencia: dict | None = None,
) -> None:
    """Monta um relatório PDF A4 profissional (1 página; 2 se houver biomecânica)."""
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

    # coluna direita: NOTA TÉCNICA (destaque) + classificação
    if evalu:
        fig.text(0.60, 0.87, "Nota técnica", fontsize=11, color="#64748b")
        fig.text(0.60, 0.80, f"{evalu['score']:.0f}", fontsize=40,
                 fontweight="bold", color=evalu["cor"])
        fig.text(0.745, 0.812, "/100", fontsize=14, color="#94a3b8")
        fig.text(0.60, 0.785, evalu["nivel"], fontsize=12, fontweight="bold",
                 color=evalu["cor"])
    fig.text(0.60, 0.74, f"Classificação: {cls['nivel']} · {cls['faixa']}",
             fontsize=10, color="#334155")
    ax_desc = fig.add_axes([0.60, 0.63, 0.34, 0.09]); ax_desc.axis("off")
    ax_desc.text(0, 1, cls["descricao"], fontsize=9.5, color="#64748b", va="top",
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

    # Em palavras simples (para o aluno) — ou recomendações se não houver
    if didatico_texto:
        fig.text(0.06, 0.165, "Em palavras simples (para o aluno)", fontsize=12,
                 fontweight="bold", color="#15803d")
        ax_e = fig.add_axes([0.06, 0.085, 0.88, 0.07]); ax_e.axis("off")
        ax_e.text(0, 1, didatico_texto, fontsize=10, color="#334155", va="top",
                  transform=ax_e.transAxes, linespacing=1.6, wrap=True)
    else:
        fig.text(0.06, 0.165, "Recomendações para evoluir", fontsize=12,
                 fontweight="bold", color="#15803d")
        recs = (evalu or {}).get("recomendacoes", [])[:4]
        rec_txt = "\n".join(f"• {t}" for t in recs) if recs else \
            "Mantenha a consistência e a regularidade do saque."
        ax_e = fig.add_axes([0.06, 0.09, 0.88, 0.065]); ax_e.axis("off")
        ax_e.text(0, 1, rec_txt, fontsize=9.5, color="#334155", va="top",
                  transform=ax_e.transAxes, linespacing=1.6, wrap=True)

    _signature(fig)

    with PdfPages(path) as pdf:
        pdf.savefig(fig)
        plt.close(fig)
        if biomech:
            fig2 = _biomech_page(athlete, biomech, biomech_png)
            pdf.savefig(fig2)
            plt.close(fig2)
        if inteligencia:
            fi = _engine_page(athlete, inteligencia)
            pdf.savefig(fi)
            plt.close(fi)
        if referencias:
            fr = _references_table_page(athlete, referencias)
            pdf.savefig(fr)
            plt.close(fr)
        if glossario:
            fg = _glossary_page(athlete, glossario)
            pdf.savefig(fg)
            plt.close(fg)


def _page_header(fig, athlete: str, subtitulo: str) -> None:
    fig.patch.set_facecolor("white")
    fig.text(0.06, 0.955, "VF Tênis Scanner", fontsize=22, fontweight="bold",
             color="#15803d")
    fig.text(0.06, 0.935, subtitulo, fontsize=12, color="#334155")
    fig.text(0.94, 0.955, athlete, fontsize=13, fontweight="bold",
             color="#0f1714", ha="right")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.922, 0.922], color="#e6ece8", lw=1))


def _references_table_page(athlete: str, rows: list):
    """Página: seus dados × referência científica."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, athlete, "Seus dados × referência científica")

    y = 0.90
    fig.text(0.06, y, "Métrica", fontsize=8.5, color="#94a3b8")
    fig.text(0.45, y, "Seu valor", fontsize=8.5, color="#94a3b8")
    fig.text(0.60, y, "Referência", fontsize=8.5, color="#94a3b8")
    y -= 0.024
    for r in rows:
        fig.text(0.06, y, r["nome"], fontsize=9.5, color="#0f1714")
        fig.text(0.45, y, r["valor"], fontsize=9.5, fontweight="bold", color="#0f1714")
        fig.text(0.60, y, r["ref"], fontsize=8, color="#334155")
        fig.text(0.06, y - 0.018, r["situacao"], fontsize=8.5,
                 fontweight="bold", color=r["cor"])
        fig.text(0.30, y - 0.018, r["para"], fontsize=7.8, color="#64748b")
        fig.add_artist(plt.Line2D([0.06, 0.94], [y - 0.03, y - 0.03],
                                  color="#eef2f0", lw=0.8))
        y -= 0.052

    ax = fig.add_axes([0.06, y - 0.06, 0.88, 0.06]); ax.axis("off")
    ax.text(0, 1, "Faixas aproximadas da literatura de biomecânica do tênis. "
            "Algumas são estimativas 2D (têm margem). Use como guia educativo e de "
            "acompanhamento — não substitui avaliação presencial nem diagnóstico médico.",
            fontsize=8, color="#94a3b8", va="top", transform=ax.transAxes,
            wrap=True, linespacing=1.4)
    _signature(fig)
    return fig


def _glossary_page(athlete: str, glossario: list):
    """Página: glossário com explicações simples."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, athlete, "Glossário — o que cada termo significa")

    y = 0.89
    for termo, expl in glossario:
        fig.text(0.06, y, f"{termo}", fontsize=10.5, fontweight="bold",
                 color="#15803d")
        ax = fig.add_axes([0.06, y - 0.058, 0.88, 0.052]); ax.axis("off")
        ax.text(0, 1, expl, fontsize=9, color="#334155", va="top",
                transform=ax.transAxes, wrap=True, linespacing=1.35)
        y -= 0.075

    _signature(fig)
    return fig


def _engine_page(athlete: str, intel: dict):
    """Página: plano inteligente (risco de lesão + músculos + treino)."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, athlete, "Plano do atleta — Inteligência VF")

    risco = intel.get("risco", {}) or {}
    cor = risco.get("cor", "#334155")

    # banner de risco
    ax_b = fig.add_axes([0.06, 0.85, 0.88, 0.05]); ax_b.axis("off")
    ax_b.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax_b.transAxes,
                                 facecolor=cor, edgecolor="none"))
    ax_b.text(0.02, 0.5, "Indice de risco de lesao", fontsize=11, color="white",
              va="center", transform=ax_b.transAxes)
    ax_b.text(0.98, 0.5, risco.get("nivel", "—"), fontsize=16, fontweight="bold",
              color="white", va="center", ha="right", transform=ax_b.transAxes)

    y = 0.82
    fatores = risco.get("fatores", []) or []
    if fatores:
        fig.text(0.06, y, "Fatores considerados", fontsize=10.5,
                 fontweight="bold", color="#15803d")
        y -= 0.022
        for f in fatores[:8]:
            fig.text(0.07, y, f"- {f}", fontsize=8.8, color="#334155")
            y -= 0.02
        y -= 0.01

    musculos = intel.get("musculos", []) or []
    if musculos:
        fig.text(0.06, y, "Musculos a priorizar", fontsize=10.5,
                 fontweight="bold", color="#15803d")
        y -= 0.024
        for m in musculos:
            grupo = str(m.get("grupo", "")).replace("_", " ").title()
            fig.text(0.07, y, grupo, fontsize=9.5, fontweight="bold", color="#0f1714")
            fig.text(0.30, y, m.get("motivo", ""), fontsize=8.3, color="#64748b")
            y -= 0.026
        y -= 0.01

    exercicios = intel.get("exercicios", []) or []
    if exercicios:
        fig.text(0.06, y, "Exercicios recomendados (biblioteca VC Fisiocoach)",
                 fontsize=10.5, fontweight="bold", color="#15803d")
        y -= 0.024
        for e in exercicios:
            grupo = str(e.get("grupo", "")).replace("_", " ").title()
            fig.text(0.07, y, f"- {e.get('nome', '')}", fontsize=9.2, color="#0f1714")
            fig.text(0.62, y, grupo, fontsize=8.3, color="#94a3b8")
            y -= 0.022
        y -= 0.01

    treino = intel.get("treino")
    if treino:
        fig.text(0.06, y, "Foco do treino", fontsize=10.5, fontweight="bold",
                 color="#15803d")
        y -= 0.02
        ax_t = fig.add_axes([0.06, y - 0.08, 0.88, 0.08]); ax_t.axis("off")
        ax_t.text(0, 1, treino, fontsize=9, color="#334155", va="top",
                  transform=ax_t.transAxes, wrap=True, linespacing=1.4)

    ax_n = fig.add_axes([0.06, 0.10, 0.88, 0.05]); ax_n.axis("off")
    ax_n.text(0, 1, "Sistema de apoio a decisao do profissional, baseado em regras "
              "transparentes que cruzam a biomecanica do saque com a anamnese. "
              "Nao substitui avaliacao presencial nem diagnostico medico.",
              fontsize=8, color="#94a3b8", va="top", transform=ax_n.transAxes,
              wrap=True, linespacing=1.4)
    _signature(fig)
    return fig


def _biomech_page(athlete: str, b: dict, biomech_png: str | None):
    """Segunda página do PDF: biomecânica do gesto."""
    import matplotlib.image as mpimg

    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    fig.text(0.06, 0.955, "VF Tênis Scanner", fontsize=22, fontweight="bold",
             color="#15803d")
    fig.text(0.06, 0.935, "Relatório de Biomecânica do Saque", fontsize=12,
             color="#334155")
    fig.text(0.94, 0.955, athlete, fontsize=13, fontweight="bold",
             color="#0f1714", ha="right")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.922, 0.922], color="#e6ece8", lw=1))

    fases = b.get("fases", {})
    chain = b.get("cadeia_cinetica", {})
    ang = b.get("angulos_no_contato") or {}

    # blocos de informação
    info = [
        ("Lado dominante", str(b.get("lado_dominante", "—")).capitalize()),
        ("Quadro do contato", str(fases.get("contato", "—"))),
        ("Cadeia proximal→distal",
         "Eficiente" if chain.get("proximal_para_distal") else "Revisar"),
        ("Quadros com pose", str(b.get("captura", {}).get("quadros_com_pose", "—"))),
    ]
    for i, (k, v) in enumerate(info):
        x = 0.06 + (i % 2) * 0.46
        y = 0.85 - (i // 2) * 0.07
        ax = fig.add_axes([x, y, 0.42, 0.06]); ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                                   facecolor="#f1f6f3", edgecolor="#e6ece8"))
        ax.text(0.04, 0.62, k, fontsize=9, color="#64748b", transform=ax.transAxes)
        ax.text(0.04, 0.22, v, fontsize=13, fontweight="bold", color="#0f1714",
                transform=ax.transAxes)

    adv = b.get("metricas_avancadas", {}) or {}

    # ângulos no contato (coluna esquerda)
    fig.text(0.06, 0.76, "Ângulos no impacto", fontsize=12,
             fontweight="bold", color="#15803d")
    if ang:
        items = [(k.replace("_", " ").capitalize(), v) for k, v in ang.items()
                 if v is not None]
        txt = "\n".join(f"• {k}: {v}°" for k, v in items)
    else:
        txt = "Pose não detectada (filme o atleta de corpo inteiro, câmera " \
              "lateral, boa iluminação)."
    ax_a = fig.add_axes([0.06, 0.585, 0.42, 0.155]); ax_a.axis("off")
    ax_a.text(0, 1, txt, fontsize=10, color="#334155", va="top",
              transform=ax_a.transAxes, linespacing=1.7)

    # métricas avançadas (coluna direita)
    fig.text(0.52, 0.76, "Métricas avançadas", fontsize=12,
             fontweight="bold", color="#15803d")
    lines = []
    dur = adv.get("duracao_fases_ms", {}) or {}
    if dur.get("aceleracao_total"):
        lines.append(f"• Aceleração total: {dur['aceleracao_total']:.0f} ms")
    if dur.get("armada"):
        lines.append(f"• Armada → impacto: {dur['armada']:.0f} ms")
    av = adv.get("velocidades_angulares_max", {}) or {}
    if av.get("cotovelo"):
        lines.append(f"• Vel. angular cotovelo: {av['cotovelo']:.0f} °/s")
    if av.get("ombro"):
        lines.append(f"• Vel. angular ombro: {av['ombro']:.0f} °/s")
    xf = adv.get("x_factor", {}) or {}
    if xf.get("disponivel"):
        lines.append(f"• X-Factor (tronco): {xf['separacao_max_graus']:.0f}°")
    txt2 = "\n".join(lines) if lines else "Disponível com pose detectada."
    ax_b = fig.add_axes([0.52, 0.585, 0.42, 0.155]); ax_b.axis("off")
    ax_b.text(0, 1, txt2, fontsize=10, color="#334155", va="top",
              transform=ax_b.transAxes, linespacing=1.7)

    # gráfico de ângulos
    if biomech_png and os.path.exists(biomech_png):
        ax_p = fig.add_axes([0.06, 0.37, 0.88, 0.20]); ax_p.axis("off")
        ax_p.imshow(mpimg.imread(biomech_png))

    # indicadores de risco
    fig.text(0.06, 0.33, "Indicadores de risco (não é diagnóstico médico)",
             fontsize=12, fontweight="bold", color="#15803d")
    flags = adv.get("indicadores_risco", []) or []
    ftxt = "\n".join(f"• [{f.get('area')}] {f.get('texto')}" for f in flags) \
        or "Sem indicadores."
    ax_f = fig.add_axes([0.06, 0.21, 0.88, 0.11]); ax_f.axis("off")
    ax_f.text(0, 1, ftxt, fontsize=9.5, color="#334155", va="top",
              transform=ax_f.transAxes, linespacing=1.6, wrap=True)

    # explicação da cadeia cinética
    fig.text(0.06, 0.17, "Cadeia cinética (sequência proximal→distal)",
             fontsize=12, fontweight="bold", color="#15803d")
    expl = (
        "Num saque eficiente, a energia sobe do solo em sequência: pernas/quadril "
        "→ tronco → ombro → cotovelo/punho. Respeitar essa ordem (proximal → "
        "distal) transfere força de forma ótima e protege as articulações."
    )
    for note in chain.get("observacoes", []):
        expl += f"\n• {note}"
    ax_e = fig.add_axes([0.06, 0.10, 0.88, 0.07]); ax_e.axis("off")
    ax_e.text(0, 1, expl, fontsize=9, color="#334155", va="top",
              transform=ax_e.transAxes, linespacing=1.4, wrap=True)

    _signature(fig)
    return fig
