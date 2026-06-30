"""Camada didática: traduz os dados técnicos para linguagem simples, para o
aluno entender. Gera um 'Resumo para o aluno', um glossário e um texto curto
para o PDF.
"""

from __future__ import annotations

REFERENCIA = ("Para comparar: iniciantes ficam perto de 100 km/h, amadores "
              "avançados entre 150 e 170, e profissionais passam de 200 km/h.")

GLOSSARIO_BASE = [
    ("Velocidade de pico",
     "A maior velocidade que a bola atingiu, logo depois da raquetada. É o "
     "número principal do saque."),
    ("Velocidade média", "A média da velocidade da bola no trecho medido."),
    ("Nota técnica",
     "Uma nota de 0 a 100 que junta a força (velocidade) com a qualidade do "
     "movimento. Quanto mais perto de 100, melhor a técnica."),
    ("fps (quadros por segundo)",
     "Quantas fotos por segundo a câmera tira. Câmera lenta (240 fps) é o que "
     "permite medir a bola com precisão."),
]

GLOSSARIO_BIO = [
    ("Cadeia cinética",
     "A ordem certa de usar o corpo no saque: primeiro as pernas, depois o "
     "tronco, o ombro e, por último, o braço — como um chicote que ganha "
     "velocidade na ponta."),
    ("X-Factor",
     "O quanto o seu tronco gira em relação ao quadril. É como esticar uma "
     "mola: quanto mais separa, mais energia o saque ganha."),
    ("Velocidade angular",
     "A rapidez com que uma articulação (ombro, cotovelo...) gira no saque."),
    ("Fases do saque",
     "As etapas do movimento: carregamento (dobrar os joelhos), armada (levar a "
     "raquete atrás), impacto (bater na bola) e finalização."),
]


def speed_context(peak: float) -> str:
    if peak < 120:
        return ("É um bom ponto de partida — usando mais as pernas e melhorando a "
                "técnica, a velocidade sobe bastante.")
    if peak < 150:
        return "É uma velocidade boa, de quem está evoluindo bem no jogo."
    if peak < 175:
        return "É um saque forte, de jogador competitivo."
    if peak < 200:
        return "É um saque de alto nível — muito bom!"
    return "É uma velocidade de elite, nível profissional!"


def student_summary(summary: dict, evalu: dict | None,
                    nivel: str | None = None) -> list[dict]:
    """Blocos em linguagem simples para a tela."""
    r = summary.get("resultado", {})
    peak = float(r.get("velocidade_pico_kmh", 0) or 0)

    blocks = []
    t = f"A sua bola saiu a {peak:.0f} km/h. {speed_context(peak)} {REFERENCIA}"
    if nivel:
        t += f" Isso coloca o seu saque no nível {nivel}."
    blocks.append({"icone": "⚡", "titulo": "A velocidade do seu saque", "texto": t})

    if evalu:
        blocks.append({
            "icone": "🏅", "titulo": "Sua nota técnica",
            "texto": f"Você tirou {evalu['score']:.0f} de 100. A nota mistura a "
                     "força do saque com a qualidade do movimento.",
        })
        rec = evalu.get("recomendacoes", [])
        if rec:
            blocks.append({
                "icone": "🎯", "titulo": "O que treinar primeiro", "texto": rec[0],
            })

    blocks.append({
        "icone": "💪", "titulo": "Próximo passo",
        "texto": "Refaça a medição daqui a algumas semanas — o app guarda tudo e "
                 "mostra a sua evolução no histórico.",
    })
    return blocks


def glossario(has_biomech: bool) -> list[tuple[str, str]]:
    return GLOSSARIO_BASE + (GLOSSARIO_BIO if has_biomech else [])


def plain_text(summary: dict, evalu: dict | None) -> str:
    """Texto curto em linguagem simples, para o rodapé do PDF (laudo do aluno)."""
    r = summary.get("resultado", {})
    peak = float(r.get("velocidade_pico_kmh", 0) or 0)
    parts = [f"A sua bola saiu a {peak:.0f} km/h. {speed_context(peak)}"]
    if evalu:
        parts.append(f"Sua nota técnica foi {evalu['score']:.0f}/100.")
        rec = evalu.get("recomendacoes", [])
        if rec:
            parts.append(f"Para melhorar agora: {rec[0]}")
    return " ".join(parts)
