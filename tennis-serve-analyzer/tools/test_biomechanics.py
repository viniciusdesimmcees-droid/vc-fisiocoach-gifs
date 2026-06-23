"""Testes determinísticos da biomecânica (geometria pura, sem deep learning).

Roda sem dependências pesadas:  python tools/test_biomechanics.py
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pose_estimator import KP, COCO_KEYPOINTS  # noqa: E402
from biomechanics import (  # noqa: E402
    angle_at, choose_serve_side, compute_angles, segment_phases,
    kinematic_sequence,
)

_fail = 0


def check(name: str, cond: bool) -> None:
    global _fail
    print(("  ok  " if cond else " FAIL ") + name)
    if not cond:
        _fail += 1


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def make_kp(coords: dict, conf: float = 1.0) -> np.ndarray:
    """Monta o array (17,3) preenchendo só os keypoints informados."""
    kp = np.zeros((17, 3), dtype=np.float32)
    for name, (x, y) in coords.items():
        kp[KP[name]] = (x, y, conf)
    return kp


print("angle_at:")
check("ângulo reto = 90", approx(angle_at((1, 0), (0, 0), (0, 1)), 90.0, 1e-4))
check("ângulo raso = 180", approx(angle_at((1, 0), (0, 0), (-1, 0)), 180.0, 1e-4))
check("ângulo nulo = 0", approx(angle_at((1, 0), (0, 0), (1, 0)), 0.0, 1e-4))
check("45 graus", approx(angle_at((1, 0), (0, 0), (1, 1)), 45.0, 1e-4))
check("vetor degenerado = nan", math.isnan(angle_at((0, 0), (0, 0), (1, 1))))

print("choose_serve_side:")
# braço direito sobe mais alto (y menor) -> lado direito dominante
f1 = make_kp({"left_wrist": (10, 100), "right_wrist": (50, 20)})
f2 = make_kp({"left_wrist": (10, 90), "right_wrist": (50, 30)})
check("lado direito", choose_serve_side([f1, f2]) == "right")
f3 = make_kp({"left_wrist": (10, 5), "right_wrist": (50, 60)})
check("lado esquerdo", choose_serve_side([f1, f2, f3]) == "left")

print("compute_angles (cotovelo):")
# ombro(0,0) cotovelo(0,10) punho(10,10) -> cotovelo a 90 graus
kp = make_kp({
    "right_shoulder": (0, 0), "right_elbow": (0, 10), "right_wrist": (10, 10),
    "right_hip": (0, 20), "right_knee": (0, 30), "right_ankle": (0, 40),
})
fa = compute_angles([kp], "right")[0]
check("cotovelo 90", approx(fa.elbow, 90.0, 1e-3))
check("joelho 180 (perna reta)", approx(fa.knee, 180.0, 1e-3))
check("wrist_y capturado", approx(fa.wrist_y, 10.0))

print("segment_phases:")
# punho desce (y sobe) até um mínimo de y (ponto alto) e volta a descer
frames = []
ys = [100, 80, 60, 30, 10, 25, 50, 90]  # contato no índice 4 (y=10)
for i, y in enumerate(ys):
    frames.append(make_kp({
        "right_shoulder": (0, 0), "right_elbow": (0, 5), "right_wrist": (i, y),
        "right_hip": (0, 20), "right_knee": (0, 30), "right_ankle": (0, 40),
    }))
ang = compute_angles(frames, "right")
ph = segment_phases(ang)
check("contato no quadro 4", ph.contact == 4)
check("loading antes do contato", ph.loading == 0)
check("follow depois do contato", ph.follow_through == 7)
check("cocking entre os dois", ph.loading <= (ph.cocking or -1) <= ph.contact)

print("kinematic_sequence:")
chain = kinematic_sequence(ang, fps=240.0)
check("registrou picos de junta", len(chain.peak_frames) >= 1)

print()
if _fail == 0:
    print("TODOS OS TESTES PASSARAM")
else:
    print(f"{_fail} TESTE(S) FALHARAM")
sys.exit(1 if _fail else 0)
