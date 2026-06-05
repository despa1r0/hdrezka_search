from __future__ import annotations

import argparse
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import (
    REZKA_ACCEPT_LANGUAGE,
    REZKA_COOKIE_FILE,
    REZKA_COOKIE_REFRESH_ENABLED,
    REZKA_COOKIE_REFRESH_HOUR,
    REZKA_COOKIE_REFRESH_MINUTE,
    REZKA_COOKIE_REFRESH_URL,
    REZKA_COOKIE_REFRESH_WRITE_ENV,
    ROOT_DIR,
    USER_AGENT,
)
from app.notifier import notify_exception, send_telegram_alert

_scheduler_started = False


def refresh_rezka_cookie(*, headless: bool = True, write_env: bool | None = None) -> str:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    cookie_value = ""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                user_agent=USER_AGENT,
                locale=_locale_from_accept_language(REZKA_ACCEPT_LANGUAGE),
                extra_http_headers={"Accept-Language": REZKA_ACCEPT_LANGUAGE},
            )
            page = context.new_page()
            page.goto(REZKA_COOKIE_REFRESH_URL, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass

            cookies = context.cookies()
            cookie_value = _format_cookie_header(cookies)
        finally:
            browser.close()

    if not cookie_value:
        raise RuntimeError("Playwright did not collect Rezka cookies")

    _write_cookie_file(cookie_value)
    should_write_env = REZKA_COOKIE_REFRESH_WRITE_ENV if write_env is None else write_env
    if should_write_env:
        _update_local_env_cookie(cookie_value)
    return cookie_value


def start_cookie_refresh_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started or not REZKA_COOKIE_REFRESH_ENABLED:
        return

    _scheduler_started = True
    thread = threading.Thread(target=_scheduler_loop, name="rezka-cookie-refresh", daemon=True)
    thread.start()


def _scheduler_loop() -> None:
    while True:
        time.sleep(_seconds_until_next_refresh())
        try:
            refresh_rezka_cookie()
            send_telegram_alert("HdRezka cookie refresh: ok")
        except Exception as exc:
            notify_exception("Rezka cookie refresh failed", exc)
            time.sleep(300)


def _seconds_until_next_refresh() -> float:
    now = datetime.now()
    target = now.replace(
        hour=max(0, min(23, REZKA_COOKIE_REFRESH_HOUR)),
        minute=max(0, min(59, REZKA_COOKIE_REFRESH_MINUTE)),
        second=0,
        microsecond=0,
    )
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def _format_cookie_header(cookies: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for cookie in cookies:
        domain = str(cookie.get("domain") or "").lstrip(".").lower()
        if "rezka" not in domain:
            continue
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def _write_cookie_file(cookie_value: str) -> None:
    path = Path(REZKA_COOKIE_FILE)
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cookie_value.strip() + "\n", encoding="utf-8")


def _update_local_env_cookie(cookie_value: str) -> None:
    env_path = ROOT_DIR / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("REZKA_COOKIE="):
            output.append(f"REZKA_COOKIE={cookie_value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"REZKA_COOKIE={cookie_value}")
    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _locale_from_accept_language(value: str) -> str:
    first = value.split(",", 1)[0].strip()
    return first or "en-US"


def run_refresh(args: argparse.Namespace) -> None:
    cookie = refresh_rezka_cookie(headless=not args.headed, write_env=args.write_env)
    print(f"Cookie refreshed: {len(cookie)} chars written to {REZKA_COOKIE_FILE}")


def run_daemon(_: argparse.Namespace) -> None:
    print(
        "Cookie refresh daemon started: "
        f"{REZKA_COOKIE_REFRESH_URL} at {REZKA_COOKIE_REFRESH_HOUR:02d}:{REZKA_COOKIE_REFRESH_MINUTE:02d}"
    )
    while True:
        time.sleep(_seconds_until_next_refresh())
        try:
            cookie = refresh_rezka_cookie()
            print(f"Cookie refreshed: {len(cookie)} chars written to {REZKA_COOKIE_FILE}")
            send_telegram_alert("HdRezka cookie refresh: ok")
        except Exception as exc:
            print(f"Cookie refresh failed: {type(exc).__name__}: {exc}")
            notify_exception("Rezka cookie refresh daemon failed", exc)
            time.sleep(300)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh Rezka cookies with Playwright.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh_parser = subparsers.add_parser("refresh", help="Refresh cookies once")
    refresh_parser.add_argument("--headed", action="store_true", help="Run Chromium with a visible window")
    refresh_parser.add_argument(
        "--write-env",
        action="store_true",
        help="Also replace REZKA_COOKIE in local .env",
    )
    refresh_parser.set_defaults(func=run_refresh)

    daemon_parser = subparsers.add_parser("daemon", help="Refresh cookies daily in a foreground loop")
    daemon_parser.set_defaults(func=run_daemon)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
