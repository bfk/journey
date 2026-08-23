"""Daily journey run: collect any new reply, commit it, and send tonight's
question once it's actually evening in the configured local timezone.

Meant to be triggered hourly (e.g. by a GitHub Actions cron), not exactly at
the target hour -- the hour gate below is what actually decides whether to
send, so drift, missed runs, and DST are all handled without special-casing.
All state that needs to survive between runs lives in .state/state.json
inside the entries repo, since it's committed and pushed like any entry.

A reply is attributed to a prompt in one of two ways: if it's an explicit
Telegram "reply" (quoting a specific past message), it's attached to whatever
prompt that message actually was, even if newer prompts have gone out since
-- this is what lets you answer something you missed a few days ago. Any
other message is assumed to be answering the most recent prompt, since
that's what a plain (non-reply) message in a one-question-a-day chat means.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from zoneinfo import ZoneInfo

from . import config, entries, prompts, state as state_mod
from .telegram_client import TelegramClient


def _resolve_target(message: dict, st: dict) -> dict | None:
    reply_to = message.get("reply_to_message")
    if reply_to:
        sent_record = st.get("sent_prompts", {}).get(str(reply_to.get("message_id")))
        if sent_record:
            return sent_record
    return st.get("last_prompt")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Send tonight's prompt even if it's not yet the target hour, or one was already sent today.",
    )
    args = parser.parse_args()

    entries.sync_repo()

    client = TelegramClient(config.TELEGRAM_BOT_TOKEN)
    st = state_mod.load()
    now_local = datetime.datetime.now(ZoneInfo(config.TIMEZONE))
    today = now_local.date()

    updates = client.get_updates(offset=st.get("telegram_offset"))
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

    already_sent_today = st.get("last_prompt") and st["last_prompt"]["date"] == today.isoformat()
    time_to_send = now_local.hour >= config.SEND_HOUR_LOCAL

    if args.force or (time_to_send and not already_sent_today):
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

    state_mod.prune_sent_prompts(st, today)
    state_mod.save(st)
    message = ", ".join(commit_message_parts) if commit_message_parts else "journey: update state"
    wrote = entries.commit_and_push(message)
    print(f"{'Pushed' if wrote else 'Nothing to push'} ({message}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
