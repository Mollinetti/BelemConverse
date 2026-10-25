"""Base paths."""
import os
from pathlib import Path

# Base paths (env-overridable for Docker / alternate deploy targets)
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.getenv("BELEM_DATA_DIR", str(BASE_DIR / "data")))
