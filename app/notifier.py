from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from app.config import TELEGRAM_ALERTS_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_alert(message: str, *, disable_web_page_preview: bool = True) -> bool:
    if not TELEGRAM_ALERTS_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    text = message.strip()
    if not text:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:3900],
        "disable_web_page_preview": disable_web_page_preview,
    }
    try:
        response = requests.post(url, json=payload, timeout=8)
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


def notify_exception(context: str, exc: BaseException, *, extra: dict[str, Any] | None = None) -> bool:
    details = [
        "HdRezka alert",
        f"time: {datetime.now().isoformat(timespec='seconds')}",
        f"context: {context}",
        f"error: {type(exc).__name__}: {exc}",
    ]
    if extra:
        rendered_extra = ", ".join(f"{key}={value}" for key, value in extra.items())
        details.append(f"extra: {rendered_extra}")
    return send_telegram_alert("\n".join(details))
