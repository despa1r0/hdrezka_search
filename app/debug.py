from __future__ import annotations

import sys

from app.config import DEBUG


def debug_log(message: str, enabled: bool = False) -> None:
    if DEBUG or enabled:
        output = f"[debug] {message}\n"
        encoding = sys.stdout.encoding or "utf-8"
        sys.stdout.buffer.write(output.encode(encoding, errors="backslashreplace"))
        sys.stdout.flush()
