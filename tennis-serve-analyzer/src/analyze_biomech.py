"""CLI da análise biomecânica do saque (pose -> ângulos -> fases -> cadeia).

Exemplo:
  python src/analyze_biomech.py --video saque.mp4 --athlete "Atleta X" --fps 240

Complementa o analyze.py (velocidade da bola): aqui o foco é o GESTO do atleta.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from biomechanics import (
    choose_serve_side, compute_angles, segment_phases, kinematic_sequence,
)
from biomech_report import (
    write_angles_plot, write_summary_json, write_skeleton_video,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Análise biomecânica do saque de tênis")
    p.add_argument("--video", required=True)
    p.add_argument("--athlete", default="Atleta")
    p.add_argument("--fps", type=float, default=None, help="fps real (sobrescreve arquivo)")
    p.add_argument("--model", default="yolov8n-pose.pt", help="pesos de pose")
    p.add_argument("--side", choices=["auto", "left", "right"], default="auto")
    p.add_argument("--outdir", default="output/biomech")
    p.add_argument("--no-video", action="store_true")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    from pose_estimator import PoseEstimator

    print(f"[1/4] Estimando pose ({args.model}) em {args.video} ...")
    pose = PoseEstimator(model_path=args.model)
    frames, meta = pose.estimate_video(args.video)
    print(f"      pose em {meta['pose_detected']}/{meta['frames']} quadros")

    fps = args.fps if args.fps else meta["fps"]
    if not fps or fps <= 0:
        print("ERRO: fps inválido. Informe --fps.", file=sys.stderr)
        return 2

    side = choose_serve_side(frames) if args.side == "auto" else args.side
    print(f"[2/4] Lado dominante: {side}")

    angles = compute_angles(frames, side)
    phases = segment_phases(angles)
    chain = kinematic_sequence(angles, fps)
    print(f"[3/4] Fases: loading={phases.loading} contato={phases.contact} "
          f"follow={phases.follow_through}")

    base = os.path.join(args.outdir, "biomech")
    write_angles_plot(base + "_angulos.png", angles, phases, fps, args.athlete)
    summary = write_summary_json(base + "_resumo.json", args.athlete, side,
                                 angles, phases, chain, {**meta, "fps": fps})
    if not args.no_video:
        write_skeleton_video(args.video, base + "_esqueleto.mp4", frames, phases)

    print(f"[4/4] Saídas em {args.outdir}/")
    for n in chain.notes:
        print(f"      • {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
