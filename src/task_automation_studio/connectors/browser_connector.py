from __future__ import annotations

from typing import Any


class PlaywrightBrowserConnector:
    """Thin wrapper around Playwright calls for reusable browser actions."""

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless

    def run_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one browser action.

        This method is intentionally minimal for scaffold stage.
        Concrete workflow executors will map step.action to target selectors and interactions.
        """
        return {"action": action, "payload": payload, "verified": False}
