"""Detector clássico de bola (cor + movimento), sem rede neural.

Estratégia (roda em qualquer máquina, sem GPU):
  1. Subtração de fundo (MOG2) para isolar o que se move.
  2. Filtro de cor HSV para o amarelo-esverdeado típico da bola.
  3. Detecção de blobs circulares por contorno (área + circularidade).

A associação quadro-a-quadro fica em `tracking.associate`. Este módulo só
fornece os CANDIDATOS de cada quadro, expondo `candidates(frame)`. O detector
por deep learning (`detector_dl.py`) cumpre a mesma interface e é intercambiável.
"""

from __future__ import annotations

import cv2
import numpy as np

from tracking import Detection, associate

# Faixa HSV para a bola amarelo-esverdeada. Ajustável conforme iluminação.
DEFAULT_HSV_LOW = (25, 60, 60)
DEFAULT_HSV_HIGH = (65, 255, 255)


class BallTracker:
    def __init__(
        self,
        hsv_low: tuple[int, int, int] = DEFAULT_HSV_LOW,
        hsv_high: tuple[int, int, int] = DEFAULT_HSV_HIGH,
        min_radius: float = 4.0,
        max_radius: float = 40.0,
        min_circularity: float = 0.55,
        use_color: bool = True,
    ) -> None:
        self.hsv_low = np.array(hsv_low, dtype=np.uint8)
        self.hsv_high = np.array(hsv_high, dtype=np.uint8)
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.min_circularity = min_circularity
        self.use_color = use_color
        self._bg = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=25, detectShadows=False
        )

    def candidates(self, frame: np.ndarray) -> list[Detection]:
        motion = self._bg.apply(frame)
        motion = cv2.medianBlur(motion, 3)

        if self.use_color:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            color = cv2.inRange(hsv, self.hsv_low, self.hsv_high)
            mask = cv2.bitwise_and(motion, color)
            # Se a interseção ficar vazia (iluminação ruim), recai no movimento.
            if cv2.countNonZero(mask) == 0:
                mask = motion
        else:
            mask = motion

        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        out: list[Detection] = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 3:
                continue
            (cx, cy), r = cv2.minEnclosingCircle(c)
            if not (self.min_radius <= r <= self.max_radius):
                continue
            circularity = area / (np.pi * r * r + 1e-6)
            if circularity < self.min_circularity:
                continue
            out.append(
                Detection(frame=-1, x=float(cx), y=float(cy), radius=float(r))
            )
        return out

    def track(
        self, video_path: str, max_jump_px: float = 180.0, max_gap: int = 6
    ) -> tuple[list[Detection], dict]:
        return associate(video_path, self, max_jump_px=max_jump_px, max_gap=max_gap)
