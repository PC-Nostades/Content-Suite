"""Genera piezas gráficas de prueba para la auditoría multimodal.

    python scripts/make_test_images.py

Produce dos imágenes con la MISMA composición y una única diferencia
controlada — el tamaño del logo — para que el dictamen del Módulo III sea
comprobable en vez de anecdótico:

  pieza_ok.png    logo al ~14 % del ancho  → debe pasar la regla del 8 %
  pieza_mala.png  logo al ~4 % del ancho   → debe incumplirla

Pillow solo se usa aquí, en tiempo de desarrollo: NO entra en requirements.txt
ni corre en Render, donde el free tier tiene 512 MB.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SALIDA = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "images"

W, H = 1080, 1080
CREMA = "#FFF4D6"
NARANJA = "#F05A28"
NEGRO = "#171717"


def _fuente(tam: int):
    for nombre in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def crear_pieza(logo_pct: float, destino: Path) -> None:
    img = Image.new("RGB", (W, H), CREMA)
    d = ImageDraw.Draw(img)

    # Banda de color de marca
    d.rectangle([0, 0, W, 220], fill=NARANJA)

    # "Producto": un rectángulo que simula el empaque
    d.rounded_rectangle([340, 380, 740, 900], radius=28, fill=NARANJA, outline=NEGRO, width=6)
    d.text((420, 600), "QUINUA\nINFLADA", font=_fuente(56), fill=CREMA, align="center")

    # Titular
    d.text((70, 950), "Energía andina para tu día", font=_fuente(46), fill=NEGRO)

    # El LOGO — la única variable entre las dos piezas.
    ancho_logo = int(W * logo_pct)
    alto_logo = int(ancho_logo * 0.38)
    x0, y0 = 60, 60
    d.rounded_rectangle(
        [x0, y0, x0 + ancho_logo, y0 + alto_logo], radius=8, fill=CREMA, outline=NEGRO, width=3
    )
    d.text(
        (x0 + ancho_logo * 0.12, y0 + alto_logo * 0.22),
        "KIWICHA",
        font=_fuente(max(8, int(alto_logo * 0.45))),
        fill=NEGRO,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "PNG", optimize=True)
    kb = destino.stat().st_size // 1024
    print(f"  {destino.name:<16} logo al {logo_pct * 100:.0f}% del ancho · {kb} KB")


def main() -> int:
    print("Generando piezas de prueba...")
    crear_pieza(0.14, SALIDA / "pieza_ok.png")
    crear_pieza(0.04, SALIDA / "pieza_mala.png")
    print(f"\nEn {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
