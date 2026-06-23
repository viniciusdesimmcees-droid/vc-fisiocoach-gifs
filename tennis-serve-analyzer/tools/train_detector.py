"""Fine-tuning do detector de bola (YOLOv8) sobre um dataset em formato YOLO.

Wrapper fino sobre o treino do Ultralytics, com defaults sensatos para o caso
"bola pequena e veloz". Use com dados REAIS anotados para produção; aqui também
roda sobre o dataset sintético do make_dataset.py para validar o pipeline.

Uso:
    python tools/train_detector.py --data dataset/data.yaml \
        --base yolov8n.pt --epochs 50 --imgsz 960 --name tennis_ball

O melhor checkpoint sai em runs/detect/<name>/weights/best.pt — aponte o
analyze.py para ele:  --detector dl --model runs/detect/<name>/weights/best.pt
"""

from __future__ import annotations

import argparse


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="caminho do data.yaml")
    p.add_argument("--base", default="yolov8n.pt", help="pesos base p/ fine-tuning")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=960, help="bola é pequena: imgsz alto")
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--name", default="tennis_ball")
    p.add_argument("--device", default="cpu", help="cpu, 0, 0,1, ...")
    p.add_argument("--patience", type=int, default=20)
    args = p.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.base)
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name,
        device=args.device,
        patience=args.patience,
        verbose=True,
    )
    print("Treino concluído.")
    save_dir = getattr(results, "save_dir", None)
    if save_dir:
        print(f"Melhor checkpoint: {save_dir}/weights/best.pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
