"""CLI do medidor de velocidade de saque.

Exemplo:
  python src/analyze.py \
      --video saque.mp4 \
      --athlete "Atleta X" \
      --ref-length-m 0.914 \
      --ref-length-px 220 \
      --fps 240 \
      --outdir output

A escala (metros por pixel) vem de um objeto de referência de tamanho conhecido
no plano do saque. Você fornece o comprimento real (--ref-length-m) e quantos
pixels ele ocupa no quadro (--ref-length-px). Se --fps não for passado, usa o
fps embutido no vídeo (cuidado: muitos celulares gravam slow-motion mas o
arquivo reporta 30 fps — confira).
"""

from __future__ import annotations

import argparse
import os
import sys

# Permite rodar tanto como módulo quanto direto de src/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calibration import Calibration
from ball_tracker import BallTracker
from speed_estimator import estimate

from report import (
    write_trajectory_csv,
    write_speed_plot,
    write_summary_json,
    write_annotated_video,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Medidor de velocidade de saque de tênis")
    p.add_argument("--video", required=True, help="Caminho do vídeo do saque")
    p.add_argument("--athlete", default="Atleta", help="Nome do atleta")
    p.add_argument(
        "--ref-length-m",
        type=float,
        required=True,
        help="Comprimento real do objeto de referência (m)",
    )
    p.add_argument(
        "--ref-length-px",
        type=float,
        required=True,
        help="Comprimento do objeto de referência no quadro (pixels)",
    )
    p.add_argument(
        "--fps",
        type=float,
        default=None,
        help="fps real da captura (sobrescreve o do arquivo)",
    )
    p.add_argument("--outdir", default="output", help="Diretório de saída")
    p.add_argument(
        "--detector",
        choices=["classic", "dl"],
        default="classic",
        help="classic = cor+movimento (sem deps pesadas); "
        "dl = YOLOv8 (robusto em quadra real, requer ultralytics/torch)",
    )
    p.add_argument(
        "--model",
        default="yolov8n.pt",
        help="Pesos do detector DL (use seu fine-tuning de bola de tênis aqui)",
    )
    p.add_argument(
        "--conf", type=float, default=0.10, help="Confiança mínima do detector DL"
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Desliga o filtro de cor (use se a bola não for amarelo-esverdeada)",
    )
    p.add_argument(
        "--no-video",
        action="store_true",
        help="Não gerar o vídeo anotado (mais rápido)",
    )
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    if args.detector == "dl":
        from detector_dl import DLBallDetector

        print(f"[0/4] Carregando detector DL ({args.model}) ...")
        tracker = DLBallDetector(model_path=args.model, conf=args.conf)
    else:
        tracker = BallTracker(use_color=not args.no_color)
    print(f"[1/4] Rastreando bola ({args.detector}) em {args.video} ...")
    trajectory, meta = tracker.track(args.video)
    print(
        f"      {meta['detections']} detecções em {meta['frames']} quadros "
        f"(fps arquivo={meta['fps']:.1f})"
    )

    fps = args.fps if args.fps else meta["fps"]
    if not fps or fps <= 0:
        print("ERRO: fps inválido. Informe --fps.", file=sys.stderr)
        return 2

    calib = Calibration.from_reference(args.ref_length_m, args.ref_length_px, fps)
    print(f"[2/4] Escala: {calib.meters_per_pixel:.5f} m/px @ {fps:.0f} fps")

    result = estimate(trajectory, calib)
    print(
        f"[3/4] Velocidade de pico: {result.peak_kmh:.1f} km/h "
        f"({result.peak_ms:.1f} m/s) | média {result.mean_kmh:.1f} km/h"
    )
    for note in result.notes:
        print(f"      ⚠ {note}")

    base = os.path.join(args.outdir, "saque")
    write_trajectory_csv(base + "_trajetoria.csv", trajectory)
    write_speed_plot(base + "_velocidade.png", result, args.athlete)
    summary = write_summary_json(
        base + "_resumo.json", args.athlete, result, meta, calib.meters_per_pixel
    )
    if not args.no_video:
        write_annotated_video(
            args.video, base + "_anotado.mp4", trajectory, result
        )

    print(f"[4/4] Saídas em {args.outdir}/")
    print(f"      pico = {summary['resultado']['velocidade_pico_kmh']} km/h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
