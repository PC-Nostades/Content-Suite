"""Genera piezas gráficas de prueba para la auditoría multimodal.

    python scripts/make_test_images.py

Cada pieza comparte la MISMA composición base y rompe **una sola** regla del
manual, para que el dictamen del Módulo III sea comprobable en vez de anecdótico:
si la auditoría marca `fail`, se sabe exactamente qué regla debía citar.

  pieza_aprobada.png        cumple TODAS las reglas    → la única que debe dar `pass`
  pieza_ok.png              logo al 14 % del ancho     → pasa la regla del 8 %
  pieza_mala.png            logo al 4 % del ancho      → la incumple
  pieza_conforme.png        producto al 34 % del área  → pasa también la regla del 25 %
  pieza_producto_chico.png  producto al 3 % del área   → incumple la del 25 %
  pieza_color_prohibido.png fucsia #FF00A8             → color fuera de la paleta declarada
  pieza_bajo_contraste.png  crema sobre crema          → contraste muy por debajo de 4.5:1
  pieza_texto_saturado.png  texto sobre ~60 % del área → excede el 35 % y deja sin aire la pieza

⚠️ Salvo `pieza_aprobada.png`, NINGUNA de estas piezas cumple el manual completo:
   cada una está construida para aislar UNA regla. `pieza_ok.png` deja el producto
   al 17,8 % (incumple la del 25 %) y `pieza_conforme.png` no dice «Grano de Puno»
   y lleva el naranja al 54 % del área (su tope declarado es 40 %). Sirven para
   comprobar que el auditor DETECTA, no para comprobar que aprueba.

Pillow solo se usa aquí, en tiempo de desarrollo: NO entra en requirements.txt
ni corre en Render, donde el free tier tiene 512 MB.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SALIDA = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "images"

W, H = 1080, 1080
AREA = W * H

# Colores de la paleta declarada en el manual sembrado.
CREMA = "#FFF4D6"
NARANJA = "#F05A28"
NEGRO = "#171717"

#: Declarado PROHIBIDO en el manual («Fucsia neón no declarado»). Existe aquí
#: para que una pieza pueda violar la regla de paleta de forma inequívoca.
FUCSIA_PROHIBIDO = "#FF00A8"

#: Caja del "empaque". La estándar ocupa el 17,8 % del encuadre.
CAJA_ESTANDAR = (340, 380, 740, 900)
CAJA_GRANDE = (240, 270, 840, 920)   # 33 % del área, sin pisar el titular
CAJA_CHICA = (500, 600, 680, 780)    # 2,8 % del área


def _fuente(tam: int):
    for nombre in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def _lienzo(fondo: str = CREMA, banda: str = NARANJA):
    """Fondo + banda superior de color de marca."""
    img = Image.new("RGB", (W, H), fondo)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 220], fill=banda)
    return img, d


def _producto(d, caja=CAJA_ESTANDAR, color: str = NARANJA) -> None:
    """El "empaque": un rectángulo con el nombre del producto.

    La posición y el cuerpo del texto se escalan con la caja mediante división
    ENTERA sobre las medidas de la caja estándar (400x520 → texto en +80,+220 a
    56 px). Así la caja estándar reproduce exactamente los valores de la versión
    original del script y `pieza_ok.png` / `pieza_mala.png` siguen siendo byte a
    byte las mismas imágenes que consume `scripts/demo_audit.py`.
    """
    x0, y0, x1, y1 = caja
    ancho, alto = x1 - x0, y1 - y0
    d.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=color, outline=NEGRO, width=6)
    d.text(
        (x0 + ancho * 80 // 400, y0 + alto * 220 // 520),
        "QUINUA\nINFLADA",
        font=_fuente(max(10, ancho * 56 // 400)),
        fill=CREMA,
        align="center",
    )


def _titular(d, color: str = NEGRO) -> None:
    d.text((70, 950), "Energía andina para tu día", font=_fuente(46), fill=color)


def _logo(d, logo_pct: float) -> None:
    """El logo. Su ancho relativo es la variable que mide la regla del 8 %."""
    ancho = int(W * logo_pct)
    alto = int(ancho * 0.38)
    x0, y0 = 60, 60
    d.rounded_rectangle([x0, y0, x0 + ancho, y0 + alto], radius=8, fill=CREMA, outline=NEGRO, width=3)
    d.text(
        (x0 + ancho * 0.12, y0 + alto * 0.22),
        "KIWICHA",
        font=_fuente(max(8, int(alto * 0.45))),
        fill=NEGRO,
    )


def _guardar(img: Image.Image, destino: Path, nota: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "PNG", optimize=True)
    kb = destino.stat().st_size // 1024
    print(f"  {destino.name:<26} {nota:<44} {kb} KB")


def _pct_area(caja) -> float:
    x0, y0, x1, y1 = caja
    return (x1 - x0) * (y1 - y0) / AREA * 100


# ------------------------------------------------------------------ las piezas


def pieza_aprobada(destino: Path) -> None:
    """La única pieza construida para obtener `pass`: cumple TODAS las reglas hard.

    Frente a `pieza_conforme.png` —que solo cumple las dos reglas métricas para las
    que fue diseñada— aquí se cierran los dos huecos que quedaban:

      1. «Grano de Puno» legible. Es una regla `hard` del manual («incluye una
         referencia visual o textual explícita al origen»), y ninguna otra pieza
         la satisface. Sin esto el veredicto es `fail` por muy bien medida que
         esté la composición.
      2. El producto va en Azul Noche Lima (#171717, tope 45 %) y no en Naranja
         Pop. Pintarlo naranja sumaría 33 % del producto + 20 % de la banda = 54 %,
         y el tope declarado del Naranja Pop es 40 % del área.

    Cuentas de la pieza resultante:
      logo 14 % del ancho (>= 8 %) · producto 33 % del área (>= 25 %)
      naranja ~20 % (<= 40 %) · negro ~34 % (<= 45 %) · crema ~47 % (<= 70 %)
      contraste negro/crema 16:1 y negro/naranja 5,3:1 (>= 4.5:1)
      texto ~4 % del área (<= 35 %) · aire >> 10 %
    """
    img, d = _lienzo()
    _producto(d, CAJA_GRANDE, color=NEGRO)
    _logo(d, 0.14)

    # Titular propio en lugar de `_titular`: hace falta una segunda línea para el
    # origen, y `_titular` no se toca porque `pieza_ok.png` y `pieza_mala.png`
    # deben seguir siendo byte a byte las que consume scripts/demo_audit.py.
    #
    # Ambas líneas en NEGRO sobre crema. En crema sobre la banda naranja el
    # contraste sería 3,1:1 y la regla de 4.5:1 es `hard`.
    d.text((70, 930), "Energía andina para tu día", font=_fuente(46), fill=NEGRO)
    d.text((70, 985), "Grano de Puno", font=_fuente(36), fill=NEGRO)

    _guardar(img, destino, "logo 14% · producto 33% · «Grano de Puno» · cumple todo")


def pieza_logo(logo_pct: float, destino: Path) -> None:
    """La pareja canónica: idénticas salvo el tamaño del logo."""
    img, d = _lienzo()
    _producto(d)
    _titular(d)
    _logo(d, logo_pct)
    veredicto = "cumple la regla del 8 %" if logo_pct >= 0.08 else "INCUMPLE la regla del 8 %"
    _guardar(img, destino, f"logo al {logo_pct * 100:.0f}% del ancho · {veredicto}")


def pieza_producto(caja, destino: Path) -> None:
    """Varía el área del producto: la regla exige al menos el 25 % del encuadre."""
    img, d = _lienzo()
    _producto(d, caja)
    _titular(d)
    _logo(d, 0.14)
    pct = _pct_area(caja)
    veredicto = "cumple la del 25 %" if pct >= 25 else "INCUMPLE la del 25 %"
    _guardar(img, destino, f"producto al {pct:.0f}% del área · {veredicto}")


def pieza_color_prohibido(destino: Path) -> None:
    """Introduce un color explícitamente prohibido en el manual."""
    img, d = _lienzo(banda=FUCSIA_PROHIBIDO)
    _producto(d, CAJA_ESTANDAR, color=FUCSIA_PROHIBIDO)
    _titular(d)
    _logo(d, 0.14)
    _guardar(img, destino, f"fucsia {FUCSIA_PROHIBIDO} · fuera de la paleta")


def pieza_bajo_contraste(destino: Path) -> None:
    """Titular en crema sobre fondo crema: contraste cercano a 1:1."""
    img, d = _lienzo()
    _producto(d)
    _titular(d, color=CREMA)  # el mismo color del fondo
    _logo(d, 0.14)
    _guardar(img, destino, "crema sobre crema · muy por debajo de 4.5:1")


def pieza_texto_saturado(destino: Path) -> None:
    """Satura la pieza de texto: excede el 35 % y no deja espacio libre."""
    img, d = _lienzo()
    _producto(d, CAJA_CHICA)
    _logo(d, 0.14)

    fuente = _fuente(40)
    lineas = [
        "Snack de quinua inflada con grano de Puno,",
        "práctico para llevar en la mochila y compartir",
        "en el recreo, en el parque o en la espera de",
        "siempre. Formato de 30 g, fácil de guardar.",
        "Energía andina para tu día, sin complicaciones.",
        "Encuéntralo en tu tienda favorita y arma tu",
        "próxima pausa donde quieras, cuando quieras.",
        "Tu pausa ya tiene plan: quinua inflada, lista",
        "para acompañarte en cualquier momento del día.",
        "Hecho en Perú con grano seleccionado de Puno.",
        "Guárdalo para tu próxima pausa y compártelo.",
        "Verano limeño: sol, tráfico y una pausa breve.",
    ]
    y = 250
    for linea in lineas:
        d.text((60, y), linea, font=fuente, fill=NEGRO)
        y += 56
    _titular(d)
    _guardar(img, destino, "texto sobre ~60% del área · excede el 35 %")


def main() -> int:
    print("Generando piezas de prueba...\n")

    # La única que debe salir `pass`. Va primera porque es la referencia: si el
    # auditor la rechaza, el problema está en el auditor, no en la pieza.
    pieza_aprobada(SALIDA / "pieza_aprobada.png")

    # La pareja canónica que usa scripts/demo_audit.py. No cambiar los nombres.
    pieza_logo(0.14, SALIDA / "pieza_ok.png")
    pieza_logo(0.04, SALIDA / "pieza_mala.png")

    pieza_producto(CAJA_GRANDE, SALIDA / "pieza_conforme.png")
    pieza_producto(CAJA_CHICA, SALIDA / "pieza_producto_chico.png")

    pieza_color_prohibido(SALIDA / "pieza_color_prohibido.png")
    pieza_bajo_contraste(SALIDA / "pieza_bajo_contraste.png")
    pieza_texto_saturado(SALIDA / "pieza_texto_saturado.png")

    print(f"\nEn {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
