"""Saídas da análise biomecânica: gráfico de ângulos, JSON e vídeo com esqueleto."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from biomechanics import FrameAngles, Phases, KinematicChain
from pose_estimator import KP

# Conexões do esqueleto COCO para desenhar.
SKELETON = [
    ("left_shoulder", "right_shoulder"), ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"), ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"), ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"), ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
]


def write_angles_plot(path: str, angles: list[FrameAngles], phases: Phases,
                      fps: float, athlete: str) -> None:
    t = [a.frame / fps for a in angles]
    series = {
        "Cotovelo": [a.elbow for a in angles],
        "Ombro": [a.shoulder for a in angles],
        "Joelho": [a.knee for a in angles],
        "Quadril": [a.hip for a in angles],
    }
    fig, ax = plt.subplots(figsize=(9.5, 5))
    for name, ys in series.items():
        ax.plot(t, ys, "-", lw=1.5, label=name)
    for label, fr in (("loading", phases.loading), ("contato", phases.contact),
                      ("follow", phases.follow_through)):
        if fr is not None:
            ax.axvline(fr / fps, ls="--", lw=1, alpha=0.6, color="gray")
            ax.text(fr / fps, ax.get_ylim()[1], label, fontsize=8,
                    rotation=90, va="top", ha="right", color="gray")
    ax.set_xlabel("Tempo (s)")
    ax.set_ylabel("Ângulo articular (graus)")
    ax.set_title(f"Ângulos articulares no saque — {athlete}")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_summary_json(path: str, athlete: str, side: str, angles: list[FrameAngles],
                       phases: Phases, chain: KinematicChain, meta: dict) -> dict:
    def at(frame):
        if frame is None:
            return None
        for a in angles:
            if a.frame == frame:
                return {
                    "cotovelo": _r(a.elbow), "ombro": _r(a.shoulder),
                    "joelho": _r(a.knee), "quadril": _r(a.hip),
                    "inclinacao_tronco": _r(a.trunk_lean),
                }
        return None

    summary = {
        "atleta": athlete,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "lado_dominante": side,
        "captura": {
            "fps": meta.get("fps"), "quadros": meta.get("frames"),
            "quadros_com_pose": meta.get("pose_detected"),
        },
        "fases": {
            "loading": phases.loading, "cocking": phases.cocking,
            "contato": phases.contact, "follow_through": phases.follow_through,
        },
        "angulos_no_contato": at(phases.contact),
        "angulos_no_loading": at(phases.loading),
        "cadeia_cinetica": {
            "picos_velocidade_angular": chain.peak_frames,
            "proximal_para_distal": chain.proximal_to_distal,
            "observacoes": chain.notes,
        },
    }
    with open(path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def _r(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(v, 1)


def write_skeleton_video(in_path: str, out_path: str, frames: list,
                         phases: Phases) -> None:
    import cv2

    cap = cv2.VideoCapture(in_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    idx = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        kp = frames[idx] if idx < len(frames) else None
        if kp is not None:
            for a, b in SKELETON:
                pa, pb = kp[KP[a]], kp[KP[b]]
                if pa[2] > 0.3 and pb[2] > 0.3:
                    cv2.line(frame, (int(pa[0]), int(pa[1])),
                             (int(pb[0]), int(pb[1])), (0, 255, 0), 2)
            for i in range(17):
                if kp[i, 2] > 0.3:
                    cv2.circle(frame, (int(kp[i, 0]), int(kp[i, 1])), 3,
                               (0, 200, 255), -1)
        phase_label = {phases.loading: "LOADING", phases.contact: "CONTATO",
                       phases.follow_through: "FOLLOW"}.get(idx)
        if phase_label:
            cv2.putText(frame, phase_label, (16, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 0, 255), 3)
        out.write(frame)
    cap.release()
    out.release()
