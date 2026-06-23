"""Detecção e rastreamento da bola de tênis em um vídeo.

Estratégia do protótipo (sem rede neural treinada, roda em qualquer máquina):
  1. Subtração de fundo (MOG2) para isolar o que se move.
  2. Filtro de cor HSV para o amarelo-esverdeado típico da bola.
  3. Detecção de blobs circulares por contorno (área + circularidade).
  4. Associação quadro-a-quadro pela proximidade (vizinho mais próximo),
     com tolerância a alguns quadros sem detecção (oclusão / blur).

Para produção, este módulo seria substituído por um detector treinado
(ex.: YOLO/TrackNet para bola de tênis), mantendo a mesma interface de saída.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Detection:
    frame: int
    x: float  # centro em pixels
    y: float
    radius: float


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

    def _candidates(self, frame: np.ndarray) -> list[Detection]:
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
            out.append(Detection(frame=-1, x=float(cx), y=float(cy), radius=float(r)))
        return out

    def track(
        self, video_path: str, max_jump_px: float = 180.0, max_gap: int = 6
    ) -> tuple[list[Detection], dict]:
        """Rastreia a bola ao longo do vídeo.

        Retorna a trajetória (lista de Detection ordenada por quadro) e um dict
        de metadados (fps, dimensões, total de quadros).
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Não foi possível abrir o vídeo: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        trajectory: list[Detection] = []
        last: Detection | None = None
        gap = 0
        frame_idx = -1

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_idx += 1

            cands = self._candidates(frame)
            for d in cands:
                d.frame = frame_idx

            if not cands:
                gap += 1
                if gap > max_gap:
                    last = None
                continue

            if last is None:
                # Pega o maior candidato (bola tende a ser blob consistente).
                chosen = max(cands, key=lambda d: d.radius)
            else:
                # Vizinho mais próximo, penalizando mudança brusca de raio
                # (rejeita blobs-fantasma de ruído com tamanho inconsistente).
                def dist(d: Detection) -> float:
                    return ((d.x - last.x) ** 2 + (d.y - last.y) ** 2) ** 0.5

                def cost(d: Detection) -> float:
                    return dist(d) + 8.0 * abs(d.radius - last.radius)

                chosen = min(cands, key=cost)
                if dist(chosen) > max_jump_px * (1 + gap):
                    gap += 1
                    if gap > max_gap:
                        last = None
                    continue

            trajectory.append(chosen)
            last = chosen
            gap = 0

        cap.release()
        meta = {
            "fps": fps,
            "width": width,
            "height": height,
            "frames": frame_idx + 1,
            "detections": len(trajectory),
        }
        return trajectory, meta
