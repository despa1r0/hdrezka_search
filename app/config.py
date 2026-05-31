from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"

HOST = "127.0.0.1"
PORT = 8000

REZKA_BASE_URL = "https://hdrezka.ag/"
DEFAULT_RESULT_LIMIT = 100
MAX_RESULT_LIMIT = 300
REQUEST_TIMEOUT = 12
DEBUG = os.getenv("HDREZKA_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)
