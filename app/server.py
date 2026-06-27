from __future__ import annotations

import threading
from datetime import datetime
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT,
    CRAWLER_LOAD_MORE_ITEM_LIMIT,
    CRAWLER_LOAD_MORE_PAGE_LIMIT,
    CRAWLER_LOAD_MORE_SLEEP_SECONDS,
    HOST,
    PORT,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from app.cookie_refresher import start_cookie_refresh_scheduler
from app.crawler import (
    RezkaCrawler,
    best_slugs_from_params,
    build_crawl_state_scope,
    filters_from_params,
    genre_slugs_from_params,
    section_from_params,
)
from app.notifier import notify_exception
from app.passive_crawler import start_passive_crawler_scheduler
from app.repositories.user_repository import ensure_app_users, get_all_users
from app.services.search_service import SearchService
from app.services.user_state_service import apply_movie_state

app = FastAPI(title="HdRezka DB Filter")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
search_service = SearchService()
crawl_lock = threading.Lock()
crawl_progress_lock = threading.Lock()
crawl_progress: dict[str, Any] = {
    "running": False,
    "message": "",
    "url": "",
    "catalogUrl": "",
    "stats": {},
    "error": "",
    "updatedAt": "",
}


@app.on_event("startup")
def on_startup() -> None:
    start_cookie_refresh_scheduler()
    start_passive_crawler_scheduler()


@app.exception_handler(Exception)
async def api_unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    notify_exception("FastAPI unhandled exception", exc)
    return _json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Internal server error"})


@app.get("/")
@app.get("/index.html")
def index() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html", media_type="text/html; charset=utf-8")


@app.get("/api/users")
def api_users() -> JSONResponse:
    try:
        ensure_app_users()
        users = get_all_users()
    except Exception as exc:
        return _json(
            HTTPStatus.SERVICE_UNAVAILABLE,
            {
                "error": (
                    "PostgreSQL недоступен или схема не применена. "
                    f"Детали: {exc}"
                )
            },
        )

    return _json(HTTPStatus.OK, {"users": users})


@app.get("/api/search")
def api_search(request: Request) -> JSONResponse:
    params = {key: value for key, value in request.query_params.items()}
    status, payload = search_service.search(params)
    return _json(status, payload)


@app.post("/api/movie-state")
async def api_movie_state(request: Request) -> JSONResponse:
    try:
        payload = await _read_request_payload(request)
        user_id = int(payload.get("user_id", ""))
        movie_id = int(payload.get("movie_id", payload.get("movieId", "")))
        state = str(payload.get("state", "")).strip()
        action = str(payload.get("action", "set")).strip() or "set"
        apply_movie_state(user_id, movie_id, state, action)
    except Exception as exc:
        return _json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    return _json(
        HTTPStatus.OK,
        {
            "ok": True,
            "user_id": user_id,
            "movie_id": movie_id,
            "state": state,
            "action": action,
        },
    )


@app.post("/api/crawl")
async def api_crawl(request: Request) -> JSONResponse:
    if not crawl_lock.acquire(blocking=False):
        return _json(
            HTTPStatus.CONFLICT,
            {"error": "Crawler уже работает. Дождись завершения текущей дозагрузки."},
        )

    try:
        params = await _read_request_payload(request)
        genre_slugs = genre_slugs_from_params(params)
        best_slugs: list[str] = []
        requested_source = str(params.get("crawl_source", "auto")).strip().lower()
        if requested_source == "popular":
            best_slugs = best_slugs_from_params(params)
            source = "best" if best_slugs else "popular"
            genre_slugs = []
        elif requested_source == "new":
            source = "new"
            genre_slugs = []
        else:
            source = "genres" if genre_slugs else "new"
        section = section_from_params(params)
        state_scope = build_crawl_state_scope(
            params,
            source=source,
            section=section,
            genre_slugs=genre_slugs,
            best_slugs=best_slugs,
        )
        _set_crawl_progress(
            running=True,
            message="Crawler стартовал.",
            source=source,
            genreSlugs=genre_slugs,
            bestSlugs=best_slugs,
            section=section,
            stateScope=state_scope,
            url="",
            catalogUrl="",
            stats={},
            error="",
        )
        crawler = RezkaCrawler(
            page_limit=CRAWLER_LOAD_MORE_PAGE_LIMIT,
            item_limit=CRAWLER_LOAD_MORE_ITEM_LIMIT,
            sleep_seconds=CRAWLER_LOAD_MORE_SLEEP_SECONDS,
            imdb_enabled=CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT > 0,
            imdb_item_limit=CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT,
            source=source,
            resume=True,
            genre_slugs=genre_slugs,
            best_slugs=best_slugs,
            section=section,
            filters=filters_from_params(params),
            state_scope=state_scope,
            progress_callback=_set_crawl_progress,
        )
        stats = await run_in_threadpool(crawler.run)
    except Exception as exc:
        _set_crawl_progress(
            running=False,
            message=f"Crawler упал: {exc}",
            error=str(exc),
        )
        notify_exception("API crawl failed", exc)
        return _json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
    finally:
        crawl_lock.release()

    _set_crawl_progress(
        running=False,
        message=(
            (
                f"Crawler закончил с ошибками: {stats.last_error}"
                if stats.errors
                else (
                    f"Crawler закончил: сохранено {stats.saved}, уже было {stats.existing}, "
                    f"пропущено {stats.skipped}, страниц {stats.pages}."
                )
            )
        ),
        source=source,
        genreSlugs=genre_slugs,
        bestSlugs=best_slugs,
        section=section,
        stateScope=state_scope,
        stats=stats.__dict__,
        error=stats.last_error,
    )
    return _json(
        HTTPStatus.OK,
        {
            "ok": True,
            "source": source,
            "genreSlugs": genre_slugs,
            "bestSlugs": best_slugs,
            "section": section,
            "stateScope": state_scope,
            "stats": stats.__dict__,
        },
    )


@app.get("/api/crawl-progress")
def api_crawl_progress() -> JSONResponse:
    with crawl_progress_lock:
        return _json(HTTPStatus.OK, dict(crawl_progress))


@app.post("/api/shutdown")
def api_shutdown() -> JSONResponse:
    return _json(
        HTTPStatus.OK,
        {"status": "FastAPI server runs under uvicorn. Stop it with Ctrl+C."},
    )


async def _read_request_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("Content-Type", "")
    if "application/json" in content_type:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    raw = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def _json(status: int, data: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=int(status), content=data)


def _set_crawl_progress(**payload: Any) -> None:
    with crawl_progress_lock:
        crawl_progress.update(payload)
        crawl_progress["updatedAt"] = datetime.now().isoformat(timespec="seconds")


def run(host: str = HOST, port: int = PORT) -> None:
    uvicorn.run("app.server:app", host=host, port=port)
