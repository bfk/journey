"""Loads settings from .env (repo root) and environment variables."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(REPO_ROOT / ".env")


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required setting: {name} (set it in .env)")
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _require("TELEGRAM_CHAT_ID")
ENTRIES_REPO_PATH = Path(_require("ENTRIES_REPO_PATH")).expanduser()

# Local wall-clock hour (0-23) at which the daily prompt should go out.
TIMEZONE = os.environ.get("JOURNEY_TIMEZONE", "Europe/London")
SEND_HOUR_LOCAL = int(os.environ.get("JOURNEY_SEND_HOUR", "19"))

# Optional: only present in the GitHub Actions run (not local manual testing),
# used solely for the PAT-expiry health check in journey/health.py -- the
# same token git already uses via actions/checkout's credential helper, just
# also readable here for one extra read-only API call.
ENTRIES_REPO_TOKEN = os.environ.get("ENTRIES_REPO_TOKEN")
ENTRIES_REPO = os.environ.get("ENTRIES_REPO")

# State lives inside the entries repo (not this one) so it survives across
# ephemeral CI runners via git commits, instead of relying on local disk.
STATE_DIR = ENTRIES_REPO_PATH / ".state"
STATE_FILE = STATE_DIR / "state.json"
PROMPTS_FILE = REPO_ROOT / "prompts.json"
