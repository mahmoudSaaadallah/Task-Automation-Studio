from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.message import Message


class EmailOTPConnector:
    """Read mailbox messages and extract OTP codes."""

    def __init__(self, host: str, username: str, password: str, folder: str = "INBOX") -> None:
        self.host = host
        self.username = username
        self.password = password
        self.folder = folder

    def fetch_latest_otp(
        self,
        *,
        sender_contains: str,
        otp_pattern: str = r"\b(\d{6})\b",
        lookback_minutes: int = 15,
    ) -> str | None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)

        with imaplib.IMAP4_SSL(self.host) as client:
            client.login(self.username, self.password)
            client.select(self.folder)
            status, data = client.search(None, "ALL")
            if status != "OK":
                return None

            message_ids = data[0].split()
            for msg_id in reversed(message_ids):
                status, msg_data = client.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw = msg_data[0][1]
                if not isinstance(raw, bytes):
                    continue

                message = email.message_from_bytes(raw)
                if not isinstance(message, Message):
                    continue

                sender = (message.get("From") or "").lower()
                if sender_contains.lower() not in sender:
                    continue

                date_header = message.get("Date")
                if date_header:
                    try:
                        msg_dt = email.utils.parsedate_to_datetime(date_header)
                        if msg_dt.tzinfo is None:
                            msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                        if msg_dt < cutoff:
                            continue
                    except Exception:
                        continue

                body = self._extract_text_body(message)
                match = re.search(otp_pattern, body)
                if match:
                    return match.group(1)
        return None

    def _extract_text_body(self, message: Message) -> str:
        if message.is_multipart():
            parts: list[str] = []
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True) or b""
                    parts.append(payload.decode(errors="ignore"))
            return "\n".join(parts)

        payload = message.get_payload(decode=True) or b""
        return payload.decode(errors="ignore")
