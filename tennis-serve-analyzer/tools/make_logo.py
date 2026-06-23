"""Gera a logomarca do VC Fisiocoach (ícone do app) em vários tamanhos.

Desenha em alta resolução (supersampling) e reduz, para bordas suaves. Produz:
  - icon-512.png / icon-192.png   (PWA)
  - icon-maskable-512.png         (PWA com área de segurança)
  - apple-touch-icon.png (180)    (tela inicial iOS)
  - favicon-32.png                (aba do navegador)
  - logo.png                      (compatibilidade / header)

Conceito: bola de tênis com rastro de velocidade sobre fundo verde (marca VF) —
remete a saque + medição de velocidade.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

GREEN_TOP = (46, 204, 85)
GREEN_BOT = (18, 150, 60)
BALL = (214, 255, 60)
BALL_SHADE = (150, 200, 30)
SEAM = (255, 255, 255)
INK = (10, 40, 18)

SS = 4  # fator de supersampling


def _vgrad(size: int, top, bot) -> Image.Image:
    g = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        g.putpixel((0, y), tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    return g.resize((size, size))


def draw_icon(size: int, *, rounded: bool = True, safe: float = 0.0) -> Image.Image:
    """Desenha o ícone em `size` px. `safe` adiciona margem (ícone maskable)."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # fundo arredondado com gradiente verde
    bg = _vgrad(S, GREEN_TOP, GREEN_BOT).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    radius = int(S * 0.22) if rounded else 0
    md.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)
    img.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # área útil (margem de segurança para ícone maskable)
    m = int(S * safe)
    cx, cy = S * 0.56, S * 0.46
    r = (S - 2 * m) * 0.26

    # rastro de velocidade (3 traços atrás da bola)
    for i, off in enumerate((1.0, 1.55, 2.15)):
        x0 = cx - r * (off + 0.7)
        x1 = cx - r * off
        y = cy - r * 0.45 + i * r * 0.45
        w = int(r * (0.34 - i * 0.08))
        d.line([(x0, y), (x1, y)], fill=(255, 255, 255, 150), width=max(2, w))

    # bola: disco com leve sombreamento
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BALL)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BALL_SHADE, width=int(r * 0.06))

    # costura clássica: dois arcos simétricos curvando para o centro
    sw = max(2, int(r * 0.11))
    # arco esquerdo (perto da borda esquerda, bojo para a direita)
    d.arc([cx - r * 2.25, cy - r, cx + r * 0.05, cy + r],
          start=302, end=58, fill=SEAM, width=sw)
    # arco direito (perto da borda direita, bojo para a esquerda)
    d.arc([cx - r * 0.05, cy - r, cx + r * 2.25, cy + r],
          start=122, end=238, fill=SEAM, width=sw)

    # monograma "VF" na base
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(S * 0.16)
        )
    except Exception:
        font = None
    if font is not None:
        text = "VF"
        tb = d.textbbox((0, 0), text, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        d.text(((S - tw) / 2 - tb[0], S * 0.74 - tb[1]), text, font=font, fill=INK)

    return img.resize((size, size), Image.LANCZOS)


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    static = os.path.join(here, "..", "webapp", "static")
    os.makedirs(static, exist_ok=True)

    draw_icon(512).save(os.path.join(static, "icon-512.png"))
    draw_icon(192).save(os.path.join(static, "icon-192.png"))
    draw_icon(180).save(os.path.join(static, "apple-touch-icon.png"))
    draw_icon(32).save(os.path.join(static, "favicon-32.png"))
    draw_icon(512).save(os.path.join(static, "logo.png"))
    # maskable: mesma arte com margem de segurança (~10%)
    draw_icon(512, safe=0.12).save(os.path.join(static, "icon-maskable-512.png"))

    print("Logo gerada em", os.path.abspath(static))
    for f in ("icon-512.png", "icon-192.png", "apple-touch-icon.png",
              "favicon-32.png", "icon-maskable-512.png", "logo.png"):
        print("  •", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
