"""Detector de bola por deep learning (YOLOv8 / Ultralytics).

A bola de tênis cai na classe COCO 32 = "sports ball", que os modelos YOLOv8
pré-treinados já detectam — então NÃO é preciso treinar nada para começar. Para
máxima robustez em quadra (bola pequena e veloz), o caminho de produção é fazer
fine-tuning com um dataset de bola de tênis e apontar `--model` para esses pesos.

Cumpre a mesma interface do detector clássico (`candidates(frame)`), então é
intercambiável em `tracking.associate` e no `analyze.py` via `--detector dl`.

Importação preguiçosa: o módulo só exige `ultralytics`/`torch` quando o detector
DL é realmente instanciado, de modo que o detector clássico funciona sem essas
dependências pesadas instaladas.
"""

from __future__ import annotations

import numpy as np

from tracking import Detection

# Classe COCO da "sports ball".
SPORTS_BALL_CLASS = 32


class DLBallDetector:
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf: float = 0.10,
        classes: tuple[int, ...] = (SPORTS_BALL_CLASS,),
        imgsz: int = 1280,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as e:  # mensagem acionável
            raise ImportError(
                "Detector DL requer 'ultralytics' e 'torch'. Instale com:\n"
                "  pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                "  pip install ultralytics"
            ) from e

        self.model = YOLO(model_path)
        self.conf = conf
        # Algumas versões esperam lista; normalizamos.
        self.classes = list(classes)
        self.imgsz = imgsz

    def candidates(self, frame: np.ndarray) -> list[Detection]:
        # conf baixo + imgsz alto: a bola é pequena e rápida; preferimos recall
        # alto aqui e deixamos a associação temporal descartar falsos positivos.
        results = self.model.predict(
            frame,
            conf=self.conf,
            classes=self.classes,
            imgsz=self.imgsz,
            verbose=False,
        )
        out: list[Detection] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                radius = max(x2 - x1, y2 - y1) / 2.0
                score = float(box.conf[0]) if box.conf is not None else 1.0
                out.append(
                    Detection(frame=-1, x=cx, y=cy, radius=radius, score=score)
                )
        return out

    def track(
        self, video_path: str, max_jump_px: float = 180.0, max_gap: int = 6
    ) -> tuple[list[Detection], dict]:
        from tracking import associate

        return associate(video_path, self, max_jump_px=max_jump_px, max_gap=max_gap)
