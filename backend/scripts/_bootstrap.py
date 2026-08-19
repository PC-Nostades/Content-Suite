"""Permite ejecutar los scripts de `backend/scripts/` directamente con `python scripts/x.py`.

Añade `backend/` al sys.path para que `import app...` funcione sin instalar el paquete.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
