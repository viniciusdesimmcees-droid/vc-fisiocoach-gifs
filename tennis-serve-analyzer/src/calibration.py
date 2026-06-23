"""Conversão pixel -> metro a partir de um objeto de referência.

Para estimar velocidade absoluta precisamos saber quantos metros vale cada
pixel. Isso exige um objeto de referência de tamanho conhecido no plano de
movimento da bola (ex.: a altura da rede = 0,914 m no centro, a fita de uma
linha, um bastão de calibração posicionado no plano do saque).

Limitação importante (honestidade técnica): a escala é válida apenas no plano
da referência. Se a bola se move muito mais perto/longe da câmera do que a
referência, há erro de perspectiva. Para o protótipo assumimos câmera lateral
com a bola viajando aproximadamente no mesmo plano da referência.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Calibration:
    """Escala métrica derivada de um objeto de referência.

    meters_per_pixel: quantos metros corresponde 1 pixel no plano de referência.
    fps: quadros por segundo do vídeo (idealmente slow-motion: 120/240).
    """

    meters_per_pixel: float
    fps: float

    @classmethod
    def from_reference(
        cls, reference_length_m: float, reference_length_px: float, fps: float
    ) -> "Calibration":
        if reference_length_m <= 0 or reference_length_px <= 0:
            raise ValueError("Comprimento de referência deve ser positivo.")
        if fps <= 0:
            raise ValueError("fps deve ser positivo.")
        return cls(meters_per_pixel=reference_length_m / reference_length_px, fps=fps)

    @classmethod
    def from_two_points(
        cls,
        p1: tuple[float, float],
        p2: tuple[float, float],
        reference_length_m: float,
        fps: float,
    ) -> "Calibration":
        """Calibra a partir de dois pontos clicados no quadro e a distância real
        entre eles (em metros)."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length_px = (dx * dx + dy * dy) ** 0.5
        return cls.from_reference(reference_length_m, length_px, fps)

    def px_to_m(self, pixels: float) -> float:
        return pixels * self.meters_per_pixel
