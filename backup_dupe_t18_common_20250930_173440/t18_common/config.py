from pathlib import Path
from dotenv import load_dotenv
import os

ROOT = Path(r"C:\T18")

# IMPORTANT: override=True ensures C:\T18\.env wins over any pre-set environment variables
load_dotenv(ROOT / ".env", override=True)

def cfg(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)

def paths():
    return {
        "root": ROOT,
        "data": Path(cfg("DATA_DIR", str(ROOT / "data"))),
        "logs": Path(cfg("LOG_DIR", str(ROOT / "logs"))),
        "db": Path(cfg("DB_PATH", str(ROOT / "data" / "t18.db"))),
        "assets": ROOT / "assets",
    }
