"""Referências científicas: compara cada dado do atleta com faixas de referência
da literatura de biomecânica do tênis e diz se está dentro/abaixo/atenção.

IMPORTANTE (honestidade): as faixas são aproximadas, da literatura, e algumas
métricas são estimativas 2D (têm margem). Servem como GUIA educativo e de
acompanhamento — não substituem avaliação presencial nem diagnóstico médico.
"""

from __future__ import annotations


def _g(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


# Cada referência: nome, unidade, direção (maior/menor = melhor), alvo, texto da
# faixa, "para que serve", e como extrair o valor do atleta.
REFS = [
    {"nome": "Velocidade de pico", "unid": "km/h", "dir": "maior", "alvo": 160,
     "ref": "150–170 amador avançado · 170–200 competitivo · 200+ pro",
     "para": "Principal indicador de potência do saque.",
     "get": lambda s, b: _g(s, "resultado", "velocidade_pico_kmh")},
    {"nome": "Extensão do cotovelo no impacto", "unid": "°", "dir": "maior",
     "alvo": 150, "ref": "150–180° (braço quase reto)",
     "para": "Braço estendido no impacto = mais alcance e força, menos carga no ombro.",
     "get": lambda s, b: _g(b, "angulos_no_contato", "cotovelo")},
    {"nome": "Flexão de joelho no carregamento", "unid": "°", "dir": "menor",
     "alvo": 145, "ref": "≤145° (joelhos bem dobrados)",
     "para": "Dobrar os joelhos carrega as pernas para impulsionar o saque.",
     "get": lambda s, b: _g(b, "angulos_no_loading", "joelho")},
    {"nome": "Inclinação do tronco no impacto", "unid": "°", "dir": "menor",
     "alvo": 35, "ref": "≤35° (acima sobrecarrega a lombar)",
     "para": "Alguma inclinação é normal; em excesso vira risco lombar.",
     "get": lambda s, b: _g(b, "angulos_no_contato", "inclinacao_tronco")},
    {"nome": "X-Factor (separação ombro–quadril)", "unid": "°", "dir": "maior",
     "alvo": 30, "ref": "≥30° (estimativa 2D)",
     "para": "Mais rotação do tronco = mais energia elástica, como uma mola.",
     "get": lambda s, b: _g(b, "metricas_avancadas", "x_factor", "separacao_max_graus")},
    {"nome": "Velocidade angular do ombro", "unid": "°/s", "dir": "maior",
     "alvo": 800, "ref": "≥800 °/s (aprox.)",
     "para": "Quão rápido o ombro gira — explosão do movimento.",
     "get": lambda s, b: _g(b, "metricas_avancadas", "velocidades_angulares_max", "ombro")},
    {"nome": "Velocidade angular do cotovelo", "unid": "°/s", "dir": "maior",
     "alvo": 900, "ref": "≥900 °/s (aprox.)",
     "para": "Velocidade de extensão do braço na raquetada.",
     "get": lambda s, b: _g(b, "metricas_avancadas", "velocidades_angulares_max", "cotovelo")},
]


def compare(summary: dict, biomech: dict | None) -> list[dict]:
    """Retorna as linhas de comparação (só métricas com valor disponível)."""
    rows = []
    for r in REFS:
        v = r["get"](summary, biomech)
        if v is None:
            continue
        v = float(v)
        if r["dir"] == "maior":
            ok = v >= r["alvo"]
            sit, cor, ic = (("Dentro da faixa", "#15803d", "✅") if ok
                            else ("Abaixo do ideal", "#d97706", "⬇️"))
        else:
            ok = v <= r["alvo"]
            sit, cor, ic = (("Dentro da faixa", "#15803d", "✅") if ok
                            else ("Acima — atenção", "#d97706", "⚠️"))
        rows.append({
            "nome": r["nome"],
            "valor": f"{v:.0f} {r['unid']}",
            "ref": r["ref"],
            "situacao": sit,   # texto puro (PDF)
            "icone": ic,       # emoji só para a web
            "cor": cor,
            "para": r["para"],
        })
    return rows
