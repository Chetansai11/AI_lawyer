from __future__ import annotations

from datetime import datetime


def agent_log(agent: str, message: str) -> str:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    return f"{timestamp} [{agent}] {message}"
