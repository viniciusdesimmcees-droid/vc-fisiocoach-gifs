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
    inteligencia: dict | None = None, golpe: dict | None = None,
    calibracao: dict | None = None, confianca: dict | None = None,
    captura: dict | None = None, benchmark: dict | None = None,
    radar_png: str | None = None,
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
    if golpe:
        gtxt = f"Golpe: {golpe.get('nome', '')}"
        if golpe.get("automatico"):
            gtxt += f" (auto · confianca {golpe.get('confianca_pct', 0)}%)"
        else:
            gtxt += " (selecionado)"
        fig.text(0.06, 0.915, gtxt, fontsize=9.5, color="#15803d", fontweight="bold")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.905, 0.905], color="#e6ece8", lw=1))

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
    peak_metric = (f"{peak:.0f} ± {confianca['margem_kmh']} km/h"
                   if confianca else f"{peak:.0f} km/h")
    metrics = [
        ("Velocidade de pico", peak_metric),
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

    # selo de confiança da medição (margem + nível)
    if confianca:
        ax_s = fig.add_axes([0.06, 0.450, 0.88, 0.035]); ax_s.axis("off")
        ax_s.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax_s.transAxes,
                                     facecolor="#f7faf8", edgecolor=confianca["cor"],
                                     linewidth=1.4))
        ax_s.text(0.02, 0.5, f"Confiança {confianca['nivel']}", fontsize=11,
                  fontweight="bold", color=confianca["cor"], va="center",
                  transform=ax_s.transAxes)
        ax_s.text(0.98, 0.5, f"{confianca['headline']}  (erro ~{confianca['erro_rel_pct']:.0f}%)",
                  fontsize=11, fontweight="bold", color="#0f1714", va="center",
                  ha="right", transform=ax_s.transAxes)

    # confiabilidade da calibração (cruzamento com a bola)
    if calibracao:
        cross = calibracao.get("cross")
        if calibracao.get("modo") == "ball":
            ctxt = (f"Calibracao automatica pela bola ({calibracao.get('ball_diameter_cm', 6.7)} cm) "
                    "— calibre tambem pela quadra para confirmar.")
            ccor = "#d97706"
        elif cross:
            ctxt = f"Calibração × bola: {cross['verdict']} (dif. {cross['abs_pct']:.0f}%)."
            ccor = cross["cor"]
        else:
            ctxt = None
        if ctxt:
            fig.text(0.06, 0.432, ctxt, fontsize=8.5, color=ccor, fontweight="bold")

    # qualidade da captura (pré-voo)
    if captura:
        aled = captura.get("n_graves", 0) + captura.get("n_avisos", 0)
        cap_txt = f"Qualidade da captura: {captura['nivel']} ({captura['nota']}/100)"
        if aled:
            probs = [i["nome"] for i in captura.get("itens", [])
                     if i["status"] in ("grave", "aviso")]
            cap_txt += " — atenção: " + ", ".join(probs[:3]) + "."
        else:
            cap_txt += " — dentro do protocolo."
        fig.text(0.06, 0.413, cap_txt, fontsize=8.5, color=captura["cor"],
                 fontweight="bold")

    # gráfico de velocidade
    if speed_png and os.path.exists(speed_png):
        import matplotlib.image as mpimg
        ax_p = fig.add_axes([0.06, 0.19, 0.88, 0.195]); ax_p.axis("off")
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
        if benchmark:
            fb = _benchmark_page(athlete, benchmark, radar_png)
            pdf.savefig(fb)
            plt.close(fb)
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


def _png_bytes_to_img(b):
    import io as _io

    import matplotlib.image as mpimg
    return mpimg.imread(_io.BytesIO(b), format="png")


def _info_boxes(fig, items, y0, x0=0.06, bw=0.42, bh=0.058, gap_x=0.46, gap_y=0.07):
    """Desenha caixinhas rótulo/valor em 2 colunas. Retorna o y final."""
    for i, (k, v) in enumerate(items):
        x = x0 + (i % 2) * gap_x
        y = y0 - (i // 2) * gap_y
        ax = fig.add_axes([x, y, bw, bh]); ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                                   facecolor="#f1f6f3", edgecolor="#e6ece8"))
        ax.text(0.05, 0.62, k, fontsize=8.5, color="#64748b", transform=ax.transAxes)
        ax.text(0.05, 0.20, str(v), fontsize=12.5, fontweight="bold", color="#0f1714",
                transform=ax.transAxes)
    rows = (len(items) + 1) // 2
    return y0 - rows * gap_y


def _load_img(p):
    import matplotlib.image as mpimg
    return mpimg.imread(p)


def write_athlete_dossier_pdf(path, athlete, profile, age, imc, stats,
                              serve_png=None, posture_png=None,
                              last_posture=None, last_posture_img=None,
                              golpe=None, inteligencia=None,
                              all_serves=None, posture_first_img=None,
                              posturas=None, objetivo=None,
                              bodymap_png=None, pontos_corpo=None,
                              comp=None, compare_png=None) -> None:
    """Laudo completo do atleta: ficha + saque + golpe + postura (com fotos) +
    plano + histórico completo + objetivo para o atleta."""
    profile = profile or {}
    with PdfPages(path) as pdf:
        # ---------------- Página 1: ficha + saque ----------------
        fig = plt.figure(figsize=(8.27, 11.69))
        _page_header(fig, athlete, "Laudo Consolidado do Atleta")

        fig.text(0.06, 0.895, "Ficha do atleta", fontsize=12, fontweight="bold",
                 color="#15803d")
        info = [
            ("Idade", f"{age} anos" if age is not None else "—"),
            ("Altura", f"{int(profile['height_cm'])} cm" if profile.get("height_cm") else "—"),
            ("IMC", imc if imc is not None else "—"),
            ("Mão dominante", (profile.get("dominant_hand") or "—").capitalize()),
            ("Nível", profile.get("level") or "—"),
            ("Treino", f"{profile['train_hours']} h/sem" if profile.get("train_hours") else "—"),
        ]
        y = _info_boxes(fig, info, 0.825)

        # texto clínico (lesões / dores / objetivos)
        clin = []
        if profile.get("injuries"):
            clin.append(f"Lesões: {profile['injuries']}")
        if profile.get("pain"):
            clin.append(f"Dores atuais: {profile['pain']}")
        if profile.get("goals"):
            clin.append(f"Objetivos: {profile['goals']}")
        if clin:
            ax = fig.add_axes([0.06, y - 0.04, 0.88, 0.05]); ax.axis("off")
            ax.text(0, 1, "\n".join(clin), fontsize=9, color="#334155", va="top",
                    transform=ax.transAxes, wrap=True, linespacing=1.5)
            y -= 0.07

        # resumo do saque
        fig.text(0.06, y, "Evolução do saque", fontsize=12, fontweight="bold",
                 color="#15803d")
        if golpe:
            gtxt = f"Último golpe reconhecido: {golpe.get('nome', '')}"
            if golpe.get("automatico"):
                gtxt += f" (auto · {golpe.get('confianca_pct', 0)}%)"
            fig.text(0.94, y, gtxt, fontsize=9.5, color="#334155", ha="right")
        y -= 0.012
        if stats:
            srv = [
                ("Recorde", f"{stats.get('best', 0):.0f} km/h"),
                ("Média", f"{stats.get('avg', 0):.0f} km/h"),
                ("Último", f"{stats.get('last', 0):.0f} km/h"),
                ("Evolução", f"{'+' if stats.get('delta', 0) >= 0 else ''}"
                 f"{stats.get('delta', 0):.0f} km/h ({stats.get('delta_pct', 0):+.0f}%)"),
            ]
            y = _info_boxes(fig, srv, y - 0.07)
        else:
            fig.text(0.06, y - 0.03, "Sem análises de saque registradas.",
                     fontsize=9.5, color="#64748b")
            y -= 0.05

        if serve_png:
            ax_p = fig.add_axes([0.06, max(0.10, y - 0.30), 0.88, 0.28]); ax_p.axis("off")
            ax_p.imshow(_png_bytes_to_img(serve_png))

        _signature(fig)
        pdf.savefig(fig)
        plt.close(fig)

        # ---------------- Página 2: postura ----------------
        if posture_png or last_posture:
            fig2 = plt.figure(figsize=(8.27, 11.69))
            _page_header(fig2, athlete, "Laudo Consolidado — Avaliação Postural")

            if posture_png:
                fig2.text(0.06, 0.895, "Evolução postural", fontsize=12,
                          fontweight="bold", color="#15803d")
                ax_e = fig2.add_axes([0.06, 0.62, 0.88, 0.26]); ax_e.axis("off")
                ax_e.imshow(_png_bytes_to_img(posture_png))

            # comparativo primeira × última foto (permanentes, do banco)
            if posture_first_img and os.path.exists(posture_first_img) and \
                    last_posture_img and os.path.exists(last_posture_img) and \
                    posture_first_img != last_posture_img:
                fig2.text(0.06, 0.58, "Comparativo: primeira × última avaliação",
                          fontsize=12, fontweight="bold", color="#15803d")
                for j, imgp in enumerate((posture_first_img, last_posture_img)):
                    img = _load_img(imgp)
                    ih, iw = img.shape[:2]
                    bw = 0.40
                    bh = min(0.30, bw * (ih / iw) * (8.27 / 11.69))
                    ax_c = fig2.add_axes([0.06 + j * 0.46, 0.55 - bh, bw, bh])
                    ax_c.axis("off"); ax_c.imshow(img)
                    fig2.text(0.06 + j * 0.46 + bw / 2, 0.55 - bh - 0.015,
                              "Primeira" if j == 0 else "Última", fontsize=9,
                              color="#64748b", ha="center")
                last_posture = None  # medidas já cobertas; evita sobrepor

            if last_posture:
                view_lbl = {"frente": "frontal", "costas": "posterior",
                            "lado": "lateral", "lateral": "lateral"}.get(
                    last_posture.get("view"), "")
                data = (last_posture.get("created_at") or "")[:10]
                fig2.text(0.06, 0.58, f"Última avaliação ({view_lbl} · {data})",
                          fontsize=12, fontweight="bold", color="#15803d")

                # imagem anotada à esquerda
                x_tab = 0.06
                if last_posture_img and os.path.exists(last_posture_img):
                    img = _load_img(last_posture_img)
                    ih, iw = img.shape[:2]
                    box_w = 0.30
                    box_h = min(0.40, box_w * (ih / iw) * (8.27 / 11.69))
                    ax_i = fig2.add_axes([0.06, 0.55 - box_h, box_w, box_h])
                    ax_i.axis("off"); ax_i.imshow(img)
                    x_tab = 0.42

                y2 = 0.54
                for m in last_posture.get("medidas", []):
                    fig2.text(x_tab, y2, m.get("nome", ""), fontsize=10,
                              fontweight="bold", color="#0f1714")
                    fig2.text(x_tab, y2 - 0.016,
                              f"{m.get('valor', '')} · {m.get('situacao', '')}",
                              fontsize=9, fontweight="bold",
                              color=_situacao_cor(m.get("situacao")))
                    fig2.add_artist(plt.Line2D([x_tab, 0.94], [y2 - 0.026, y2 - 0.026],
                                               color="#eef2f0", lw=0.8))
                    y2 -= 0.042

            ax_n = fig2.add_axes([0.06, 0.10, 0.88, 0.05]); ax_n.axis("off")
            ax_n.text(0, 1, "Triagem postural por geometria 2D (tem margem). Apoio a "
                      "avaliacao do profissional, nao substitui avaliacao presencial "
                      "nem diagnostico medico.", fontsize=8, color="#94a3b8",
                      va="top", transform=ax_n.transAxes, wrap=True, linespacing=1.4)
            _signature(fig2)
            pdf.savefig(fig2)
            plt.close(fig2)

        # ---------------- Página: comparativo postural (antes × agora) ----------------
        if compare_png and comp:
            figc = plt.figure(figsize=(8.27, 11.69))
            _page_header(figc, athlete, "Comparativo Postural — Antes × Agora")
            ax_c = figc.add_axes([0.08, 0.46, 0.84, 0.43]); ax_c.axis("off")
            ax_c.imshow(_png_bytes_to_img(compare_png))

            y = 0.435
            figc.text(0.06, y, "O que mudou", fontsize=12, fontweight="bold",
                      color="#15803d")
            y -= 0.020
            figc.text(0.06, y, comp.get("resumo", ""), fontsize=9.5,
                      fontweight="bold", color="#334155")
            y -= 0.028
            for d in comp.get("deltas", [])[:10]:
                figc.text(0.07, y, d.get("nome", ""), fontsize=9.5,
                          fontweight="bold", color="#0f1714")
                figc.text(0.50, y, f"{d.get('antes', '')} → {d.get('agora', '')}",
                          fontsize=9, color="#334155")
                figc.text(0.94, y, d.get("verdito", ""), fontsize=9,
                          fontweight="bold", color=d.get("cor", "#334155"),
                          ha="right")
                figc.add_artist(plt.Line2D([0.06, 0.94], [y - 0.010, y - 0.010],
                                           color="#eef2f0", lw=0.8))
                y -= 0.026

            ax_n = figc.add_axes([0.06, 0.09, 0.88, 0.04]); ax_n.axis("off")
            ax_n.text(0, 1, "Comparacao medida a medida entre a primeira e a ultima "
                      "avaliacao postural. Quanto menor o angulo de assimetria, "
                      "melhor. Versao 3D interativa disponivel no aplicativo.",
                      fontsize=8, color="#94a3b8", va="top",
                      transform=ax_n.transAxes, wrap=True, linespacing=1.4)
            _signature(figc)
            pdf.savefig(figc)
            plt.close(figc)

        # ---------------- Página: mapa corporal (boneco) ----------------
        if bodymap_png:
            figm = plt.figure(figsize=(8.27, 11.69))
            _page_header(figm, athlete, "Mapa Corporal do Aluno")
            ax_m = figm.add_axes([0.08, 0.42, 0.84, 0.47]); ax_m.axis("off")
            ax_m.imshow(_png_bytes_to_img(bodymap_png))

            y = 0.395
            figm.text(0.06, y, "Pontos marcados no corpo", fontsize=12,
                      fontweight="bold", color="#15803d")
            y -= 0.024
            for p in (pontos_corpo or [])[:12]:
                figm.text(0.07, y, "•", fontsize=11, fontweight="bold",
                          color=p.get("cor", "#334155"))
                figm.text(0.09, y, f"{p.get('titulo', '')} — {p.get('texto', '')}"[:105],
                          fontsize=8.6, color="#334155")
                y -= 0.019

            ax_n = figm.add_axes([0.06, 0.09, 0.88, 0.04]); ax_n.axis("off")
            ax_n.text(0, 1, "O boneco é um esquema ilustrativo do corpo; os pontos e "
                      "textos vem das avaliacoes reais do aluno (postura e plano "
                      "inteligente). Versao interativa 3D disponivel no aplicativo.",
                      fontsize=8, color="#94a3b8", va="top",
                      transform=ax_n.transAxes, wrap=True, linespacing=1.4)
            _signature(figm)
            pdf.savefig(figm)
            plt.close(figm)

        # ---------------- Página 3: plano inteligente ----------------
        if inteligencia:
            fig3 = _engine_page(athlete, inteligencia)
            pdf.savefig(fig3)
            plt.close(fig3)

        # ---------------- Página 4: histórico completo + objetivo ----------------
        if all_serves or posturas or objetivo:
            fig4 = plt.figure(figsize=(8.27, 11.69))
            _page_header(fig4, athlete, "Histórico Completo e Objetivo")
            y = 0.90

            if objetivo:
                fig4.text(0.06, y, "Objetivo para o atleta", fontsize=12,
                          fontweight="bold", color="#15803d")
                ax_o = fig4.add_axes([0.06, y - 0.10, 0.88, 0.09]); ax_o.axis("off")
                ax_o.text(0, 1, objetivo, fontsize=10, color="#334155", va="top",
                          transform=ax_o.transAxes, wrap=True, linespacing=1.5)
                y -= 0.14

            if all_serves:
                fig4.text(0.06, y, f"Todos os saques analisados ({len(all_serves)})",
                          fontsize=12, fontweight="bold", color="#15803d")
                y -= 0.008
                fig4.text(0.06, y - 0.016, "Cada linha mostra a data, a velocidade de "
                          "pico e a classificação — do primeiro ao mais recente.",
                          fontsize=8.3, color="#64748b")
                y -= 0.034
                for a in all_serves[-14:]:
                    d = a.get("data", "")
                    dbr = f"{d[8:10]}/{d[5:7]}/{d[0:4]}" if len(d) >= 10 else d
                    fig4.text(0.07, y, dbr, fontsize=9, color="#334155")
                    fig4.text(0.40, y, f"{(a.get('peak') or 0):.0f} km/h", fontsize=9,
                              fontweight="bold", color="#0f1714")
                    fig4.text(0.62, y, a.get("nivel", ""), fontsize=9, color="#64748b")
                    y -= 0.0185
                y -= 0.015

            if posturas:
                fig4.text(0.06, y, f"Todas as avaliações posturais ({len(posturas)})",
                          fontsize=12, fontweight="bold", color="#15803d")
                y -= 0.028
                for p in posturas[-10:]:
                    d = (p.get("created_at") or "")[:10]
                    dbr = f"{d[8:10]}/{d[5:7]}/{d[0:4]}" if len(d) >= 10 else d
                    flag = ("atenção" if p.get("graves") else
                            ("leve" if p.get("alertas") else "simétrico"))
                    fig4.text(0.07, y, dbr, fontsize=9, color="#334155")
                    fig4.text(0.40, y, p.get("view_label", ""), fontsize=9, color="#0f1714")
                    fig4.text(0.62, y, f"{p.get('alertas', 0)} alerta(s) · {flag}",
                              fontsize=9, color="#64748b")
                    y -= 0.0185

            ax_n = fig4.add_axes([0.06, 0.08, 0.88, 0.05]); ax_n.axis("off")
            ax_n.text(0, 1, "Laudo gerado pelo VF Tênis Scanner com todo o histórico do "
                      "atleta. Cada seção traz a explicação e o objetivo correspondente.",
                      fontsize=8, color="#94a3b8", va="top", transform=ax_n.transAxes,
                      wrap=True, linespacing=1.4)
            _signature(fig4)
            pdf.savefig(fig4)
            plt.close(fig4)


def write_manual_pdf(path: str, secoes: list, versao: str = "1.0") -> None:
    """Manual do Operador em PDF: capa + seções com paginação automática."""
    import re
    import textwrap
    from datetime import date

    # remove emojis (a fonte do PDF não os tem; a versão web mantém)
    _emoji = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")

    def _limpo(s):
        return _emoji.sub("", s).replace("  ", " ").strip()

    with PdfPages(path) as pdf:
        # ---- capa ----
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.patch.set_facecolor("white")
        logo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "static", "logo.png")
        if os.path.exists(logo):
            import matplotlib.image as mpimg
            ax_l = fig.add_axes([0.38, 0.66, 0.24, 0.17]); ax_l.axis("off")
            ax_l.imshow(mpimg.imread(logo))
        fig.text(0.5, 0.58, "VF Tênis Scanner", fontsize=30, fontweight="bold",
                 color="#15803d", ha="center")
        fig.text(0.5, 0.535, "Manual do Operador", fontsize=18,
                 color="#334155", ha="center")
        fig.text(0.5, 0.49, f"Versão {versao} · {date.today().strftime('%d/%m/%Y')}",
                 fontsize=11, color="#64748b", ha="center")
        fig.text(0.5, 0.42, "Guia completo de uso para professores e avaliadores:",
                 fontsize=10.5, color="#334155", ha="center")
        fig.text(0.5, 0.395, "captura, análise do saque, postura, boneco 3D, "
                 "laudos, exportação e confiabilidade.",
                 fontsize=10.5, color="#334155", ha="center")
        _signature(fig)
        pdf.savefig(fig)
        plt.close(fig)

        # ---- seções com fluxo/paginção ----
        def nova_pagina():
            f = plt.figure(figsize=(8.27, 11.69))
            _page_header(f, "Manual do Operador", "VF Tênis Scanner — guia de uso")
            return f, 0.885

        fig, y = nova_pagina()
        for sec in secoes:
            # quebra de página se o título não couber com pelo menos 2 linhas
            if y < 0.20:
                _signature(fig); pdf.savefig(fig); plt.close(fig)
                fig, y = nova_pagina()
            fig.text(0.06, y, sec["titulo"], fontsize=12.5, fontweight="bold",
                     color="#15803d")
            y -= 0.026
            for item in sec["itens"]:
                linhas = textwrap.wrap(_limpo(item), width=98)
                alt = 0.0165 * len(linhas) + 0.007
                if y - alt < 0.13:
                    _signature(fig); pdf.savefig(fig); plt.close(fig)
                    fig, y = nova_pagina()
                    fig.text(0.06, y, sec["titulo"] + " (cont.)", fontsize=11,
                             fontweight="bold", color="#15803d")
                    y -= 0.024
                fig.text(0.065, y, "•", fontsize=10, color="#15803d")
                for li, ln in enumerate(linhas):
                    fig.text(0.085, y - li * 0.0155, ln, fontsize=9,
                             color="#334155")
                y -= alt
            y -= 0.014
        _signature(fig)
        pdf.savefig(fig)
        plt.close(fig)


def write_analysis_pdf(path: str, row: dict, percurso_png: bytes | None = None) -> None:
    """Relatório completo de UMA análise já feita, reconstruído do banco:
    velocidade + golpe + percurso + plano inteligente + biomecânica."""
    athlete = row.get("athlete", "Atleta")
    peak = float(row.get("peak_kmh") or 0)
    cls = classify(peak)
    d = (row.get("created_at") or "")[:10]
    data_br = f"{d[8:10]}/{d[5:7]}/{d[0:4]}" if len(d) >= 10 else d
    golpe = row.get("stroke")

    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        _page_header(fig, athlete, f"Relatório do Saque — {data_br}")

        if golpe:
            gtxt = f"Golpe: {golpe.get('nome', '')}"
            if golpe.get("automatico"):
                gtxt += f" (auto · confianca {golpe.get('confianca_pct', 0)}%)"
            fig.text(0.06, 0.895, gtxt, fontsize=10, fontweight="bold",
                     color="#15803d")

        # velocímetro + classificação
        ax_g = fig.add_axes([0.08, 0.60, 0.5, 0.26])
        draw_gauge(ax_g, peak, cls)
        fig.text(0.62, 0.80, f"Classificação: {cls['nivel']}", fontsize=12,
                 fontweight="bold", color=cls["cor"])
        fig.text(0.62, 0.775, cls["faixa"], fontsize=10, color="#64748b")
        ax_d = fig.add_axes([0.62, 0.63, 0.32, 0.12]); ax_d.axis("off")
        ax_d.text(0, 1, cls["descricao"], fontsize=9.5, color="#64748b",
                  va="top", wrap=True, transform=ax_d.transAxes)

        _info_boxes(fig, [
            ("Velocidade de pico", f"{peak:.0f} km/h"),
            ("Velocidade média", f"{(row.get('mean_kmh') or 0):.0f} km/h"),
            ("Captura", f"{(row.get('fps') or 0):.0f} fps · detector {row.get('detector', '—')}"),
            ("Data da análise", data_br),
        ], 0.52)

        # percurso da bola (prova visual do que foi medido)
        if percurso_png:
            fig.text(0.06, 0.40, "Percurso da bola rastreado", fontsize=12,
                     fontweight="bold", color="#15803d")
            ax_p = fig.add_axes([0.08, 0.13, 0.84, 0.26]); ax_p.axis("off")
            ax_p.imshow(_png_bytes_to_img(percurso_png))

        _signature(fig)
        pdf.savefig(fig)
        plt.close(fig)

        if row.get("intel"):
            fi = _engine_page(athlete, row["intel"])
            pdf.savefig(fi)
            plt.close(fi)
        if row.get("biomech"):
            fb = _biomech_page(athlete, row["biomech"], None)
            pdf.savefig(fb)
            plt.close(fb)


def _situacao_cor(sit):
    s = (sit or "").lower()
    if "leve" in s:
        return "#d97706"
    if "observar" in s or "atenç" in s or "atenc" in s:
        return "#dc2626"
    return "#15803d"


def write_spec_pdf(path: str, spec: list, drops: list, ref_speeds, metodologia: list) -> None:
    """Ficha Técnica de Acurácia (selo de validação científica)."""
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, "Selo de Validação Científica", "Ficha Técnica de Acurácia")

    y = 0.89
    fig.text(0.06, y, "Acurácia esperada", fontsize=12, fontweight="bold",
             color="#15803d")
    y -= 0.028
    fig.text(0.06, y, "Erro = √(fps² + calibração² + rastreio²). Estimativa de "
             "engenharia, não certificação de laboratório.", fontsize=8.5,
             color="#64748b")
    y -= 0.022
    for s in spec:
        fig.text(0.06, y, s["nome"], fontsize=10.5, fontweight="bold", color="#0f1714")
        fig.text(0.94, y, f"± {s['erro_pct']}%", fontsize=10.5, fontweight="bold",
                 color="#15803d", ha="right")
        fig.text(0.06, y - 0.016, s["cond"], fontsize=8.2, color="#64748b")
        margens = "   ".join(f"{v} km/h → ±{s['margens'][v]}" for v in ref_speeds)
        fig.text(0.06, y - 0.030, margens, fontsize=8.5, color="#334155")
        fig.add_artist(plt.Line2D([0.06, 0.94], [y - 0.040, y - 0.040],
                                  color="#eef2f0", lw=0.8))
        y -= 0.058

    # autoteste por queda livre
    y -= 0.01
    fig.text(0.06, y, "Autoteste por queda livre (verificável)", fontsize=12,
             fontweight="bold", color="#15803d")
    y -= 0.024
    fig.text(0.06, y, "Solte uma bola de uma altura H; pela física a velocidade no "
             "impacto é v = √(2·g·H), g = 9,81 m/s². Filme, meça e compare.",
             fontsize=9, color="#334155")
    y -= 0.026
    cols = "    ".join(f"{d['altura_m']}m={d['v_kmh']}km/h" for d in drops)
    fig.text(0.06, y, cols, fontsize=9, fontweight="bold", color="#0f1714")
    y -= 0.03

    # metodologia
    fig.text(0.06, y, "Metodologia e limites", fontsize=12, fontweight="bold",
             color="#15803d")
    y -= 0.022
    for titulo, texto in metodologia:
        fig.text(0.06, y, titulo, fontsize=10, fontweight="bold", color="#0f1714")
        ax = fig.add_axes([0.06, y - 0.052, 0.88, 0.05]); ax.axis("off")
        ax.text(0, 1, texto, fontsize=8.3, color="#334155", va="top",
                transform=ax.transAxes, wrap=True, linespacing=1.35)
        y -= 0.075

    _signature(fig)
    with PdfPages(path) as pdf:
        pdf.savefig(fig)
        plt.close(fig)


def write_posture_pdf(path: str, athlete: str, resultado: dict, annot_png: str) -> None:
    """Laudo PDF da avaliação postural (1 página): imagem anotada + medidas."""
    import matplotlib.image as mpimg

    view_lbl = {"frente": "Vista frontal", "costas": "Vista posterior",
                "lado": "Vista lateral", "lateral": "Vista lateral"}.get(
        resultado.get("view"), "Avaliação")
    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, athlete, f"Avaliação Postural — {view_lbl}")

    # imagem anotada à esquerda
    if annot_png and os.path.exists(annot_png):
        img = mpimg.imread(annot_png)
        ih, iw = img.shape[:2]
        aspect = ih / iw
        box_w = 0.34
        box_h = min(0.62, box_w * aspect * (8.27 / 11.69))
        ax_i = fig.add_axes([0.06, 0.88 - box_h, box_w, box_h]); ax_i.axis("off")
        ax_i.imshow(img)

    # medidas à direita
    x = 0.46
    y = 0.86
    for m in resultado.get("medidas", []):
        fig.text(x, y, m["nome"], fontsize=10.5, fontweight="bold", color="#0f1714")
        fig.text(x, y - 0.016, f"{m['valor']} · {m['situacao']}", fontsize=9.5,
                 fontweight="bold", color=m["cor"])
        fig.text(x, y - 0.030, m.get("detalhe", ""), fontsize=8.3, color="#334155")
        fig.text(x, y - 0.043, m.get("para", ""), fontsize=7.6, color="#94a3b8")
        fig.add_artist(plt.Line2D([x, 0.94], [y - 0.052, y - 0.052],
                                  color="#eef2f0", lw=0.8))
        y -= 0.072

    # resumo
    fig.text(0.06, 0.30, "Resumo", fontsize=12, fontweight="bold", color="#15803d")
    ax_r = fig.add_axes([0.06, 0.22, 0.88, 0.07]); ax_r.axis("off")
    ax_r.text(0, 1, resultado.get("resumo", ""), fontsize=10, color="#334155",
              va="top", transform=ax_r.transAxes, wrap=True, linespacing=1.5)

    ax_n = fig.add_axes([0.06, 0.12, 0.88, 0.06]); ax_n.axis("off")
    ax_n.text(0, 1, "Triagem por geometria 2D a partir da pose: tem margem e "
              "depende do enquadramento (atleta ereto, corpo inteiro, de frente/"
              "costas/lado). Apoio a avaliacao do profissional, nao substitui "
              "avaliacao postural presencial nem diagnostico medico.",
              fontsize=8, color="#94a3b8", va="top", transform=ax_n.transAxes,
              wrap=True, linespacing=1.4)
    _signature(fig)

    with PdfPages(path) as pdf:
        pdf.savefig(fig)
        plt.close(fig)


def _benchmark_page(athlete: str, bench: dict, radar_png: str | None):
    """Página: benchmark vs. profissional (radar + níveis + o que falta)."""
    import matplotlib.image as mpimg

    fig = plt.figure(figsize=(8.27, 11.69))
    _page_header(fig, athlete, "Benchmark vs. Profissional")

    # índice de nível
    ax_b = fig.add_axes([0.06, 0.85, 0.88, 0.05]); ax_b.axis("off")
    ax_b.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax_b.transAxes,
                                 facecolor=bench["cor"], edgecolor="none"))
    ax_b.text(0.02, 0.5, f"Índice de nível: {bench['indice']}/100", fontsize=12,
              color="white", va="center", transform=ax_b.transAxes)
    ax_b.text(0.98, 0.5, bench["nivel"], fontsize=15, fontweight="bold",
              color="white", va="center", ha="right", transform=ax_b.transAxes)

    y = 0.82
    # radar à esquerda (se houver)
    x_tab = 0.06
    if radar_png and os.path.exists(radar_png):
        img = mpimg.imread(radar_png)
        ih, iw = img.shape[:2]
        bw = 0.42
        bh = bw * (ih / iw) * (8.27 / 11.69)
        ax_i = fig.add_axes([0.05, 0.55, bw, min(0.30, bh)]); ax_i.axis("off")
        ax_i.imshow(img)
        x_tab = 0.50

    fig.text(x_tab, y, "Métrica × nível", fontsize=11, fontweight="bold",
             color="#15803d")
    y -= 0.026
    for m in bench["metricas"]:
        fig.text(x_tab, y, m["nome"], fontsize=8.8, fontweight="bold", color="#0f1714")
        fig.text(x_tab, y - 0.014, f"{m['valor']} · {m['nivel']} · {m['percentil']}% "
                 "rumo ao pro", fontsize=7.8, color="#64748b")
        y -= 0.034

    # o que falta
    if bench.get("faltam"):
        y2 = 0.50
        fig.text(0.06, y2, "O que falta para o nível profissional", fontsize=12,
                 fontweight="bold", color="#15803d")
        y2 -= 0.026
        for m in bench["faltam"]:
            fig.text(0.07, y2, f"{m['short']}: {m['gap']}", fontsize=9.5,
                     fontweight="bold", color="#0f1714")
            ax = fig.add_axes([0.07, y2 - 0.030, 0.87, 0.024]); ax.axis("off")
            ax.text(0, 1, m["dica"], fontsize=8.3, color="#334155", va="top",
                    transform=ax.transAxes, wrap=True)
            y2 -= 0.050

    ax_n = fig.add_axes([0.06, 0.10, 0.88, 0.05]); ax_n.axis("off")
    ax_n.text(0, 1, "Faixas aproximadas da literatura de biomecanica do tenis e de "
              "medicoes tipicas por nivel de jogo. Metricas 2D tem margem. Guia de "
              "desenvolvimento e metas, nao avaliacao oficial de ranking.",
              fontsize=8, color="#94a3b8", va="top", transform=ax_n.transAxes,
              wrap=True, linespacing=1.4)
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
