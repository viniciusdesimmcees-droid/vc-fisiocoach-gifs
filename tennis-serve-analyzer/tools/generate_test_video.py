"""Gera um saque sintético com velocidade de referência CONHECIDA.

Serve para validar a precisão do medidor de ponta a ponta sem precisar de
filmagem real. Imprime o ground truth (velocidade real, escala e px da
referência) para você comparar com o resultado do analyze.py.

Cena:
  - Fundo de quadra (verde) + objeto de referência (barra branca vertical de
    comprimento conhecido em metros).
  - Fase 1: toss (bola sobe e desacelera) — lenta.
  - Fase 2: impacto + saque (bola desce em diagonal) — rápida, velocidade alvo.
"""

from __future__ import annotations

import argparse

import cv2
import numpy as np


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="output/saque_sintetico.mp4")
    p.add_argument("--fps", type=float, default=240.0)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument(
        "--serve-kmh", type=float, default=180.0, help="velocidade alvo do saque"
    )
    p.add_argument(
        "--ref-length-m", type=float, default=1.0, help="comprimento real da referência"
    )
    p.add_argument(
        "--ref-length-px", type=float, default=200.0, help="comprimento da referência em px"
    )
    args = p.parse_args()

    mpp = args.ref_length_m / args.ref_length_px  # metros por pixel (ground truth)
    serve_ms = args.serve_kmh / 3.6
    serve_px_per_frame = serve_ms / mpp / args.fps  # deslocamento por quadro em px

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(args.out, fourcc, args.fps, (args.width, args.height))

    ball_r = 7
    ref_x = 120
    ref_top = args.height - 120 - int(args.ref_length_px)

    # --- Fase 1: toss (sobe desacelerando) ---
    toss_frames = 40
    start = np.array([args.width * 0.35, args.height * 0.70])
    apex = np.array([args.width * 0.40, args.height * 0.18])
    positions: list[np.ndarray] = []
    for i in range(toss_frames):
        # ease-out quadrático: rápido no início, lento no apex
        t = i / (toss_frames - 1)
        e = 1 - (1 - t) ** 2
        positions.append(start + (apex - start) * e)

    # --- Fase 2: saque (diagonal rápida e constante na velocidade alvo) ---
    direction = np.array([0.82, 0.57])  # para baixo e para frente
    direction = direction / np.linalg.norm(direction)
    pos = apex.copy()
    serve_frames = 22
    for _ in range(serve_frames):
        pos = pos + direction * serve_px_per_frame
        if pos[0] > args.width - 20 or pos[1] > args.height - 20:
            break
        positions.append(pos.copy())

    for pt in positions:
        frame = np.full((args.height, args.width, 3), (60, 120, 60), dtype=np.uint8)
        # linha de base da quadra
        cv2.line(
            frame, (0, args.height - 110), (args.width, args.height - 110),
            (230, 230, 230), 3,
        )
        # objeto de referência (barra branca de comprimento conhecido)
        cv2.line(
            frame, (ref_x, ref_top), (ref_x, ref_top + int(args.ref_length_px)),
            (255, 255, 255), 6,
        )
        # bola amarelo-esverdeada (BGR)
        cv2.circle(frame, (int(pt[0]), int(pt[1])), ball_r, (60, 230, 220), -1)
        out.write(frame)

    out.release()

    print("Vídeo sintético gerado:", args.out)
    print("--- GROUND TRUTH (use no analyze.py) ---")
    print(f"  fps              = {args.fps:.0f}")
    print(f"  ref-length-m     = {args.ref_length_m}")
    print(f"  ref-length-px    = {args.ref_length_px:.0f}")
    print(f"  metros_por_pixel = {mpp:.5f}")
    print(f"  VELOCIDADE REAL  = {args.serve_kmh:.1f} km/h ({serve_ms:.1f} m/s)")
    print(f"  desloc/quadro    = {serve_px_per_frame:.1f} px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
