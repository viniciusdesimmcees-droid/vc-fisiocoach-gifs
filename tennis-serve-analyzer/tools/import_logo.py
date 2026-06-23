"""Importa uma logo pronta (imagem do usuário) e gera todos os tamanhos do app.

Uso:
    python tools/import_logo.py --src webapp/static/logo-vf.png

Gera, em webapp/static/:
    icon-512.png, icon-192.png, apple-touch-icon.png (180), favicon-32.png,
    logo.png e icon-maskable-512.png (com margem de segurança).

Mantém a arte original; apenas redimensiona (recorte central para quadrado) e,
para o ícone maskable, adiciona margem para não cortar nas máscaras do Android.
"""

from __future__ import annotations

import argparse
import os

from PIL import Image


def _square(img: Image.Image) -> Image.Image:
    w, h = img.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    return img.crop((left, top, left + s, top + s))


def _resize(img: Image.Image, size: int) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def _maskable(img: Image.Image, size: int, safe: float = 0.12) -> Image.Image:
    """Coloca a arte numa área central (1 - 2*safe), com fundo da cor das bordas."""
    bg = img.getpixel((2, 2)) if img.mode == "RGBA" else img.convert("RGBA").getpixel((2, 2))
    canvas = Image.new("RGBA", (size, size), bg)
    inner = int(size * (1 - 2 * safe))
    art = _resize(img.convert("RGBA"), inner)
    off = (size - inner) // 2
    canvas.paste(art, (off, off), art)
    return canvas


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, help="caminho da logo de origem (PNG/JPG)")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    static = os.path.join(here, "..", "webapp", "static")
    os.makedirs(static, exist_ok=True)

    if not os.path.exists(args.src):
        print(f"ERRO: arquivo não encontrado: {args.src}")
        return 2

    img = Image.open(args.src).convert("RGBA")
    img = _square(img)

    out = {
        "icon-512.png": _resize(img, 512),
        "icon-192.png": _resize(img, 192),
        "apple-touch-icon.png": _resize(img, 180),
        "favicon-32.png": _resize(img, 32),
        "logo.png": _resize(img, 512),
        "icon-maskable-512.png": _maskable(img, 512),
    }
    for name, im in out.items():
        im.save(os.path.join(static, name))
        print("  •", name)
    print("Logo importada com sucesso em", os.path.abspath(static))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
