"""Utilidades de color: normalización de hex y contraste WCAG.

Vive en el backend porque el post-proceso del manual valida los pares de color que
declara el modelo. El frontend tiene su propia copia en `lib/contrast.ts` para
pintar el texto de los swatches — duplicar ~20 líneas es preferible a montar un
paquete compartido para eso.
"""

import re

_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def normalize_hex(value: str) -> str | None:
    """Devuelve `#RRGGBB` en mayúsculas, o `None` si no es un color válido.

    Acepta la forma corta (`#ABC` → `#AABBCC`) porque los modelos la producen a
    veces pese a pedirles 6 dígitos.
    """
    if not isinstance(value, str):
        return None
    match = _HEX_RE.match(value.strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return f"#{digits.upper()}"


def _srgb_channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float | None:
    """Luminancia relativa según WCAG 2.1."""
    normalized = normalize_hex(hex_color)
    if normalized is None:
        return None
    r, g, b = (int(normalized[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)


def contrast_ratio(a: str, b: str) -> float | None:
    """Ratio de contraste WCAG entre dos colores. Va de 1.0 a 21.0."""
    la, lb = relative_luminance(a), relative_luminance(b)
    if la is None or lb is None:
        return None
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_level(ratio: float, *, large_text: bool = False) -> str:
    """'AAA', 'AA' o 'fail' para el ratio dado."""
    if large_text:
        return "AAA" if ratio >= 4.5 else "AA" if ratio >= 3.0 else "fail"
    return "AAA" if ratio >= 7.0 else "AA" if ratio >= 4.5 else "fail"
