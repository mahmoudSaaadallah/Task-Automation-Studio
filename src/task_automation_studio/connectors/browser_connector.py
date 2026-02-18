from __future__ import annotations

from collections.abc import Callable
from typing import Any


class PlaywrightBrowserConnector:
    """Action router for browser operations.

    Handlers can be registered per action to keep workflow logic externalized.
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register_action_handler(
        self,
        action: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._handlers[action] = handler

    def run_action(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(action)
        if handler is None:
            raise ValueError(f"No browser handler registered for action '{action}'.")

        response = handler(payload)
        if "verified" not in response:
            response["verified"] = False
        response["action"] = action
        return response
