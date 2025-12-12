# tests/conftest.py
import sys
from pathlib import Path

# Ensure project root (the directory that contains the "app" package) is on sys.path
ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    # insert at position 0 so imports prefer local package
    sys.path.insert(0, root_str)
