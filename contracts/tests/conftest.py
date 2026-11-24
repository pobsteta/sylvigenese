"""Configuration pytest des tests unitaires du validateur (mission 009)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (HERE, HERE.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
