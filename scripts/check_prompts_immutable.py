"""Fails if any existing prompts.json id's text changed since the last push.

Why this matters: state.json (in the entries repo) only ever stores a sent
prompt's id, never its text -- entries.py resolves the actual wording fresh
from prompts.json at write time, intentionally, so a tampered or corrupted
state.json can't inject arbitrary text into an entry (see README Security
notes). The cost of that design: if an existing id's *wording* changes
between when a prompt is sent and when its reply gets processed -- up to
about a day, given the once-daily cadence and hourly polling -- the reply
ends up logged against whatever text that id resolves to *now*, not what
was actually sent. Adding a new id, or deleting one outright, is always
safe (a deleted id just falls back to a placeholder for any in-flight
reference); editing an existing id's text is the one unsafe move. This
check makes that a hard CI failure instead of a rule to remember.
"""
import json
import subprocess
import sys

ZERO_SHA = "0" * 40


def load_prompts(text: str) -> dict[str, str]:
    return {p["id"]: p["text"] for p in json.loads(text)}


def main() -> int:
    before_sha = sys.argv[1] if len(sys.argv) > 1 else "HEAD^"

    if before_sha == ZERO_SHA:
        print("First push to this branch -- nothing to compare against.")
        return 0

    verify = subprocess.run(["git", "rev-parse", "--verify", before_sha], capture_output=True, text=True)
    if verify.returncode != 0:
        print(f"Can't resolve {before_sha!r} -- skipping (likely a fresh/shallow history).")
        return 0

    old_text = subprocess.run(["git", "show", f"{before_sha}:prompts.json"], capture_output=True, text=True)
    if old_text.returncode != 0:
        print("prompts.json didn't exist before this push -- nothing to check.")
        return 0

    with open("prompts.json") as f:
        new_prompts = load_prompts(f.read())
    old_prompts = load_prompts(old_text.stdout)

    changed = [pid for pid, text in old_prompts.items() if pid in new_prompts and new_prompts[pid] != text]
    if changed:
        print("prompts.json: the following ids changed text since the last push:")
        for pid in changed:
            print(f"  {pid}:")
            print(f"    was: {old_prompts[pid]!r}")
            print(f"    now: {new_prompts[pid]!r}")
        print(
            "\nExisting prompt ids must never change text -- a prompt already sent "
            "but not yet replied to would retroactively be recorded under the new "
            "wording. Add a new id for a reworded question instead, or delete this "
            "one outright (safe -- any in-flight reference just falls back to a "
            "placeholder)."
        )
        return 1

    print("prompts.json: no existing id's text changed. OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
