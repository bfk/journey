"""Picks the next journaling question, avoiding recent repeats."""
from __future__ import annotations

import json
import random

from . import config


def load_all() -> list[dict]:
    return json.loads(config.PROMPTS_FILE.read_text())


def get_by_id(question_id: str) -> dict | None:
    """Resolves a question id against the authoritative library. Used when
    writing an entry so the prompt text always comes from prompts.json at
    write-time, never from a copy cached in state."""
    for p in load_all():
        if p["id"] == question_id:
            return p
    return None


def pick_next(recent_ids: list[str]) -> dict:
    prompts = load_all()
    recent = set(recent_ids)
    candidates = [p for p in prompts if p["id"] not in recent]
    if not candidates:
        # Exhausted the "recent" window (or the whole library) -- start over.
        candidates = prompts
    return random.choice(candidates)
