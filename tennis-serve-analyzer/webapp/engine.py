"""Motor inteligente VF: cruza biomecânica + anamnese para gerar
índice de risco de lesão, músculos a trabalhar e exercícios recomendados
(da biblioteca VC Fisiocoach).

Tudo é um sistema de regras transparente (mostra os fatores) — é apoio à
decisão do profissional, NÃO diagnóstico médico.
"""

from __future__ import annotations

import json
import os
import unicodedata

_LIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exercicios.json")

# carrega a biblioteca uma vez, indexada por grupo muscular
_BY_GROUP: dict[str, list] = {}
try:
    with open(_LIB_PATH, encoding="utf-8") as _f:
        for _ex in json.load(_f):
            _BY_GROUP.setdefault(_ex.get("grupo_muscular_principal", ""), []).append(_ex)
except Exception:
    _BY_GROUP = {}


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower()


def _g(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _pick(grupo: str, n: int = 2, max_dif: int = 3) -> list[dict]:
    """Escolhe n exercícios de um grupo, preferindo menor dificuldade e
    equipamento acessível."""
    cands = _BY_GROUP.get(grupo, [])
    if not cands:
        return []
    pref_eq = {"peso_corporal", "halteres"}
    ranked = sorted(
        cands,
        key=lambda e: (e.get("dificuldade", 3) > max_dif,
                       e.get("equipamento") not in pref_eq,
                       e.get("dificuldade", 3)),
    )
    return [{"nome": e["nome"], "grupo": grupo, "gif_url": e.get("gif_url"),
             "passos": e.get("passos") or [], "beneficio": e.get("beneficio"),
             "evitar": e.get("evitar")}
            for e in ranked[:n]]


def evaluate(summary: dict, biomech: dict | None, profile: dict | None) -> dict:
    profile = profile or {}
    pain = _norm(profile.get("pain"))
    injuries = _norm(profile.get("injuries"))
    texto_clinico = pain + " " + injuries

    score = 0
    fatores: list[str] = []
    musculos: list[dict] = []  # {grupo, motivo}
    seen_groups: set[str] = set()

    def add_musc(grupo: str, motivo: str):
        if grupo in _BY_GROUP and grupo not in seen_groups:
            musculos.append({"grupo": grupo, "motivo": motivo})
            seen_groups.add(grupo)

    # ---- déficits biomecânicos -> músculos ----
    joelho_load = _g(biomech, "angulos_no_loading", "joelho")
    if joelho_load is not None and joelho_load > 150:
        add_musc("quadriceps", "Pouca flexão de joelhos — fortalecer a impulsão das pernas.")
        add_musc("gluteos", "Potência do salto e do empurrão das pernas no saque.")

    cotovelo = _g(biomech, "angulos_no_contato", "cotovelo")
    if cotovelo is not None and cotovelo < 150:
        add_musc("triceps", "Melhorar a extensão do braço no impacto.")

    av_ombro = _g(biomech, "metricas_avancadas", "velocidades_angulares_max", "ombro")
    if av_ombro is not None and av_ombro < 800:
        add_musc("ombros", "Ganhar velocidade e potência do braço no saque.")

    tronco = _g(biomech, "angulos_no_contato", "inclinacao_tronco")
    if tronco is not None and tronco > 35:
        add_musc("abdomen", "Estabilizar o core e proteger a lombar (tronco muito inclinado).")
        add_musc("posterior", "Cadeia posterior / sustentação lombar.")

    xf = _g(biomech, "metricas_avancadas", "x_factor", "separacao_max_graus")
    if (xf is not None and xf < 30) or not _g(biomech, "cadeia_cinetica", "proximal_para_distal"):
        add_musc("abdomen", "Rotação do tronco (oblíquos) e transferência de força.")

    # ---- risco a partir da biomecânica ----
    for f in (_g(biomech, "metricas_avancadas", "indicadores_risco") or []):
        if f.get("nivel") == "atenção":
            score += 2
            fatores.append(f.get("texto", ""))

    # ---- anamnese -> risco + músculos específicos ----
    if injuries.strip():
        score += 2
        fatores.append("Histórico de lesão informado na ficha.")
    if pain.strip():
        score += 3
        fatores.append(f"Dor atual relatada: {profile.get('pain')}.")

    if "ombro" in texto_clinico:
        add_musc("ombros", "Fortalecer o manguito rotador (queixa no ombro).")
    if "cotovel" in texto_clinico or "epicond" in texto_clinico:
        add_musc("antebraco", "Prevenção de epicondilite (queixa no cotovelo).")
    if any(k in texto_clinico for k in ("lombar", "coluna", "costas")):
        add_musc("posterior", "Estabilização lombar (queixa nas costas).")
        add_musc("abdomen", "Core para proteger a coluna.")
    if "joelho" in texto_clinico:
        add_musc("quadriceps", "Estabilidade do joelho (queixa no joelho).")

    # carga e idade
    try:
        th = float(profile.get("train_hours") or 0)
        if th >= 15:
            score += 1
            fatores.append(f"Carga de treino alta ({th:.0f} h/semana).")
    except (TypeError, ValueError):
        pass

    # ---- complemento: condicionamento geral ----
    add_musc("full_body", "Condicionamento geral e prevenção.")

    # nível de risco
    if score <= 2:
        nivel, cor = "Baixo", "#15803d"
    elif score <= 5:
        nivel, cor = "Moderado", "#d97706"
    else:
        nivel, cor = "Alto", "#dc2626"
    if not profile:
        fatores.append("Cadastre a anamnese do atleta para um índice de risco mais preciso.")

    # exercícios recomendados (prioriza os 4 primeiros grupos)
    exercicios = []
    for m in musculos[:4]:
        exercicios.extend(_pick(m["grupo"], n=2))

    # foco de treino
    if musculos:
        focos = ", ".join(m["grupo"] for m in musculos[:3])
        treino = (f"Prioridade desta fase: {focos}. Combine força específica desses "
                  "grupos com técnica do gesto e mobilidade. 2–3 sessões/semana, "
                  "respeitando dor e recuperação.")
    else:
        treino = "Mantenha um programa equilibrado de força e mobilidade."

    return {
        "risco": {"nivel": nivel, "cor": cor, "score": score, "fatores": fatores},
        "musculos": musculos,
        "exercicios": exercicios,
        "treino": treino,
    }
