import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
