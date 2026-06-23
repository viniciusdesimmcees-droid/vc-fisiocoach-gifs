"""Demo da camada biomecânica com keypoints SINTÉTICOS de um saque.

Por que sintético: a pose (YOLOv8-pose) só funciona em pessoas reais filmadas
(validada em foto real em output/_probe.jpg). Para mostrar o FORMATO das saídas
(gráfico de ângulos + JSON) sem filmagem, sintetizamos uma sequência de
keypoints de um saque destro plausível e rodamos o pipeline real
(compute_angles -> segment_phases -> kinematic_sequence -> relatório).

Não substitui análise de vídeo real — é uma demonstração do entregável.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pose_estimator import KP  # noqa: E402
from biomechanics import (  # noqa: E402
    compute_angles, segment_phases, kinematic_sequence, choose_serve_side,
)
from biomech_report import write_angles_plot, write_summary_json  # noqa: E402


def _ramp(t: float, center: float, width: float = 0.05) -> float:
    """Logística: sua derivada (velocidade) tem pico em t=center. Usada para
    escalonar o movimento das juntas e produzir cadeia proximal->distal."""
    return 1.0 / (1.0 + math.exp(-(t - center) / width))


def synth_serve(n: int = 60) -> list:
    """Gera keypoints (17,3) por quadro de um saque destro idealizado.

    Cadeia proximal->distal: cada junta acelera em um instante crescente —
    quadril (t~0.20) -> tronco (~0.32) -> ombro (~0.44) -> cotovelo (~0.56),
    com o punho atingindo o ponto alto no contato (~t=0.60).
    """
    frames = []
    for i in range(n):
        t = i / (n - 1)
        kp = np.zeros((17, 3), dtype=np.float32)

        # quadril: gira primeiro (joelho/tornozelo avançam) — pico ~0.20
        rh = _ramp(t, 0.20)
        hip = np.array([300.0, 350.0])
        knee = np.array([300.0 + 35 * rh, 430.0])
        ankle = np.array([300.0 + 55 * rh, 500.0])

        # tronco: inclina logo depois — pico ~0.32 (ombro desloca em x)
        rt = _ramp(t, 0.32)
        shoulder = np.array([300.0 + 45 * rt, 200.0])

        # ombro: estende o braço — pico ~0.44 (eleva o cotovelo)
        rs = _ramp(t, 0.44)
        elbow = np.array([shoulder[0] + 30.0, 260.0 - 70 * rs])

        # cotovelo: estende por último — pico ~0.56; punho sobe ao contato
        re = _ramp(t, 0.56)
        wrist_y = 360 - 320 * math.exp(-((t - 0.60) ** 2) / 0.02)
        wrist = np.array([elbow[0] + 10 + 30 * re, wrist_y])

        pts = {
            "right_shoulder": shoulder, "right_hip": hip, "right_knee": knee,
            "right_ankle": ankle, "right_elbow": elbow, "right_wrist": wrist,
            "left_shoulder": shoulder + [20, 0], "left_hip": hip + [20, 0],
            "left_wrist": np.array([260.0, 380.0]),
        }
        for name, xy in pts.items():
            kp[KP[name]] = (float(xy[0]), float(xy[1]), 0.9)
        frames.append(kp)
    return frames


def main() -> int:
    outdir = "output/biomech"
    os.makedirs(outdir, exist_ok=True)
    fps = 240.0

    frames = synth_serve(60)
    side = choose_serve_side(frames)
    angles = compute_angles(frames, side)
    phases = segment_phases(angles)
    chain = kinematic_sequence(angles, fps)
    meta = {"fps": fps, "frames": len(frames), "pose_detected": len(frames)}

    base = os.path.join(outdir, "biomech_demo")
    write_angles_plot(base + "_angulos.png", angles, phases, fps, "Atleta Demo (sintético)")
    summary = write_summary_json(base + "_resumo.json", "Atleta Demo (sintético)",
                                 side, angles, phases, chain, meta)
    print("Demo biomecânica gerada em", outdir)
    print("  lado:", side, "| contato no quadro", phases.contact)
    print("  cadeia proximal->distal:", chain.proximal_to_distal)
    for n in chain.notes:
        print("  •", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
