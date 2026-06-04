from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"

HOST = "127.0.0.1"
PORT = 8000

REZKA_BASE_URL = "https://hdrezka.ag/"
DEFAULT_RESULT_LIMIT = 100
MAX_RESULT_LIMIT = 300
REQUEST_TIMEOUT = 12
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://hdrezka_user:password@localhost:5432/hdrezka_filter",
)
HDREZKA_DEBUG = os.getenv("HDREZKA_DEBUG", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEBUG = HDREZKA_DEBUG
CRAWLER_PAGE_LIMIT = int(os.getenv("CRAWLER_PAGE_LIMIT", "20"))
CRAWLER_ITEM_LIMIT = int(os.getenv("CRAWLER_ITEM_LIMIT", "500"))
CRAWLER_SLEEP_SECONDS = float(os.getenv("CRAWLER_SLEEP_SECONDS", "1.0"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)
