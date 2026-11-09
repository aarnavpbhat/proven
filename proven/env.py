"""Read a `.env` file into the environment. Standard library only.

Keys already set in the real environment win, so a shell export always overrides
the file. Nothing here is required: the offline core reads no configuration.
"""
from __future__ import annotations

import os
from pathlib import Path


def parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            values[key] = value
    return values


def load(path: str | Path | None = None) -> list[str]:
    """Set every key from `path` that the environment does not already define.

    `path` defaults to $PROVEN_ENV_FILE, then `.env` in the working directory.
    Returns the names it set (never the values). A missing file is not an error.
    """
    file = Path(path or os.environ.get("PROVEN_ENV_FILE") or ".env")
    if not file.is_file():
        return []
    applied = []
    for key, value in parse(file.read_text(encoding="utf-8")).items():
        if value and key not in os.environ:
            os.environ[key] = value
            applied.append(key)
    return applied
