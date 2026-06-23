"""Gera um dataset rotulado de bola de tênis em formato YOLO (sintético).

Serve para (a) provar que o harness de fine-tuning funciona de ponta a ponta e
(b) dar um ponto de partida quando ainda não há filmagem real anotada.

ATENÇÃO: dados sintéticos servem para validar o PIPELINE, não para produção.
Para um detector robusto em quadra, troque por imagens reais anotadas (exporte
do Roboflow/CVAT no formato YOLO) mantendo a mesma estrutura de pastas:

    dataset/
      images/{train,val}/*.jpg
      labels/{train,val}/*.txt   # cada linha: classe cx cy w h  (normalizado)
      data.yaml

Uso:
    python tools/make_dataset.py --out dataset --n-train 200 --n-val 40
"""

from __future__ import annotations

import argparse
import os
import random

import cv2
import numpy as np

from render_realistic_ball import draw_tennis_ball


def random_background(n: int) -> np.ndarray:
    """Fundo variado tipo quadra/ambiente para o detector não decorar o cenário."""
    base = random.choice([(60, 110, 70), (90, 90, 95), (40, 70, 120), (70, 120, 110)])
    img = np.full((n, n, 3), base, dtype=np.uint8)
    noise = np.random.randint(-18, 18, (n, n, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # algumas linhas de quadra aleatórias
    for _ in range(random.randint(0, 3)):
        y = random.randint(0, n - 1)
        cv2.line(img, (0, y), (n, y), (235, 235, 235), random.randint(2, 5))
    return img


def make_split(out_dir: str, split: str, count: int, size: int) -> None:
    img_dir = os.path.join(out_dir, "images", split)
    lbl_dir = os.path.join(out_dir, "labels", split)
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(lbl_dir, exist_ok=True)

    for i in range(count):
        img = random_background(size)
        # 1 bola por imagem (poderia ser 0..N; mantemos simples)
        r = random.randint(8, 42)
        cx = random.randint(r, size - r)
        cy = random.randint(r, size - r)
        draw_tennis_ball(img, cx, cy, r)

        # data augmentation leve: blur de movimento ocasional
        if random.random() < 0.4:
            k = random.choice([3, 5])
            img = cv2.GaussianBlur(img, (k, k), 0)

        name = f"{split}_{i:04d}"
        cv2.imwrite(os.path.join(img_dir, name + ".jpg"), img)

        # rótulo YOLO normalizado: classe 0 (tennis_ball)
        bw = (2 * r) / size
        bh = (2 * r) / size
        with open(os.path.join(lbl_dir, name + ".txt"), "w") as f:
            f.write(f"0 {cx / size:.6f} {cy / size:.6f} {bw:.6f} {bh:.6f}\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="dataset")
    p.add_argument("--n-train", type=int, default=200)
    p.add_argument("--n-val", type=int, default=40)
    p.add_argument("--size", type=int, default=640)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    make_split(args.out, "train", args.n_train, args.size)
    make_split(args.out, "val", args.n_val, args.size)

    data_yaml = os.path.join(args.out, "data.yaml")
    abs_out = os.path.abspath(args.out)
    with open(data_yaml, "w") as f:
        f.write(
            f"path: {abs_out}\n"
            "train: images/train\n"
            "val: images/val\n"
            "nc: 1\n"
            "names:\n"
            "  0: tennis_ball\n"
        )
    print(f"Dataset gerado em {abs_out}")
    print(f"  train={args.n_train}  val={args.n_val}  -> {data_yaml}")
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
