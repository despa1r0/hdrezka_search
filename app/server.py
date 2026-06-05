from __future__ import annotations

import threading
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, Request
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
from app.crawler import RezkaCrawler, filters_from_params, genre_slugs_from_params, section_from_params
from app.repositories.user_repository import ensure_test_users, get_all_users
from app.services.search_service import SearchService
from app.services.user_state_service import apply_movie_state

app = FastAPI(title="HdRezka DB Filter")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
search_service = SearchService()
crawl_lock = threading.Lock()


@app.get("/")
@app.get("/index.html")
def index() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html", media_type="text/html; charset=utf-8")


@app.get("/api/users")
def api_users() -> JSONResponse:
    try:
        ensure_test_users()
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
        source = "genres" if genre_slugs else "new"
        section = section_from_params(params)
        crawler = RezkaCrawler(
            page_limit=CRAWLER_LOAD_MORE_PAGE_LIMIT,
            item_limit=CRAWLER_LOAD_MORE_ITEM_LIMIT,
            sleep_seconds=CRAWLER_LOAD_MORE_SLEEP_SECONDS,
            imdb_enabled=CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT > 0,
            imdb_item_limit=CRAWLER_LOAD_MORE_IMDB_ITEM_LIMIT,
            source=source,
            resume=True,
            genre_slugs=genre_slugs,
            section=section,
            filters=filters_from_params(params),
        )
        stats = crawler.run()
    except Exception as exc:
        return _json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
    finally:
        crawl_lock.release()

    return _json(
        HTTPStatus.OK,
        {
            "ok": True,
            "source": source,
            "genreSlugs": genre_slugs,
            "section": section,
            "stats": stats.__dict__,
        },
    )


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


def run(host: str = HOST, port: int = PORT) -> None:
    uvicorn.run("app.server:app", host=host, port=port)
