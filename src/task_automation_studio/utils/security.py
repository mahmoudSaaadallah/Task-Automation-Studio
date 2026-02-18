from __future__ import annotations

import keyring


class SecretStore:
    """Wrapper for OS keychain/keyring storage."""

    def __init__(self, service_name: str = "task_automation_studio") -> None:
        self.service_name = service_name

    def set_secret(self, key: str, value: str) -> None:
        keyring.set_password(self.service_name, key, value)

    def get_secret(self, key: str) -> str | None:
        return keyring.get_password(self.service_name, key)

    def delete_secret(self, key: str) -> None:
        try:
            keyring.delete_password(self.service_name, key)
        except keyring.errors.PasswordDeleteError:
            return
