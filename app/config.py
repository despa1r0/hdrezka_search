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

REZKA_BASE_URL = os.getenv("REZKA_BASE_URL", "https://rezka.ag/")
REZKA_USER_AGENT = os.getenv(
    "REZKA_USER_AGENT",
    (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:149.0) "
        "Gecko/20100101 Firefox/149.0"
    ),
)
REZKA_COOKIE = os.getenv("REZKA_COOKIE", "").strip()
REZKA_ACCEPT_LANGUAGE = os.getenv("REZKA_ACCEPT_LANGUAGE", "en-US,en;q=0.9")
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
CRAWLER_SOURCE = os.getenv("CRAWLER_SOURCE", "new").strip().lower()
CRAWLER_LOAD_MORE_PAGE_LIMIT = int(os.getenv("CRAWLER_LOAD_MORE_PAGE_LIMIT", "3"))
CRAWLER_LOAD_MORE_ITEM_LIMIT = int(os.getenv("CRAWLER_LOAD_MORE_ITEM_LIMIT", "12"))
CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT = int(os.getenv("CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT", "0"))
CRAWLER_LOAD_MORE_SLEEP_SECONDS = float(os.getenv("CRAWLER_LOAD_MORE_SLEEP_SECONDS", "0"))
CRAWLER_IMDB_ENABLED = os.getenv("CRAWLER_IMDB_ENABLED", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CRAWLER_IMDB_ITEM_LIMIT = int(os.getenv("CRAWLER_IMDB_ITEM_LIMIT", "200"))

USER_AGENT = REZKA_USER_AGENT
