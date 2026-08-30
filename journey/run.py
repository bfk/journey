"""journey has two independent commands, run as separate scheduled workflows
because they have fundamentally different tolerance for a missed or delayed
run:

- `send`: must fire within a narrow evening window, or that day's prompt is
  permanently lost (recoverable only via --backfill-date). Scheduled
  sparingly and deliberately -- a handful of fires in the evening window --
  precisely because what matters is that it actually fires, not that it
  fires often.
- `poll`: fetches Telegram replies and commits them. A late or occasionally
  skipped poll only delays when a reply becomes visible -- nothing is lost,
  since Telegram's own update offset and this app's reply-to-prompt
  attribution are both idempotent regardless of when a poll actually runs.
  Can be scheduled as frequently as wanted without a correctness cost.

Both share the same state.json in the entries repo and must never run
concurrently against it -- see the shared concurrency group in both
workflow files. Ownership within state.json is split cleanly: `send` is the
only writer of last_prompt, sent_prompts, recent_question_ids, and
last_pat_warning_date; `poll` is the only writer of telegram_offset, and
only ever reads (never writes) last_prompt/sent_prompts.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from zoneinfo import ZoneInfo

from . import config, entries, health, prompts, state as state_mod
from .telegram_client import TelegramClient


def _resolve_target(message: dict, st: dict) -> dict | None:
    reply_to = message.get("reply_to_message")
    if reply_to:
        sent_record = st.get("sent_prompts", {}).get(str(reply_to.get("message_id")))
        if sent_record:
            return sent_record
    return st.get("last_prompt")


def _poll(client: TelegramClient, st: dict) -> list[str]:
    updates = client.get_all_updates(offset=st.get("telegram_offset"))
    replies_by_date: dict[str, list[str]] = {}
    question_id_by_date: dict[str, str] = {}
    max_update_id = None
    skipped_unattributed = 0

    for update in updates:
        max_update_id = update["update_id"]
        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        if str(message.get("chat", {}).get("id")) != str(config.TELEGRAM_CHAT_ID):
            continue
        text = message.get("text")
        if not text:
            continue

        target = _resolve_target(message, st)
        if target is None:
            skipped_unattributed += 1
            continue

        replies_by_date.setdefault(target["date"], []).append(text)
        question_id_by_date[target["date"]] = target["question_id"]

    if max_update_id is not None:
        st["telegram_offset"] = max_update_id + 1

    commit_message_parts = []
    for date_str in sorted(replies_by_date):
        entry_date = datetime.date.fromisoformat(date_str)
        # Resolve the prompt text from prompts.json now, by id -- never trust
        # free text cached in state.json, which lives in a repo state.py
        # itself doesn't control the integrity of.
        prompt = prompts.get_by_id(question_id_by_date[date_str])
        prompt_text = prompt["text"] if prompt else "(original prompt no longer in prompts.json)"
        entries.append_entry(entry_date, prompt_text, "\n".join(replies_by_date[date_str]))
        commit_message_parts.append(f"entry: {date_str}")
        print(f"Recorded reply for {date_str}.")

    if not replies_by_date:
        if skipped_unattributed:
            print(f"Got {skipped_unattributed} message(s) but no prompt on record to attach them to; skipping.")
        else:
            print("No new reply since last run.")

    return commit_message_parts


def _send(client: TelegramClient, st: dict, now_local: datetime.datetime, force: bool) -> list[str]:
    today = now_local.date()
    commit_message_parts = []

    already_sent_today = st.get("last_prompt") and st["last_prompt"]["date"] == today.isoformat()
    time_to_send = now_local.hour >= config.SEND_HOUR_LOCAL

    if force or (time_to_send and not already_sent_today):
        question = prompts.pick_next(st.get("recent_question_ids", []))
        sent_message = client.send_message(config.TELEGRAM_CHAT_ID, question["text"])
        state_mod.record_question_used(st, question["id"])
        st["last_prompt"] = {"date": today.isoformat(), "question_id": question["id"]}
        state_mod.record_sent_prompt(st, sent_message["message_id"], today.isoformat(), question["id"])
        commit_message_parts.append(f"prompt: {today.isoformat()}")
        print(f"Sent prompt {question['id']} for {today.isoformat()}.")
    elif already_sent_today:
        print(f"Already sent today's prompt ({today.isoformat()}); nothing more to do.")
    else:
        print(f"Not sending yet (local time {now_local:%H:%M}, target hour {config.SEND_HOUR_LOCAL}).")

    try:
        pat_warning = health.check_pat_expiry()
    except Exception as exc:
        # Belt and braces on top of health.py's own broad catch: a health
        # check must never take down the actual journaling flow, even if a
        # future change to health.py forgets to honor that itself.
        print(f"PAT-expiry check failed unexpectedly, skipping it: {exc}")
        pat_warning = None
    if pat_warning and st.get("last_pat_warning_date") != today.isoformat():
        # A standalone status message, not attached to any prompt_id -- it's
        # about the system, not something to reply to or attribute an entry to.
        client.send_message(config.TELEGRAM_CHAT_ID, pat_warning)
        st["last_pat_warning_date"] = today.isoformat()
        print("Sent PAT-expiry warning.")

    state_mod.prune_sent_prompts(st, today)
    return commit_message_parts


def _backfill(client: TelegramClient, st: dict, backfill_date: datetime.date) -> list[str]:
    question = prompts.pick_next(st.get("recent_question_ids", []))
    sent_message = client.send_message(
        config.TELEGRAM_CHAT_ID,
        f"(Backfilling {backfill_date.isoformat()}) {question['text']}",
    )
    state_mod.record_question_used(st, question["id"])
    # Deliberately not touching last_prompt: that stays pointed at today's
    # real prompt (or none), so a plain non-reply message still defaults
    # to today as normal. Only an explicit reply-to on this specific
    # message resolves to the backfilled date, via sent_prompts.
    state_mod.record_sent_prompt(st, sent_message["message_id"], backfill_date.isoformat(), question["id"])
    print(
        f"Sent backfill prompt {question['id']} for {backfill_date.isoformat()} "
        f"(message_id={sent_message['message_id']}). Reply to that message using "
        f"Telegram's reply action to attribute it correctly."
    )
    return [f"backfill prompt: {backfill_date.isoformat()}"]


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    send_parser = subparsers.add_parser("send", help="Send today's prompt if it's time.")
    send_parser.add_argument(
        "--force",
        action="store_true",
        help="Send even if it's not yet the target hour, or one was already sent today.",
    )
    send_parser.add_argument(
        "--backfill-date",
        metavar="YYYY-MM-DD",
        help="Send a fresh prompt now, but attribute it to this past date instead of today "
        "-- for rebuilding a day the schedule skipped. Reply using Telegram's reply action "
        "on that specific message (not a plain message) to land it correctly. Does nothing "
        "else in this run.",
    )

    subparsers.add_parser("poll", help="Fetch and commit any new Telegram replies.")

    args = parser.parse_args()

    entries.sync_repo()
    client = TelegramClient(config.TELEGRAM_BOT_TOKEN)
    st = state_mod.load()

    if args.command == "poll":
        commit_message_parts = _poll(client, st)
    elif args.backfill_date:
        commit_message_parts = _backfill(client, st, datetime.date.fromisoformat(args.backfill_date))
    else:
        now_local = datetime.datetime.now(ZoneInfo(config.TIMEZONE))
        commit_message_parts = _send(client, st, now_local, args.force)

    state_mod.save(st)
    message = ", ".join(commit_message_parts) if commit_message_parts else "journey: update state"
    wrote = entries.commit_and_push(message)
    print(f"{'Pushed' if wrote else 'Nothing to push'} ({message}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
