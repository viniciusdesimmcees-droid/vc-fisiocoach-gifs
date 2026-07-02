"""Boneco 3D do aluno: traduz a avaliação em PONTOS no corpo.

Usa apenas dados persistidos no banco:
  - última avaliação postural (medidas com situação) -> pontos verdes (simétrico)
    ou âmbar/vermelho (assimetrias), na região correspondente do corpo;
  - plano inteligente mais recente (músculos a priorizar) -> pontos âmbar
    "trabalhar", com o motivo;
  - risco de lesão -> selo geral do boneco.

As posições 3D de cada região ficam no template (three.js). Aqui só mapeamos
avaliação -> região + status + explicação. Honestidade: o boneco é um avatar
ilustrativo do corpo (não uma reconstrução 3D do aluno); os pontos e textos
vêm 100% das avaliações reais.
"""

from __future__ import annotations

# medida postural (chave) -> região do boneco
POSTURE_REGION = {
    "ombros": "ombros",
    "cabeca": "cabeca",
    "cabeca_ant": "cabeca",
    "pelvis": "pelvis",
    "tronco": "tronco",
    "tronco_sag": "tronco",
    "joelhos": "joelhos",
}

# grupo muscular (motor inteligente) -> região; "@dom" usa o lado dominante
MUSCLE_REGION = {
    "quadriceps": "coxas",
    "gluteos": "gluteos",
    "posterior": "lombar",
    "abdomen": "abdomen",
    "costas": "costas",
    "trapezio": "trapezio",
    "peito": "peito",
    "ombros": "ombro@dom",
    "triceps": "braco@dom",
    "biceps": "braco@dom",
    "antebraco": "antebraco@dom",
    "panturrilha": "panturrilhas",
}

STATUS = {
    "ok": {"cor": "#22c55e", "rotulo": "Ponto positivo"},
    "atencao": {"cor": "#f59e0b", "rotulo": "Atenção leve"},
    "grave": {"cor": "#ef4444", "rotulo": "Atenção maior"},
    "trabalhar": {"cor": "#f59e0b", "rotulo": "Músculo a trabalhar"},
}


def _situacao_status(situacao: str) -> str:
    s = (situacao or "").lower()
    if "leve" in s:
        return "atencao"
    if "observar" in s or "atenç" in s or "atenc" in s:
        return "grave"
    return "ok"


def _dom_side(profile) -> str:
    hand = ((profile or {}).get("dominant_hand") or "").lower()
    return "esq" if hand.startswith("e") else "dir"


def build(profile, posturas, intel) -> tuple[list[dict], dict | None]:
    """Retorna (pontos, risco). Cada ponto: regiao, status, cor, rotulo,
    titulo, texto, origem."""
    dom = _dom_side(profile)
    pontos: list[dict] = []

    # ---- última avaliação postural ----
    ultima = posturas[-1] if posturas else None
    if ultima:
        d = (ultima.get("created_at") or "")[:10]
        data_br = f"{d[8:10]}/{d[5:7]}/{d[0:4]}" if len(d) >= 10 else d
        origem = f"Avaliação postural ({data_br})"
        for m in ultima.get("medidas", []):
            regiao = POSTURE_REGION.get(m.get("chave"))
            if not regiao:
                continue
            st = _situacao_status(m.get("situacao"))
            pontos.append({
                "regiao": regiao,
                "status": st,
                "cor": STATUS[st]["cor"],
                "rotulo": STATUS[st]["rotulo"],
                "titulo": m.get("nome", ""),
                "texto": f"{m.get('valor', '')} · {m.get('situacao', '')}",
                "origem": origem,
            })

    # ---- músculos a trabalhar (plano inteligente) ----
    if intel:
        for m in intel.get("musculos", []):
            reg = MUSCLE_REGION.get(m.get("grupo"))
            if not reg:
                continue
            regiao = reg.replace("@dom", f"_{dom}")
            pontos.append({
                "regiao": regiao,
                "status": "trabalhar",
                "cor": STATUS["trabalhar"]["cor"],
                "rotulo": STATUS["trabalhar"]["rotulo"],
                "titulo": m.get("grupo", "").replace("_", " ").title(),
                "texto": m.get("motivo", ""),
                "origem": "Plano inteligente (última análise)",
            })

    risco = (intel or {}).get("risco") or None
    return pontos, risco


def _data_br(iso: str) -> str:
    d = (iso or "")[:10]
    return f"{d[8:10]}/{d[5:7]}/{d[0:4]}" if len(d) >= 10 else d


def build_from_assessment(assess: dict) -> list[dict]:
    """Pontos posturais de UMA avaliação específica (para o comparativo)."""
    pontos = []
    origem = f"Avaliação postural ({_data_br(assess.get('created_at'))})"
    for m in assess.get("medidas", []):
        regiao = POSTURE_REGION.get(m.get("chave"))
        if not regiao:
            continue
        st = _situacao_status(m.get("situacao"))
        pontos.append({
            "regiao": regiao, "status": st, "cor": STATUS[st]["cor"],
            "rotulo": STATUS[st]["rotulo"], "titulo": m.get("nome", ""),
            "texto": f"{m.get('valor', '')} · {m.get('situacao', '')}",
            "origem": origem,
        })
    return pontos


VIEW_LABEL = {"frente": "Frontal", "costas": "Posterior",
              "lado": "Lateral", "lateral": "Lateral"}


def _view(a) -> str:
    v = (a.get("view") or "frente").lower()
    return "lateral" if v in ("lado", "lateral") else v


def photo_pairs(posturas: list) -> list[dict]:
    """Pares de fotos primeira × última DA MESMA VISTA (frontal com frontal,
    lateral com lateral…). Vistas diferentes nunca são comparadas entre si."""
    by: dict[str, list] = {}
    for p in posturas:
        if p.get("tem_imagem"):
            by.setdefault(_view(p), []).append(p)
    pares = []
    for v, lst in by.items():
        if len(lst) >= 2 and lst[0]["id"] != lst[-1]["id"]:
            pares.append({
                "view": v,
                "view_label": VIEW_LABEL.get(v, v.title()),
                "antes": {"id": lst[0]["id"],
                          "data": _data_br(lst[0].get("created_at"))},
                "agora": {"id": lst[-1]["id"],
                          "data": _data_br(lst[-1].get("created_at"))},
                "mesmo_dia": (lst[0].get("created_at") or "")[:10]
                             == (lst[-1].get("created_at") or "")[:10],
            })
    ordem = {"frente": 0, "costas": 1, "lateral": 2}
    pares.sort(key=lambda x: ordem.get(x["view"], 9))
    return pares


def compare(posturas: list) -> dict | None:
    """Compara primeira × última avaliação POR VISTA (frontal com frontal,
    lateral com lateral…). Retorna pontos antes/agora da vista principal e os
    deltas de todas as vistas com par."""
    if not posturas or len(posturas) < 2:
        return None

    by: dict[str, list] = {}
    for p in posturas:
        by.setdefault(_view(p), []).append(p)
    com_par = {v: lst for v, lst in by.items()
               if len(lst) >= 2 and lst[0]["id"] != lst[-1]["id"]}
    if not com_par:
        return None

    def _by_chave(a):
        return {m.get("chave"): m for m in a.get("medidas", []) if m.get("chave")}

    deltas = []
    mesmo_dia = True
    for v, lst in com_par.items():
        antes, agora = lst[0], lst[-1]
        if (antes.get("created_at") or "")[:10] != (agora.get("created_at") or "")[:10]:
            mesmo_dia = False
        rotulo_v = VIEW_LABEL.get(v, v.title())
        m_antes, m_agora = _by_chave(antes), _by_chave(agora)
        for chave, ma in m_agora.items():
            mb = m_antes.get(chave)
            if not mb or ma.get("graus") is None or mb.get("graus") is None:
                continue
            d = abs(float(ma["graus"])) - abs(float(mb["graus"]))
            if d <= -1.0:
                verd, ic, cor = f"melhorou {abs(d):.1f}°", "✅", "#15803d"
            elif d >= 1.0:
                verd, ic, cor = f"aumentou {d:.1f}°", "⚠️", "#d97706"
            else:
                verd, ic, cor = "estável", "➖", "#64748b"
            deltas.append({
                "nome": f"{ma.get('nome', chave)} ({rotulo_v})",
                "antes": mb.get("valor", ""), "agora": ma.get("valor", ""),
                "delta": round(d, 1), "verdito": verd, "icone": ic, "cor": cor,
            })
    deltas.sort(key=lambda x: x["delta"])  # melhoras primeiro

    # vista principal para os bonecos 3D / mapa: frontal, senão a primeira com par
    ordem = {"frente": 0, "costas": 1, "lateral": 2}
    vp = sorted(com_par, key=lambda v: ordem.get(v, 9))[0]
    antes_p, agora_p = com_par[vp][0], com_par[vp][-1]

    n_mel = sum(1 for x in deltas if x["delta"] <= -1.0)
    n_pio = sum(1 for x in deltas if x["delta"] >= 1.0)
    if n_mel and not n_pio:
        resumo = f"Evolução positiva: {n_mel} medida(s) melhoraram desde a primeira avaliação."
    elif n_mel or n_pio:
        resumo = f"{n_mel} medida(s) melhoraram e {n_pio} pioraram — ajuste o foco do treino."
    else:
        resumo = "Postura estável entre as avaliações."
    if mesmo_dia:
        resumo += " Atenção: as avaliações comparadas são do MESMO dia — faça uma nova sessão para acompanhar a evolução real."

    return {
        "antes": {"pontos": build_from_assessment(antes_p),
                  "data": _data_br(antes_p.get("created_at"))},
        "agora": {"pontos": build_from_assessment(agora_p),
                  "data": _data_br(agora_p.get("created_at"))},
        "vista_label": VIEW_LABEL.get(vp, vp.title()),
        "deltas": deltas,
        "resumo": resumo,
        "mesmo_dia": mesmo_dia,
    }


def sessions(posturas: list) -> list[dict]:
    """Agrupa as avaliações por DIA (sessão), mais recentes primeiro."""
    by_day: dict[str, list] = {}
    for p in posturas:
        by_day.setdefault((p.get("created_at") or "")[:10], []).append(p)
    out = []
    for dia in sorted(by_day, reverse=True):
        itens = list(reversed(by_day[dia]))
        vistas = []
        for p in itens:
            lbl = VIEW_LABEL.get(_view(p), "")
            if lbl and lbl not in vistas:
                vistas.append(lbl)
        out.append({"data": _data_br(dia), "dia": dia, "itens": itens,
                    "vistas": " · ".join(vistas)})
    return out
