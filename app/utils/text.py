from __future__ import annotations

import re
from typing import Any


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def split_csv(value: str) -> list[str]:
    parts = re.split(r"[,/]| \u0438 ", value)
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
        "\u0430": "a",
        "\u0431": "b",
        "\u0432": "v",
        "\u0433": "g",
        "\u0434": "d",
        "\u0435": "e",
        "\u0451": "e",
        "\u0436": "zh",
        "\u0437": "z",
        "\u0438": "i",
        "\u0439": "y",
        "\u043a": "k",
        "\u043b": "l",
        "\u043c": "m",
        "\u043d": "n",
        "\u043e": "o",
        "\u043f": "p",
        "\u0440": "r",
        "\u0441": "s",
        "\u0442": "t",
        "\u0443": "u",
        "\u0444": "f",
        "\u0445": "h",
        "\u0446": "ts",
        "\u0447": "ch",
        "\u0448": "sh",
        "\u0449": "sch",
        "\u044a": "",
        "\u044b": "y",
        "\u044c": "",
        "\u044d": "e",
        "\u044e": "yu",
        "\u044f": "ya",
    }
    return "".join(table.get(char.casefold(), char) for char in value)
