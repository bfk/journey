# journey

A low-key daily journaling prompt over Telegram.

Every evening it sends you an open-ended question. Whenever you reply, your answer is committed as a dated entry to a private GitHub repository that you control.

There is no server to run and no third-party journaling service holding your journal: just a script, a Telegram bot, Git, and GitHub Actions.

## How it works

`prompts.json` is a library of open-ended questions. Each run picks one at random, avoiding the last 30 used.

`journey/run.py` is the whole program. It checks Telegram for new replies, commits them to your entries repository, and sends that day's question once it is evening in your timezone.

The program runs on GitHub Actions rather than on your laptop. The workflow triggers hourly, but the script sends only once per day. It checks the local wall-clock time set by `JOURNEY_TIMEZONE` and `JOURNEY_SEND_HOUR` in `.github/workflows/daily.yml`, then sends after that hour once per local calendar day.

The default configuration sends at 9pm Europe/London time. You do not need to edit the workflow if that suits you.

Running hourly also means that a reply is normally collected and committed within about an hour.

State that must survive between runs lives in `.state/state.json` inside your entries repository. It records which Telegram messages have been processed, which questions were recently asked, and when the last prompt was sent. This persists through Git commits because each GitHub Actions runner is discarded after its run.

Journal entries live in a separate private repository, referred to throughout this README as `<entries-repo>`. The code can remain public without mixing it with your journal content.

A plain Telegram message is assumed to answer the most recent prompt. If you use Telegram's Reply action to quote an older prompt, the reply is attributed to the date and question it answers, even if newer prompts have since been sent. This lets you catch up on a missed prompt without placing the answer under today's date.

The state keeps the last 180 days of prompt-message ID to date/question mappings for this purpose. See `journey/state.py`.

## Why GitHub Actions rather than a local scheduled task?

A `launchd` or `cron` job on a personal computer runs only while that computer is awake. An application-level scheduled task may also depend on the application remaining open.

GitHub Actions runs on GitHub's infrastructure. There is no server to maintain and no personal computer that must remain switched on. The trade-off is that entries and run state must persist in Git rather than on a runner's local disk.

## Deployment model

Journey is a single-user application. One fork runs one person's journal, using that person's Telegram bot and private entries repository.

The upstream `bfk/journey` repository runs the maintainer's instance. To run Journey for yourself, fork the repository into your own GitHub account. Your fork gives you a separate GitHub Actions workflow and your own repository secrets.

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
python3 -m journey.run --force
```

You should receive a message from your bot in Telegram.

Reply to it, then run the same command again:

```bash
python3 -m journey.run --force
```

The script should commit your reply to:

```text
<entries-repo>/entries/<year>/<date>.md
```

It should push the commit, then send another question.

`--force` bypasses both the "already sent today" check and the evening-hour check, so you can test at any time. It can send more than one prompt on the same day, so use it for testing rather than routine operation.

### 7. Create a token for the entries repository

The workflow runs in your Journey fork but must push to your separate private entries repository. GitHub's automatic per-workflow token covers only the repository in which the workflow runs.

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

The default workflow configuration sends the daily prompt at 9pm Europe/London time. If that suits you, do not change `.github/workflows/daily.yml`.

If you want a different local time or timezone, edit:

- `JOURNEY_TIMEZONE`; and
- `JOURNEY_SEND_HOUR`.

Then commit and push the change to your fork:

```bash
git add .github/workflows/daily.yml
git commit -m "Configure Journey schedule"
git push
```

These values are stored in the workflow rather than as secrets because they are configuration, not credentials.

### 10. Run and verify the workflow

In your Journey fork on GitHub:

1. Open the **Actions** tab.
2. Enable workflows if GitHub asks you to do so.
3. Select **Journey daily prompt**.
4. Select **Run workflow** to trigger it manually.
5. Check the run and confirm that your Telegram bot sends a prompt.

Once the manual run works, the scheduled workflow can take over. You do not need to leave your computer running.

## Day-to-day use

The workflow runs hourly. After the configured local send hour, the first eligible run sends that day's prompt. A Telegram reply is normally collected and committed by a later hourly run.

To answer the latest prompt, send an ordinary message in the bot chat.

To answer an older prompt, use Telegram's Reply action on that specific prompt message.

Your entries accumulate in the private entries repository under:

```text
entries/<year>/<date>.md
```

## Customising the prompts

Edit `prompts.json` in your Journey fork, then commit and push the change:

```bash
git add prompts.json
git commit -m "Customise Journey prompts"
git push
```

The application avoids the 30 most recently used prompts when choosing the next question.

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

### The workflow cannot push to the entries repository

Check that:

- `ENTRIES_REPO` contains both your GitHub username and the entries repository name;
- `ENTRIES_REPO_TOKEN` has access to that repository;
- the token has `Contents: Read and write`; and
- all four values were added as repository secrets in your Journey fork.

### The workflow runs but no prompt arrives

Check:

- the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets;
- `JOURNEY_TIMEZONE` and `JOURNEY_SEND_HOUR` in `.github/workflows/daily.yml`; and
- whether a prompt has already been sent for the current local calendar day.

Use a manual workflow run or the local `--force` option when testing.

### The workflow is not visible or does not run

Check that you are looking at the **Actions** tab in your fork, `<your-github-username>/journey`, rather than the upstream `bfk/journey` repository. Enable workflows in the fork if GitHub asks you to do so.

## Repository separation at a glance

Your Journey fork contains:

- the Python code;
- the prompt library;
- the GitHub Actions workflow; and
- no journal entries or committed credentials.

Your private entries repository contains:

- your dated journal entries; and
- `.state/state.json`, which lets the application continue correctly across temporary Actions runners.

Keeping the repositories separate allows the code to remain public while your journal remains private.
