from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TeachSessionStatus(StrEnum):
    RECORDING = "recording"
    FINISHED = "finished"


class TeachEventType(StrEnum):
    OPEN_URL = "open_url"
    CLICK = "click"
    FILL = "fill"
    WAIT_FOR = "wait_for"
    MOUSE_CLICK = "mouse_click"
    MOUSE_SCROLL = "mouse_scroll"
    KEY_PRESS = "key_press"
    CLIPBOARD_COPY = "clipboard_copy"
    CLIPBOARD_PASTE = "clipboard_paste"
    WINDOW_SWITCH = "window_switch"
    CHECKPOINT = "checkpoint"


class TeachEventData(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: TeachEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    sensitive: bool = False
    timestamp: datetime


class TeachSessionData(BaseModel):
    session_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: TeachSessionStatus = TeachSessionStatus.RECORDING
    started_at: datetime
    finished_at: datetime | None = None
    events: list[TeachEventData] = Field(default_factory=list)
