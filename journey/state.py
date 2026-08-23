"""Run state: Telegram update offset, sent-prompt history, recent question history.

Lives at .state/state.json inside the entries repo (config.STATE_FILE) so it
survives across ephemeral CI runners via git commits, not local disk.

`sent_prompts` maps a Telegram message_id (as a string, since JSON object
keys are always strings) to the {date, question_id} it represents, so an
explicit Telegram "reply" to an older prompt can be attributed to the right
day even after later prompts have gone out. `last_prompt` is just the most
recently sent one, kept separately since it's also used as the "have we
already sent today" check and as the fallback target for replies that
aren't an explicit Telegram reply-to.
"""
from __future__ import annotations

import datetime
import json
from typing import Any

from . import config

MAX_RECENT_QUESTIONS = 30
SENT_PROMPT_RETENTION_DAYS = 180


def load() -> dict[str, Any]:
    if not config.STATE_FILE.exists():
        return {
            "telegram_offset": None,
            "last_prompt": None,
            "recent_question_ids": [],
            "sent_prompts": {},
        }
    try:
        state = json.loads(config.STATE_FILE.read_text())
    except json.JSONDecodeError as exc:
        # Unlike a transient network blip, this doesn't self-heal -- every
        # run will fail here identically until the file is actually fixed.
        # Worth a clear, actionable message rather than a bare traceback.
        raise RuntimeError(
            f"{config.STATE_FILE} is corrupted and can't be parsed as JSON ({exc}). "
            "This won't fix itself on the next run. Either edit the file directly, "
            "or restore the last good version from git history: "
            "`git log --oneline -- .state/state.json`, then "
            "`git checkout <sha> -- .state/state.json`."
        ) from exc
    state.setdefault("sent_prompts", {})
    return state


def save(state: dict[str, Any]) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def record_question_used(state: dict[str, Any], question_id: str) -> None:
    recent = state.setdefault("recent_question_ids", [])
    recent.insert(0, question_id)
    del recent[MAX_RECENT_QUESTIONS:]


def record_sent_prompt(state: dict[str, Any], message_id: int, date: str, question_id: str) -> None:
    state.setdefault("sent_prompts", {})[str(message_id)] = {"date": date, "question_id": question_id}


def prune_sent_prompts(state: dict[str, Any], today: datetime.date) -> None:
    cutoff = today - datetime.timedelta(days=SENT_PROMPT_RETENTION_DAYS)
    sent = state.get("sent_prompts", {})
    state["sent_prompts"] = {
        message_id: record
        for message_id, record in sent.items()
        if datetime.date.fromisoformat(record["date"]) >= cutoff
    }
