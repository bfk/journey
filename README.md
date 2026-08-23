# journey

A low-key daily journaling prompt over Telegram. Every evening it sends you an
open-ended question; whenever you reply, your answer gets committed as a dated
entry to a private GitHub repo you control. No server to run and no
third-party SaaS holding your journal — a script, a Telegram bot, git, and
GitHub Actions to trigger it.

## How it works

- `prompts.json` is a library of open-ended questions. Each run picks one at
  random, avoiding the last 30 used. **Existing ids' text must never change**
  once added -- add a new id for a reworded question, or delete one outright
  (safe; an in-flight reference just falls back to a placeholder). Editing
  existing wording is unsafe because entries.py always resolves a prompt's
  text fresh from this file *at reply-write time*, by id, not from whatever
  was actually shown when it was sent (that's deliberate -- see Security
  notes) -- so a same-day edit can retroactively relabel a reply that's
  already in flight. `.github/workflows/check-prompts.yml` enforces this
  automatically on every push that touches the file.
- `journey/run.py` is the whole program: it checks Telegram for any new
  reply, commits it to the entries repo, and sends tonight's question once
  it's actually evening in your timezone.
- It runs on **GitHub Actions**, not your laptop — see [Why GitHub Actions,
  not a local cron job](#why-github-actions-not-a-local-cron-job) below for
  why that matters for you specifically.
- The workflow triggers **hourly**, but only actually sends once a day: the
  script itself checks the current local wall-clock time (`JOURNEY_TIMEZONE` /
  `JOURNEY_SEND_HOUR` in [.github/workflows/daily.yml](.github/workflows/daily.yml))
  and only sends past that hour, once, per local calendar day. This sidesteps
  GitHub's cron being UTC-only with no DST awareness, and as a side effect a
  reply gets picked up and committed within about an hour instead of waiting
  a full day.
- State that needs to survive between runs (which Telegram messages have
  already been processed, which questions were recently asked, when the
  last prompt went out) lives in `.state/state.json` **inside the entries
  repo**, so it persists via git commits rather than local disk — the
  Actions runner is thrown away after every run.
- Journal entries live in a **separate** private repo (`<entries-repo>`),
  not in this one, so the code (which could be shared or made public) never
  mixes with your journal content.
- A reply is normally assumed to answer the most recent prompt — that's the
  right default for a plain message in a one-question-a-day chat. But if you
  use Telegram's own **reply** action (swipe on, or long-press and choose
  Reply) to quote an older prompt specifically, that reply gets attributed to
  the day it actually answers, even if newer prompts have since gone out.
  That's what lets you catch up on a prompt you missed a few days ago without
  it landing under today's date. State tracks the last 180 days of
  prompt-message-id → date/question mappings to make this possible
  (`journey/state.py`).

## Why GitHub Actions, not a local cron job

The obvious-seeming alternative — a `launchd`/cron job on a personal machine,
or a Claude Code scheduled task — only fires while that machine is awake (and
for the Claude Code option, while the app itself is open). That means the
whole setup's reliability would depend on one particular computer being on
and unlocked at prompt time every single day, which defeats the point of a
low-maintenance daily habit. Running the trigger on GitHub Actions instead
means there's no server to keep running or machine that has to stay awake at
all — it fires on GitHub's infrastructure regardless of what device you're
using or whether anything you own is even powered on, using free-tier cloud
compute instead of infrastructure you'd have to stand up and maintain
yourself. The only cost is that entries and run state need to live in git
(already true) rather than local disk, since the runner that executes each
run is thrown away immediately afterward.

## One-time setup

### 1. Create the Telegram bot

**Searching for "BotFather" in Telegram is not safe** — Telegram's in-app
search matches the display name, which anyone can set to anything, not the
`@username`, which is the only part that's actually unique and can't be
faked. Search for it and you'll find several impostor accounts with names
like "BotFather" but a completely different underlying `@username` (e.g.
`@Botfagher_bot`) — these are phishing accounts, not typos or unofficial
clones.

Instead:

1. Open **[t.me/BotFather](https://t.me/BotFather)** directly (in a browser
   or by typing that exact address into Telegram) rather than using search.
   Telegram usernames are globally unique, so this link can only ever open
   the one account that actually holds the username `BotFather` — the
   phishing accounts hold different usernames entirely and can't intercept
   it. Once open, double-check the `@username` shown in the chat header
   reads exactly `BotFather` and that it carries Telegram's verified badge.
2. Send it `/newbot`.
3. Give it a name and a username (must end in `bot`, e.g. `my_journey_bot`).
4. BotFather gives you a token like `123456789:AAExampleTokenNotReal` — save
   it. The real BotFather will never ask you to log in anywhere, enter your
   Telegram password, or forward a login code — it only ever talks to you
   through bot commands like `/newbot`. If anything claiming to be BotFather
   asks for those, it's one of the impostors, regardless of what its display
   name says.
5. Send your new bot any message (e.g. "hi") so it knows who you are.

### 2. Install and authenticate the GitHub CLI

```bash
brew install gh
gh auth login
```

Run `gh auth login` yourself in a terminal — it's an interactive browser
sign-in and shouldn't be run through anything else.

### 3. Create the two repos

These two commands need to run from **different directories** — don't run
them back to back from the same spot.

**`journey` (code)**: run this from the root of *this* project — the folder
containing this README, `prompts.json`, `.github/`, and the `journey/`
package folder as siblings (i.e. `.git` already lives here; this is not the
same as the `journey/` package folder one level down, which just holds the
`.py` files). It holds no personal data or secrets (see "Security notes"
below), so `--public` is a reasonable default if you'd like the code to be
shareable; swap in `--private` instead if you'd simply rather not:

```bash
gh repo create journey --public --source=. --remote=origin --push
```

**`<entries-repo>` (data)**: throughout this README, `<entries-repo>` is a
placeholder — pick your own actual name for it, and ideally not one derived
from "journey" or anything else documented here. The whole point of keeping
`ENTRIES_REPO` as a secret rather than writing it into this (possibly
public) repo is so the entries repo's name isn't guessable from `journey`'s
own contents; using the obvious/suggested name here would quietly undo that,
since it just becomes the documented default guess. GitHub private-repo
access control doesn't depend on the name being secret — this is
belt-and-braces obscurity on top of that, not the actual security boundary
— but it's cheap to get right, so may as well.

Run this from wherever you want that repo to live long-term — **not** from
inside the `journey` folder, which would nest one git repo inside another's
working directory. Anywhere else is fine,
including inside a cloud-synced folder like Dropbox or iCloud Drive: the
automation itself (GitHub Actions) clones this repo fresh on every run and
never touches your local copy at all, so there's no risk of it colliding
with a sync client — your local clone here is purely for your own manual
testing and editing, and having it mirrored to your other devices via
Dropbox/iCloud on top of git's own GitHub sync is a genuine convenience,
not redundant effort. (The one thing to actually avoid, unrelated to cloud
sync specifically, is running git commands against this *same* local clone
from two machines at the same moment — ordinary shared-clone caution, not a
sync-service-specific risk.) A natural spot is right alongside `journey`.
Unlike `journey`, this one holds your actual journal text, so `--private`
here isn't optional:

```bash
cd ~/Dropbox/dev   # or wherever you keep this kind of thing
gh repo create <entries-repo> --private --clone
```

That leaves you with `journey` and `<entries-repo>` as two independent,
sibling repos — which is what `ENTRIES_REPO_PATH` in `.env` should point to.

### 4. Configure locally (for manual runs/testing)

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `TELEGRAM_BOT_TOKEN` — from BotFather.
- `ENTRIES_REPO_PATH` — the path to your `<entries-repo>` clone.
- `TELEGRAM_CHAT_ID` — leave blank for now, run this to get it (after step 1.5):

```bash
python3 scripts/capture_chat_id.py
```

Paste the `chat_id` it prints into `.env`.

### 5. Test it manually

```bash
python3 -m journey.run --force
```

You should get a message from your bot on Telegram. Reply to it, then run
the same command again (with `--force`) — it should commit your reply into
`<entries-repo>/entries/<year>/<date>.md` and push it, then send a new
question. `--force` bypasses both the "already sent today" check and the
evening-hour check, so you can test anytime.

### 6. Set up the GitHub Actions secrets

The workflow needs a way to push to `<entries-repo>`, which is a different
repo than the one it runs in — GitHub's automatic per-workflow token only
covers the repo the workflow lives in. So:

1. Create a **fine-grained personal access token** at
   [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new):
   - Repository access: **only** `<entries-repo>`.
   - Permissions: **Contents: Read and write**. Nothing else.
   - Expiration: give it an actual date rather than "No expiration" — the
     narrow scope above already bounds the blast radius if it leaks, but an
     expiry bounds it in *time* too, and costs nothing since journey's own
     PAT-expiry check (see Maintenance) will remind you before it lapses.
2. In the `journey` repo on GitHub, go to **Settings → Secrets and
   variables → Actions**, and under the **Secrets** tab add each of these as
   a **Repository secret** — not an Environment secret, and not a variable.
   Environment secrets only reach a job that explicitly declares
   `environment: <name>` in the workflow, which `daily.yml` doesn't (there's
   no deployment gating here), so one would just be silently invisible to
   the run:
   - `ENTRIES_REPO_TOKEN` — the token from step 1.
   - `ENTRIES_REPO` — `<your-github-username>/<entries-repo>`. This is a
     secret rather than a repo variable even though the name itself isn't a
     credential: `actions/checkout` logs "Syncing repository: `<value>`",
     and only `secrets.*` values get automatically redacted from run logs —
     a plain variable's value would still print in plain text if `journey`
     is public. No reason to advertise which private repo backs this.
   - `TELEGRAM_BOT_TOKEN` — same value as in your `.env`.
   - `TELEGRAM_CHAT_ID` — same value as in your `.env`.

The timezone and send hour are set directly in
[.github/workflows/daily.yml](.github/workflows/daily.yml) (`JOURNEY_TIMEZONE`,
`JOURNEY_SEND_HOUR`) rather than as secrets, since they're not sensitive —
edit and push that file if you want to change them.

### 7. Push and verify

```bash
git push
```

Then in the `journey` repo on GitHub, go to the **Actions** tab, select
"Journey daily prompt", and click **Run workflow** to trigger it manually
once, to confirm secrets are wired up correctly before waiting for the real
schedule.

## Editing entries directly (e.g. from Working Copy on iOS)

Since entries are just markdown files in an ordinary git repo, you can clone
`<entries-repo>` in [Working Copy](https://workingcopy.app) and add or edit
entries by hand, then push — no need to go through the bot. Useful for
backfilling, editing a typo, or journaling on a day you'd rather not wait for
the evening prompt. Just avoid touching `.state/`, which the bot manages
itself; if you do end up with a conflicting push, the next Actions run will
fail at `git pull --ff-only` rather than silently overwrite anything —
resolve it manually in that repo like any other git conflict.

## Querying your journal later

Once you've got a backlog, just point Claude at the `<entries-repo>` repo
(or ask it to read the files) and ask about trends — no special tooling
needed for that; the entries are already the input Claude works from.

## Security notes

- **`journey` can safely be public.** All four secrets (`TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `ENTRIES_REPO_TOKEN`, `ENTRIES_REPO`) live in GitHub's
  encrypted Actions secrets store, never in repo files or git history. The
  workflow only triggers on `schedule` and `workflow_dispatch` — never
  `pull_request`/`pull_request_target` — so the common "malicious PR steals
  secrets" pattern for public-repo Actions doesn't apply here: forked PRs
  can't run our workflow or reach its secrets, and `schedule` always runs
  the workflow as it exists on the default branch, not from a PR.
- **`ENTRIES_REPO_TOKEN` is scoped narrowly on purpose**: a fine-grained PAT
  limited to `<entries-repo>`, Contents read/write only. If it ever leaked,
  the blast radius is read/write on your journal text — nothing else on
  your GitHub account.
- **No untrusted GitHub context is ever interpolated into a shell step.**
  The known "Actions script injection" class of attack comes from putting
  things like `${{ github.event.issue.title }}` directly into a `run:`
  block, letting an attacker's PR title or comment execute as shell code.
  This workflow never reads PR/issue/comment content at all.
- **Reply text is never trusted as anything but journal content.** It's
  written straight into a markdown file (`entries.append_entry`) and never
  passed to a shell, used to build a git commit message, or used to look up
  which prompt it's replying to. The prompt text that ends up in an entry is
  always resolved fresh from `prompts.json` by id (`prompts.get_by_id`) at
  write time — never taken from the free-text copy Telegram-side, so a
  corrupted or tampered `.state/state.json` can at worst mislabel which
  question was asked, never inject arbitrary text into an entry.
- **If you later have an LLM read `<entries-repo>` for trend analysis**,
  file content should always be treated as data to summarize, never as
  instructions to act on — the same rule that applies to any tool output.
  That's Claude's default behavior, but worth knowing if you build any other
  tooling against these files.
- **`ENTRIES_REPO_TOKEN` is readable by `journey/health.py`, not just by
  git.** It was originally only ever handed to `actions/checkout`, which uses
  it internally for git's own credential helper — the Python script never
  saw it. The PAT-expiry check below needs to make its own authenticated API
  call with that same token, so it's now also passed into the script's
  environment. Same secret, same job, one more internal consumer reading it
  read-only — not a new party gaining access, just a widened *use* of access
  the job already had.

## Maintenance

Two things need periodic attention even once this is running — both are now
handled with as little manual effort as reasonably possible:

- **The `ENTRIES_REPO_TOKEN` PAT expires** on whatever schedule you set when
  creating it (step 6 recommends giving it an actual expiration rather
  than none). `journey/health.py` checks GitHub's own record of that expiry
  date on every run — not a guess — and has the bot send you a standalone
  Telegram message (not attached to any prompt) once it's within 7 days of
  expiring, once per day until you rotate it. When that happens: create a
  new fine-grained PAT the same way as in step 6, and update the
  `ENTRIES_REPO_TOKEN` secret with the new value.
- **GitHub auto-disables scheduled workflows after 60 days of no activity**
  in the repo the workflow lives in (`journey`) — and since this project's
  actual daily activity all lands in the *entries* repo, `journey` itself
  would otherwise only get touched when the code changes, which could easily
  exceed 60 days. Rather than trying to warn about this (a disabled schedule
  can't run to warn you — there's no window in which it's both about to be
  disabled and still capable of telling you so), the workflow prevents it
  outright: every run checks how long it's been since `journey`'s last
  commit, and once that passes 45 days, pushes a trivial one-line
  `.heartbeat` commit to reset GitHub's clock. No action needed on your
  part; mentioned here so a `chore: keepalive` commit showing up in the
  history isn't a surprise.

## Known limitations

- If you skip replying to more than one prompt and then send a plain
  (non-reply) message, it gets attributed to the *most recent* prompt, not
  necessarily the one you meant to answer — use Telegram's reply action on
  the specific prompt you're answering to avoid this (see "How it works").
- The hourly trigger means a reply can take up to ~1 hour to show up as a
  commit, and the daily prompt can go out up to ~1 hour later than
  `JOURNEY_SEND_HOUR` if a run is delayed — GitHub doesn't guarantee
  scheduled workflows fire exactly on time, especially at busy top-of-hour
  minutes (which is also why the cron is set to `:17`, not `:00`).
