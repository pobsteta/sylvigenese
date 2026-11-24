"""Configuration pytest des tests d'acceptation de `contracts/validate` (mission 010)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
