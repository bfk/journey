"""Minimal Telegram Bot API client. Stdlib only."""
from __future__ import annotations

import json
import urllib.request
import urllib.parse
from typing import Any


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str):
        self._base = f"https://api.telegram.org/bot{token}"

    def _call(self, method: str, params: dict[str, Any]) -> Any:
        url = f"{self._base}/{method}"
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        if not body.get("ok"):
            raise TelegramError(f"{method} failed: {body}")
        return body["result"]

    def send_message(self, chat_id: str, text: str) -> dict:
        """Returns the sent Message object (includes message_id), so callers
        can record which message a future Telegram reply-to might target."""
        return self._call("sendMessage", {"chat_id": chat_id, "text": text})

    def get_updates(self, offset: int | None = None) -> list[dict]:
        params: dict[str, Any] = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        return self._call("getUpdates", params)
