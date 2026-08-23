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


def _current_branch() -> str:
    # symbolic-ref (not rev-parse --abbrev-ref) because it works even on a
    # brand-new repo with zero commits yet, where HEAD doesn't resolve to a
    # commit at all but still points at a branch name.
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=config.ENTRIES_REPO_PATH,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git symbolic-ref --short HEAD failed:\n{result.stderr}")
    return result.stdout.strip()


def _remote_branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        cwd=config.ENTRIES_REPO_PATH,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 2:  # git's documented "no matching refs" exit code
        return False
    raise RuntimeError(f"git ls-remote failed:\n{result.stderr}")


def sync_repo() -> None:
    """Pull latest before writing, in case an entry was edited from another device.

    Pulls by explicit remote+branch rather than relying on upstream tracking
    being configured, and skips cleanly (rather than erroring) if the entries
    repo is still brand new with nothing pushed to it yet -- there's simply
    nothing to pull in that case, not a failure.
    """
    branch = _current_branch()
    if not _remote_branch_exists(branch):
        return
    _run_git("pull", "--ff-only", "origin", branch)


def entry_path(date: datetime.date) -> Path:
    return config.ENTRIES_REPO_PATH / "entries" / str(date.year) / f"{date.isoformat()}.md"


def append_entry(date: datetime.date, prompt_text: str, reply_text: str) -> Path:
    """Appends a prompt+reply block to the day's entry file, always labeling
    which prompt it answers -- even on a later append to an already-existing
    file, since a given day can have more than one prompt (e.g. a manually
    forced prompt alongside the scheduled one), and a block with no label
    silently reads as answering whatever prompt came first that day."""
    path = entry_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    block = f"**Prompt:** {prompt_text}\n\n{reply_text}\n"

    if path.exists():
        with path.open("a") as f:
            f.write(f"\n---\n\n{block}")
    else:
        path.write_text(f"# {date.isoformat()}\n\n{block}")

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
    # -u sets upstream tracking on the first push (a fresh entries repo starts
    # with none), and is a harmless no-op on every push after that.
    _run_git("push", "-u", "origin", _current_branch())
    return True
