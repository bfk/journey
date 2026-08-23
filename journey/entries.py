"""Writes journal entries into the entries repo and syncs them to GitHub."""
from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

from . import config


def _run_git(*args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=config.ENTRIES_REPO_PATH,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr}")


def sync_repo() -> None:
    """Pull latest before writing, in case an entry was edited from another device."""
    _run_git("pull", "--ff-only")


def entry_path(date: datetime.date) -> Path:
    return config.ENTRIES_REPO_PATH / "entries" / str(date.year) / f"{date.isoformat()}.md"


def append_entry(date: datetime.date, prompt_text: str, reply_text: str) -> Path:
    path = entry_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        # A second reply arriving the same day -- add it under the same entry.
        with path.open("a") as f:
            f.write(f"\n---\n\n{reply_text}\n")
    else:
        path.write_text(f"# {date.isoformat()}\n\n**Prompt:** {prompt_text}\n\n{reply_text}\n")

    return path


def commit_and_push(message: str) -> bool:
    """Stages and pushes everything changed in the entries repo (entries and/or
    .state/state.json). Returns True if there was something to commit."""
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=config.ENTRIES_REPO_PATH,
        check=True,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        return False

    _run_git("add", "-A")
    _run_git("commit", "-m", message)
    _run_git("push")
    return True
