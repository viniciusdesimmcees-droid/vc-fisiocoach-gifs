"""Renderiza um quadro com uma bola de tênis de aparência mais realista.

Objetivo: dar ao detector DL (YOLOv8 treinado em fotos reais) uma chance justa
de reconhecer a bola, já que o círculo chapado do vídeo sintético não se parece
com uma foto. NÃO substitui validação com filmagem real — é apenas um teste de
fumaça para confirmar que o detector dispara em algo parecido com uma bola.
"""

from __future__ import annotations

import argparse

import cv2
import numpy as np


def draw_tennis_ball(img: np.ndarray, cx: int, cy: int, r: int) -> None:
    # Esfera com sombreamento radial (mais clara em cima-esquerda).
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            dx, dy = xx - cx, yy - cy
            d2 = dx * dx + dy * dy
            if d2 > r * r:
                continue
            # iluminação: ponto de luz em (-0.4r, -0.4r)
            nx, ny = dx + 0.4 * r, dy + 0.4 * r
            shade = max(0.35, 1.0 - (nx * nx + ny * ny) / (2.2 * r * r))
            b, g, rr = 70 * shade, 235 * shade, 225 * shade  # amarelo-esverdeado
            img[yy, xx] = (int(b), int(g), int(rr))
    # Costura curva branca característica.
    cv2.ellipse(img, (cx, cy), (r, int(r * 0.55)), 20, 200, 340, (245, 245, 245), 2)
    cv2.ellipse(img, (cx, cy), (r, int(r * 0.55)), 20, 20, 160, (245, 245, 245), 2)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="output/ball_realistic.png")
    p.add_argument("--size", type=int, default=640)
    p.add_argument("--radius", type=int, default=70)
    args = p.parse_args()

    n = args.size
    # Fundo tipo quadra: gradiente esverdeado com ruído leve.
    img = np.full((n, n, 3), (60, 110, 70), dtype=np.uint8)
    noise = np.random.randint(-12, 12, (n, n, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    cv2.line(img, (0, int(n * 0.8)), (n, int(n * 0.8)), (235, 235, 235), 4)

    draw_tennis_ball(img, n // 2, n // 2, args.radius)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    cv2.imwrite(args.out, img)
    print("Quadro realista salvo em:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
