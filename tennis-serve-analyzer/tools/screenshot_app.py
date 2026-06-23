"""Tira prints reais do app (home e tela de resultado) num viewport de celular.

Requer o app rodando (gunicorn/flask) e o Playwright+Chromium instalados.
Uso:  python tools/screenshot_app.py --base http://127.0.0.1:5013 --out output/shots
"""

from __future__ import annotations

import argparse
import os


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:5013")
    p.add_argument("--out", default="output/shots")
    p.add_argument("--video", default="output/saque_sintetico.mp4")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
        )
        page = ctx.new_page()

        # ---- tela inicial ----
        page.goto(args.base, wait_until="networkidle")
        page.screenshot(path=os.path.join(args.out, "01_home.png"), full_page=True)
        print("home capturada")

        # ---- preenche e envia para gerar a tela de resultado ----
        page.fill('input[name="athlete"]', "João Silva")
        page.fill('#fps', "240")
        page.fill('input[name="ref_length_m"]', "1.0")
        page.fill('input[name="ref_length_px"]', "200")
        page.set_input_files('#video', os.path.abspath(args.video))
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)  # deixa o GIF/imagens carregarem
        page.screenshot(path=os.path.join(args.out, "02_resultado.png"), full_page=True)
        print("resultado capturado")

        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
