"""Estimativa de pose do atleta (YOLOv8-pose / Ultralytics).

Extrai os 17 keypoints do esqueleto (padrão COCO) por quadro. Em um vídeo de
saque há um atleta; escolhemos a pessoa de maior confiança/área em cada quadro.

Saída: lista (por quadro) de arrays (17, 3) -> (x_px, y_px, confiança), ou None
quando nenhuma pessoa é detectada.

Importação preguiçosa de ultralytics/torch (igual ao detector_dl): a camada de
biomecânica em si (ângulos) é geometria pura e não depende de deep learning.
"""

from __future__ import annotations

import numpy as np

# Ordem dos keypoints COCO.
COCO_KEYPOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
KP = {name: i for i, name in enumerate(COCO_KEYPOINTS)}


class PoseEstimator:
    def __init__(self, model_path: str = "yolov8n-pose.pt") -> None:
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise ImportError(
                "Pose requer 'ultralytics' e 'torch'. Instale:\n"
                "  pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                "  pip install ultralytics"
            ) from e
        # Em CPU compartilhada (ex.: hospedagem pequena), o torch cria threads
        # demais e o processo trava/estoura o tempo. Limitar estabiliza.
        try:
            import os
            import torch

            n = int(os.environ.get("TORCH_THREADS", "2"))
            torch.set_num_threads(n)
        except Exception:
            pass
        self.model = YOLO(model_path)

    def _largest_person(self, result) -> np.ndarray | None:
        if result.keypoints is None or len(result.keypoints) == 0:
            return None
        kxy = result.keypoints.xy.cpu().numpy()  # (n, 17, 2)
        kconf = result.keypoints.conf
        kconf = (
            kconf.cpu().numpy()
            if kconf is not None
            else np.ones(kxy.shape[:2], dtype=np.float32)
        )
        # escolhe a pessoa com maior "extensão" (proxy de tamanho/proximidade)
        best_i, best_area = 0, -1.0
        for i in range(kxy.shape[0]):
            pts = kxy[i][kconf[i] > 0.3]
            if len(pts) < 2:
                continue
            area = np.ptp(pts[:, 0]) * np.ptp(pts[:, 1])
            if area > best_area:
                best_area, best_i = area, i
        kp = np.concatenate([kxy[best_i], kconf[best_i][:, None]], axis=1)  # (17,3)
        return kp.astype(np.float32)

    def estimate_frame(self, frame: np.ndarray) -> np.ndarray | None:
        res = self.model.predict(frame, verbose=False)[0]
        return self._largest_person(res)

    def estimate_video(
        self, video_path: str, max_width: int | None = None,
        max_frames: int | None = None,
    ) -> tuple[list, dict]:
        """Estima a pose quadro a quadro.

        `max_width` reduz a resolução (ângulos não mudam com a escala, então
        acelera sem perder precisão). `max_frames` limita o total processado
        (pose em CPU é pesada). Retorna a lista de keypoints por quadro + meta.
        """
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Não foi possível abrir o vídeo: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        scale = 1.0
        if max_width and width > max_width:
            scale = max_width / width

        frames: list = []
        idx = -1
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            idx += 1
            if max_frames and idx >= max_frames:
                break
            if scale != 1.0:
                frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
            frames.append(self.estimate_frame(frame))
        cap.release()

        detected = sum(1 for f in frames if f is not None)
        meta = {
            "fps": fps, "width": width, "height": height,
            "frames": len(frames), "pose_detected": detected, "scale": scale,
        }
        return frames, meta
