# journey

A low-key daily journaling prompt over Telegram.

Every evening it sends you an open-ended question. Whenever you reply, your answer is committed as a dated entry to a private GitHub repository that you control.

There is no server to run and no third-party journaling service holding your journal: just a script, a Telegram bot, Git, and GitHub Actions.

## How it works

`prompts.json` is a library of open-ended questions. Each run picks one at random, avoiding the last 30 used.

`journey/run.py` has two commands, run as two separate GitHub Actions workflows, because they tolerate a missed or delayed run very differently:

- **`send`** (`.github/workflows/send-prompt.yml`) sends that day's question once it is evening in your timezone. It checks the local wall-clock time set by `JOURNEY_TIMEZONE` and `JOURNEY_SEND_HOUR`, and sends once per local calendar day. If it never fires during the eligible window on a given day, that day's prompt is permanently missed — recoverable only with `--backfill-date` (see Troubleshooting). Because a missed fire here is costly, this workflow fires only a few times a day, deliberately concentrated in the evening window rather than spread out.
- **`poll`** (`.github/workflows/poll-replies.yml`) checks Telegram for new replies and commits them to your entries repository. A late or occasionally skipped poll only delays when a reply becomes visible — nothing is lost, so this workflow can fire much more often without the same risk.

The default configuration sends at 7pm Europe/London time. You do not need to edit either workflow if that suits you.

The default send hour is chosen deliberately, not just for tone: `send-prompt.yml` fires at 19:00, 21:00, and 23:00, so 7pm is the earliest hour that gets all three fires inside the eligible window before midnight — three independent chances rather than one. If GitHub delays or skips one scheduled fire, which happens in practice (see Troubleshooting), that redundancy is what actually protects the day, not the choice of hour by itself.

State that must survive between runs lives in `.state/state.json` inside your entries repository. It records which Telegram messages have been processed, which questions were recently asked, and when the last prompt was sent. This persists through Git commits because each GitHub Actions runner is discarded after its run.

Journal entries live in a separate private repository, referred to throughout this README as `<entries-repo>`. The code can remain public without mixing it with your journal content.

A plain Telegram message is assumed to answer the most recent prompt. If you use Telegram's Reply action to quote an older prompt, the reply is attributed to the date and question it answers, even if newer prompts have since been sent. This lets you catch up on a missed prompt without placing the answer under today's date.

The state keeps the last 180 days of prompt-message ID to date/question mappings for this purpose. See `journey/state.py`.

## Why GitHub Actions rather than a local scheduled task?

A `launchd` or `cron` job on a personal computer runs only while that computer is awake. An application-level scheduled task may also depend on the application remaining open.

GitHub Actions runs on GitHub's infrastructure. There is no server to maintain and no personal computer that must remain switched on. The trade-off is that entries and run state must persist in Git rather than on a runner's local disk.

## Deployment model

Journey is a single-user application. One fork runs one person's journal, using that person's Telegram bot and private entries repository.

The upstream `bfk/journey` repository runs the maintainer's instance. To run Journey for yourself, fork the repository into your own GitHub account. Your fork gives you separate GitHub Actions workflows and your own repository secrets.

Throughout this README, **your Journey repository** means your fork, normally `<your-github-username>/journey`.

## One-time setup

### 1. Create the Telegram bot

Searching for "BotFather" in Telegram is unsafe. Telegram search matches display names, which are not unique, while the `@username` is unique.

Open [the official BotFather account](https://t.me/BotFather) directly rather than finding it through Telegram search.

Check that:

- the username in the chat header is exactly `BotFather`; and
- the account has Telegram's verified badge.

Then:

1. Send `/newbot`.
2. Give the bot a name and a username. The username must end in `bot`, for example `my_journey_bot`.
3. Save the token BotFather gives you. It will look similar to `123456789:AAExampleTokenNotReal`.
4. Send your new bot any message, such as `hi`, so that it knows who you are.

The genuine BotFather will never ask for your Telegram password, a login code, or a sign-in on another website.

### 2. Install and authenticate the GitHub CLI

On macOS with Homebrew:

```bash
brew install gh
```

Then authenticate:

```bash
gh auth login
```

Run `gh auth login` yourself in a terminal. It uses an interactive browser sign-in.

### 3. Fork and clone Journey

On the [Journey repository](https://github.com/bfk/journey), select **Fork** and create the fork in your own GitHub account. Keep the default repository name, `journey`.

Then clone your fork:

```bash
gh repo clone <your-github-username>/journey
cd journey
```

You should now be in the root of your fork's local clone. This is the directory containing `README.md`, `prompts.json`, `.github/`, and the `journey/` Python package as siblings.

### 4. Create your private entries repository

`<entries-repo>` is a placeholder. Choose your own name, ideally one that is not derived from `journey` or anything else documented here.

Keeping `ENTRIES_REPO` as a secret means that the name of the private repository does not need to appear in your public Journey fork. A non-obvious name adds minor obscurity, although GitHub's private-repository access controls remain the security boundary.

Create the repository outside the `journey` folder. Do not nest one Git repository inside the other's working directory.

For example:

```bash
cd ~/Dropbox/dev  # or wherever you keep local repositories
gh repo create <entries-repo> --private --clone
```

The entries repository can live in a cloud-synchronised folder such as Dropbox or iCloud Drive. GitHub Actions clones it fresh for each run and never uses your local copy. Avoid running Git commands against the same local clone from two computers at the same time.

You should now have two independent repositories, for example:

```text
~/Dropbox/dev/
├── journey/
└── <entries-repo>/
```

The `journey` repository is your public fork containing the application. `<entries-repo>` is private and contains your journal and persistent state.

### 5. Configure local testing

Return to your local Journey clone:

```bash
cd /path/to/journey
cp .env.example .env
```

Edit `.env` and set:

- `TELEGRAM_BOT_TOKEN` to the token from BotFather;
- `ENTRIES_REPO_PATH` to the local path of your `<entries-repo>` clone; and
- `TELEGRAM_CHAT_ID` after obtaining it in the next step.

After sending your bot a message, run:

```bash
python3 scripts/capture_chat_id.py
```

Paste the `chat_id` printed by the script into `.env` as `TELEGRAM_CHAT_ID`.

Do not commit `.env`. It contains sensitive values for local use.

### 6. Test it manually

From the root of your local Journey clone, run:

```bash
python3 -m journey.run send --force
```

You should receive a message from your bot in Telegram.

Reply to it, then run:

```bash
python3 -m journey.run poll
```

This should commit your reply to:

```text
<entries-repo>/entries/<year>/<date>.md
```

and push the commit. `send` and `poll` are separate commands, matching how they run as separate workflows in production — running them separately here tests exactly what production does, rather than a combined path that does not otherwise exist.

`send --force` bypasses both the "already sent today" check and the evening-hour check, so you can test at any time. It can send more than one prompt on the same day, so use it for testing rather than routine operation.

### 7. Create a token for the entries repository

Both workflows run in your Journey fork but must push to your separate private entries repository. GitHub's automatic per-workflow token covers only the repository in which a workflow runs.

Create a fine-grained personal access token at [GitHub personal access tokens](https://github.com/settings/personal-access-tokens/new) with:

- **Repository access:** only `<entries-repo>`;
- **Permissions:** `Contents: Read and write`; and
- no other permissions.

Save the token when GitHub displays it.

### 8. Add the GitHub Actions secrets

In your Journey fork on GitHub, open:

**Settings → Secrets and variables → Actions**

Under **Secrets**, add each of these as a **repository secret**:

- `ENTRIES_REPO_TOKEN`: the fine-grained personal access token created in step 7.
- `ENTRIES_REPO`: `<your-github-username>/<entries-repo>`.
- `TELEGRAM_BOT_TOKEN`: the token issued by BotFather.
- `TELEGRAM_CHAT_ID`: the chat ID captured during local setup.

Use repository secrets rather than environment secrets or repository variables. The workflow does not declare a GitHub environment, so environment secrets will not be available to it.

`ENTRIES_REPO` is stored as a secret even though the name itself is not a credential. `actions/checkout` logs the repository it is synchronising, and values supplied through `secrets.*` are redacted from workflow logs. This avoids advertising which private repository backs a public Journey fork.

### 9. Confirm the schedule

The default configuration sends the daily prompt at 7pm Europe/London time. If that suits you, do not change `.github/workflows/send-prompt.yml`.

If you want a different local time or timezone, edit `JOURNEY_TIMEZONE` and `JOURNEY_SEND_HOUR` in `.github/workflows/send-prompt.yml`. If you move the send hour more than an hour or two from 7pm, also consider adjusting the `cron:` line in that file so its fire times still bracket your new send hour — see How it works for why that alignment matters.

`.github/workflows/poll-replies.yml` has no send hour to configure; its schedule only affects how quickly a reply is picked up, not whether anything is missed.

Commit and push any change to your fork:

```bash
git add .github/workflows/send-prompt.yml
git commit -m "Configure Journey schedule"
git push
```

These values are stored in the workflow rather than as secrets because they are configuration, not credentials.

### 10. Run and verify the workflows

In your Journey fork on GitHub:

1. Open the **Actions** tab.
2. Enable workflows if GitHub asks you to do so.
3. Select **Journey send prompt**, then **Run workflow**, and confirm your Telegram bot sends a prompt.
4. Reply to it, then select **Journey poll replies**, then **Run workflow**, and confirm the reply is committed to your entries repository.

Once both manual runs work, the schedules can take over. You do not need to leave your computer running.

## Day-to-day use

`send-prompt.yml` fires three times in the evening (19:00, 21:00, 23:00 by default); the first of those fires after the configured send hour sends that day's prompt. `poll-replies.yml` fires every 30 minutes throughout the day and commits any reply since the last poll, whenever it actually arrives.

To answer the latest prompt, send an ordinary message in the bot chat.

To answer an older prompt, use Telegram's Reply action on that specific prompt message.

Your entries accumulate in the private entries repository under:

```text
entries/<year>/<date>.md
```

GitHub's `schedule` trigger is best effort for both workflows, but the consequence differs sharply. A delayed or skipped poll just means a reply shows up a little later — nothing is lost. A delayed or skipped send is different: if none of the day's three fires actually happens, that day's prompt never goes out, and no later poll can recover it, since there is nothing to poll for. This did happen in practice under the previous single-workflow, hourly-everything design — a firing interval that was observed to degrade over consecutive days, from tens of minutes of delay up to several hours, well beyond GitHub's documented top-of-hour jitter. Splitting the two concerns and scheduling each according to its own tolerance for delay is the mitigation; `--backfill-date` (see Troubleshooting) is what to reach for if a day still gets missed regardless.

## Customising the prompts

Edit `prompts.json` in your Journey fork, then commit and push the change:

```bash
git add prompts.json
git commit -m "Customise Journey prompts"
git push
```

The application avoids the 30 most recently used prompts when choosing the next question.

Existing prompt ids must keep their original text. `journey/run.py` resolves a sent prompt's wording from `prompts.json` by id when a reply is recorded, not from a copy made when the prompt was sent — so editing an existing id's text can retroactively change what an already-sent, not-yet-answered prompt is recorded as having asked. Add a new id for a reworded question, or delete an id outright; both are safe. `.github/workflows/check-prompts.yml` runs on every push that touches `prompts.json` and fails the push if an existing id's text has changed.

## Maintenance

Two things need periodic attention:

- **The `ENTRIES_REPO_TOKEN` fine-grained personal access token expires** on whatever date was chosen when creating it (step 7). `journey/health.py` checks GitHub's own record of that expiry date on every run — not a guess — and sends a standalone Telegram message, not attached to any prompt, once it is within 7 days of expiring, once per day until the token is rotated. To rotate: create a new fine-grained personal access token the same way as in step 7, and update the `ENTRIES_REPO_TOKEN` secret with the new value.
- **GitHub disables scheduled workflows after 60 days of no activity** in the repository they run in — both workflows here, since that limit applies per repository, not per workflow. Journey's actual daily activity lands in the separate entries repository, so the Journey fork itself could go 60 days without a commit if the code is never edited. `poll-replies.yml` checks the age of the fork's own last commit on every run and, once that exceeds 45 days, pushes a one-line `.heartbeat` commit to reset GitHub's inactivity clock. This requires no action — it is documented here so a `chore: keepalive` commit in the history is not a surprise.

## Security notes

- Keep the entries repository private.
- Never commit `.env`.
- Store `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ENTRIES_REPO`, and `ENTRIES_REPO_TOKEN` as GitHub Actions repository secrets in your fork.
- Limit the fine-grained personal access token to the entries repository and grant only `Contents: Read and write`.
- Treat the Telegram bot token and GitHub token as credentials. Revoke and replace either token if it is exposed.
- A non-obvious entries-repository name provides only minor additional obscurity. GitHub access controls and the restricted token are the security boundaries.
- Journal content is stored by GitHub, and messages pass through Telegram.

## Troubleshooting

### `capture_chat_id.py` does not find a chat

Send a message directly to your bot, then run the script again.

### A workflow cannot push to the entries repository

Check that:

- `ENTRIES_REPO` contains both your GitHub username and the entries repository name;
- `ENTRIES_REPO_TOKEN` has access to that repository;
- the token has `Contents: Read and write`; and
- all four values were added as repository secrets in your Journey fork.

### The send workflow runs but no prompt arrives

Check:

- the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets;
- `JOURNEY_TIMEZONE` and `JOURNEY_SEND_HOUR` in `.github/workflows/send-prompt.yml`; and
- whether a prompt has already been sent for the current local calendar day.

Use a manual workflow run or the local `send --force` option when testing.

### The poll workflow runs but a reply never arrives in your entries repository

Check:

- the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets; and
- whether the reply was sent as an explicit Telegram Reply to an old prompt message that Journey no longer has a record of (see the 180-day limit in How it works) — in that case it falls back to attributing the reply to the most recent prompt instead.

Use a manual workflow run or the local `poll` command when testing.

### The workflows are not visible or do not run

Check that you are looking at the **Actions** tab in your fork, `<your-github-username>/journey`, rather than the upstream `bfk/journey` repository. Enable workflows in the fork if GitHub asks you to do so.

### A day was skipped entirely

GitHub's `schedule` trigger does not guarantee delivery (see Day-to-day use). If a day has no entry at all, recover it from your local clone:

```bash
python3 -m journey.run send --backfill-date 2026-08-28
```

This sends a fresh prompt immediately, labeled with the date being backfilled, but does not touch today's actual prompt state. Reply to that specific message using Telegram's **Reply** action, not a plain message — a plain message still defaults to today's prompt as normal. The next run then commits your reply under the backfilled date, not today's.

## Repository separation at a glance

Your Journey fork contains:

- the Python code;
- the prompt library;
- the GitHub Actions workflows; and
- no journal entries or committed credentials.

Your private entries repository contains:

- your dated journal entries; and
- `.state/state.json`, which lets the application continue correctly across temporary Actions runners.

Keeping the repositories separate allows the code to remain public while your journal remains private.
