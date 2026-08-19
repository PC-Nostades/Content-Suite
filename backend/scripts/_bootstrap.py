"""Permite ejecutar los scripts de `backend/scripts/` directamente con `python scripts/x.py`.

Añade `backend/` al sys.path para que `import app...` funcione sin instalar el paquete.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# La consola de Windows usa cp1252 por defecto y revienta con UnicodeEncodeError
# ante cualquier carácter fuera de esa página (flechas, símbolos, incluso acentos
# según la configuración). `errors="replace"` garantiza que un script nunca falle
# por no poder imprimir un carácter.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass
