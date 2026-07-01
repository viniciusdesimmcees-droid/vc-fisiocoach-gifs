"""Registro central das métricas que o scanner lê/compara.

O operador pode MARCAR métricas para não participarem da leitura (página de
Configurações). O mesmo vocabulário de chaves é usado nas referências
científicas e no benchmark, para que a exclusão valha em tudo.
"""

from __future__ import annotations

METRIC_REGISTRY = [
    ("velocidade", "Velocidade de pico"),
    ("cotovelo", "Extensão do cotovelo no impacto"),
    ("joelho", "Flexão de joelho no carregamento"),
    ("tronco", "Inclinação do tronco no impacto"),
    ("xfactor", "X-Factor (separação ombro–quadril)"),
    ("av_ombro", "Velocidade angular do ombro"),
    ("av_cotovelo", "Velocidade angular do cotovelo"),
]

METRIC_NAMES = dict(METRIC_REGISTRY)
