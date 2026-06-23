"""Lógica de rastreio compartilhada (associação quadro-a-quadro).

O DETECTOR de candidatos é plugável: qualquer objeto com o método
`candidates(frame) -> list[Detection]` serve (tracker clássico por cor/movimento
ou detector por deep learning). Esta camada apenas associa as detecções ao longo
do tempo, formando a trajetória da bola.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2


@dataclass
class Detection:
    frame: int
    x: float  # centro em pixels
    y: float
    radius: float
    score: float = 1.0  # confiança (1.0 p/ detectores sem score)


class CandidateDetector(Protocol):
    """Interface que qualquer detector de bola deve cumprir."""

    def candidates(self, frame) -> list[Detection]:
        ...


def associate(
    video_path: str,
    detector: CandidateDetector,
    max_jump_px: float = 180.0,
    max_gap: int = 6,
) -> tuple[list[Detection], dict]:
    """Rastreia a bola: lê o vídeo, pede candidatos por quadro ao `detector` e
    encadeia as detecções por proximidade + consistência de tamanho.

    Retorna (trajetória ordenada por quadro, metadados).
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

        cands = detector.candidates(frame)
        for d in cands:
            d.frame = frame_idx

        if not cands:
            gap += 1
            if gap > max_gap:
                last = None
            continue

        if last is None:
            # Sem âncora: pega o candidato de maior confiança (e maior raio
            # como desempate) — tende a ser a bola.
            chosen = max(cands, key=lambda d: (d.score, d.radius))
        else:
            def dist(d: Detection) -> float:
                return ((d.x - last.x) ** 2 + (d.y - last.y) ** 2) ** 0.5

            def cost(d: Detection) -> float:
                # proximidade + penalidade por mudança de raio - bônus de confiança
                return dist(d) + 8.0 * abs(d.radius - last.radius) - 20.0 * d.score

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
