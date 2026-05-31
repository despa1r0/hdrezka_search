from __future__ import annotations

import re
from typing import Any


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def split_csv(value: str) -> list[str]:
    parts = re.split(r"[,/]| и ", value)
    return [part.strip() for part in parts if part.strip()]


def parse_rating(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    if not match:
        return None

    return float(match.group(0).replace(",", "."))


def parse_year(*values: str) -> str:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", " ".join(values))
    return match.group(1) if match else ""


def get_attr(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def transliterate(value: str) -> str:
    table = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    return "".join(table.get(char.casefold(), char) for char in value)
