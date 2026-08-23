"""One-off setup helper.

Message your bot on Telegram first (anything, e.g. "hi"), then run this
script to print the chat_id you need to put in .env as TELEGRAM_CHAT_ID.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from journey.telegram_client import TelegramClient  # noqa: E402

token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    # .env may not be loaded yet since TELEGRAM_CHAT_ID isn't set -- read the token directly.
    env_path = Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"').strip("'")

if not token:
    print("Set TELEGRAM_BOT_TOKEN in .env first.")
    sys.exit(1)

client = TelegramClient(token)
updates = client.get_updates()
if not updates:
    print("No messages found. Send your bot a message on Telegram, then rerun this script.")
    sys.exit(1)

seen = {}
for update in updates:
    message = update.get("message")
    if not message:
        continue
    chat = message["chat"]
    seen[chat["id"]] = chat

for chat_id, chat in seen.items():
    label = chat.get("username") or chat.get("first_name") or "unknown"
    print(f"chat_id={chat_id}  ({label})")
