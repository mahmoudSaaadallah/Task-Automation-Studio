from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    app_name: str = "Task Automation Studio"
    database_url: str = "sqlite:///data/app.db"
    log_dir: Path = Path("logs")
    artifacts_dir: Path = Path("artifacts")
    default_safe_stop_error_rate: float = 0.2

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("TAS_DATABASE_URL", "sqlite:///data/app.db")
        safe_stop_raw = os.getenv("TAS_SAFE_STOP_ERROR_RATE", "0.2")
        try:
            safe_stop = float(safe_stop_raw)
        except ValueError:
            safe_stop = 0.2
        return cls(database_url=database_url, default_safe_stop_error_rate=max(0.0, min(1.0, safe_stop)))
