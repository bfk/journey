# journey

A low-key daily journalling prompt over Telegram.

Every evening, `journey` sends you an open-ended question. When you reply, your answer is committed as a dated entry to a private GitHub repository that you control.

There is no server to run and no third-party journalling service holding your entries. The project uses a small Python script, a Telegram bot, Git, and GitHub Actions.

## How it works

- `prompts.json` contains a library of open-ended questions. Each run chooses one at random while avoiding the 30 most recently used questions.
- `journey/run.py` checks Telegram for new replies, commits them to your entries repository, and sends the day's question once it is evening in your timezone.
- `.github/workflows/daily.yml` runs the script hourly on GitHub Actions.
- The script checks `JOURNEY_TIMEZONE` and `JOURNEY_SEND_HOUR`, so it sends only once per local calendar day and only after the configured hour.
- Replies are normally associated with the most recent prompt. If you use Telegram's Reply action to quote an older prompt, the entry is associated with the date of that prompt instead.
- Persistent state is stored in `.state/state.json` in your entries repository. This records processed Telegram messages, recently used questions, and the last prompt sent.
- Journal entries are stored in a separate private repository, so your personal writing is never mixed with this code repository.

The state retains prompt-message mappings for the last 180 days, which allows you to go back and answer an older prompt by replying to that specific Telegram message.

## Why GitHub Actions instead of a local scheduled task?

A local `cron` or `launchd` job only runs while its computer is awake. An application-level scheduled task may also depend on that application remaining open.

GitHub Actions runs independently of your own devices. The workflow can send the prompt even when your laptop is closed or switched off. Because an Actions runner is temporary, the project stores its durable state in the entries repository rather than on the runner's local disk.

## What you will need

Before you start, make sure you have:

- a GitHub account;
- Git installed;
- Python 3 installed;
- the [GitHub CLI](https://cli.github.com/) installed;
- a Telegram account; and
- permission to create a private GitHub repository and repository secrets.

## One-time setup

### 1. Create a Telegram bot

Searching for "BotFather" in Telegram is unsafe because display names are not unique. Open [the official BotFather account](https://t.me/BotFather) directly and check that:

- the username shown in the chat header is exactly `BotFather`; and
- the account has Telegram's verified badge.

Then:

1. Send `/newbot`.
2. Give the bot a name and a username. The username must end in `bot`, for example `my_journey_bot`.
3. Save the token BotFather gives you. It will look similar to `123456789:AAExampleTokenNotReal`.
4. Send your new bot any message, such as `hi`, so that it has a conversation with you to inspect.

The genuine BotFather does not ask for your Telegram password, a login code, or a sign-in on another website.

### 2. Install and authenticate the GitHub CLI

On macOS with Homebrew:

```bash
brew install gh
```

Then authenticate:

```bash
gh auth login
```

Run `gh auth login` directly in your terminal. It uses an interactive sign-in flow.

### 3. Clone this repository

From the directory where you keep development projects, run:

```bash
git clone https://github.com/bfk/journey.git
cd journey
```

You now have the code repository. You do not need to create or republish it.

If you want to make your own changes and keep them on GitHub, fork the project first and clone your fork instead.

### 4. Create a private entries repository

Your journal entries and the application's persistent state live in a separate repository.

Throughout this README, `<entries-repo>` means the name you choose for that repository. Consider choosing a name that is not obviously connected to `journey`. The repository name is not a security boundary, but a less predictable name avoids advertising where your entries are stored.

Run the following command from the directory in which you want the entries repository to live. Do not run it inside the cloned `journey` directory.

```bash
cd ~/Dropbox/dev  # or another directory outside the journey repository
gh repo create <entries-repo> --private --clone
```

This leaves you with two independent repositories, for example:

```text
~/Dropbox/dev/
├── journey/
└── <entries-repo>/
```

The entries repository may be in a cloud-synchronised folder such as Dropbox or iCloud Drive. GitHub Actions clones it afresh on each run and does not use your local copy. As with any shared working directory, avoid running Git commands against the same local clone from two computers at the same time.

The entries repository must remain private because it contains your journal text.

### 5. Configure local testing

Return to the cloned `journey` repository:

```bash
cd /path/to/journey
cp .env.example .env
```

Edit `.env` and set:

- `TELEGRAM_BOT_TOKEN` to the token from BotFather;
- `ENTRIES_REPO_PATH` to the path of your local `<entries-repo>` clone; and
- `TELEGRAM_CHAT_ID` after obtaining it in the next step.

After you have sent your bot a message, run:

```bash
python3 scripts/capture_chat_id.py
```

Copy the `chat_id` printed by the script into `.env` as `TELEGRAM_CHAT_ID`.

Do not commit `.env`. It contains sensitive values intended only for local use.

### 6. Test it locally

From the root of the `journey` repository, run:

```bash
python3 -m journey.run --force
```

You should receive a message from your bot in Telegram.

Reply to the prompt, then run the same command again:

```bash
python3 -m journey.run --force
```

The script should commit your reply to:

```text
<entries-repo>/entries/<year>/<date>.md
```

It will then push the commit and send another question.

`--force` bypasses both the evening-hour check and the check that prevents a second prompt being sent on the same day. Use it for testing rather than routine operation.

### 7. Give GitHub Actions access to the entries repository

The workflow runs in the `journey` repository but must push to your separate private entries repository. GitHub's automatic workflow token does not provide that cross-repository access.

Create a fine-grained personal access token at [GitHub personal access tokens](https://github.com/settings/personal-access-tokens/new) with:

- **Repository access:** only your `<entries-repo>` repository;
- **Repository permission:** `Contents: Read and write`; and
- no other permissions.

Save the token when GitHub displays it.

### 8. Add the GitHub Actions secrets

In your cloned `journey` repository on GitHub, open:

**Settings → Secrets and variables → Actions → Secrets**

Add these as **repository secrets**:

| Secret | Value |
| --- | --- |
| `ENTRIES_REPO_TOKEN` | The fine-grained personal access token created above |
| `ENTRIES_REPO` | `<your-github-username>/<entries-repo>` |
| `TELEGRAM_BOT_TOKEN` | The token issued by BotFather |
| `TELEGRAM_CHAT_ID` | The chat ID captured during local setup |

Use repository secrets rather than environment secrets or repository variables. The workflow does not declare a GitHub environment, and secret values are redacted from workflow logs.

`ENTRIES_REPO` is stored as a secret even though it is not a credential. This prevents the name of the private repository appearing in logs from a public code repository.

### 9. Set your timezone and delivery hour

Open `.github/workflows/daily.yml` and edit:

- `JOURNEY_TIMEZONE`; and
- `JOURNEY_SEND_HOUR`.

These values are stored in the workflow rather than as secrets because they are configuration, not credentials.

Commit and push your changes:

```bash
git add .github/workflows/daily.yml
git commit -m "Configure journey schedule"
git push
```

If you cloned the original repository directly and do not have permission to push to it, create a fork, point your local `origin` remote at your fork, and push the configuration there. GitHub Actions must run from a repository you control because that is where you add the secrets.

### 10. Enable and verify the workflow

In the GitHub repository that you control:

1. Open the **Actions** tab.
2. Enable workflows if GitHub asks you to do so.
3. Select **Journey daily prompt**.
4. Choose **Run workflow** to trigger a manual run.
5. Check the run output and confirm that the bot sends a prompt.

Once the manual run works, the scheduled workflow can take over.

## Day-to-day use

You do not need to leave your computer running.

The GitHub Actions workflow runs hourly. After the configured local send hour, the first eligible run sends that day's prompt. A Telegram reply is normally collected and committed within roughly the next hourly run.

To answer the latest prompt, send an ordinary reply in the bot chat. To answer an older prompt, use Telegram's Reply action on that specific prompt message.

Your entries accumulate in the private entries repository under:

```text
entries/<year>/<date>.md
```

## Customising the prompts

Edit `prompts.json` in the code repository, then commit and push your changes to the repository from which the workflow runs.

The application avoids the 30 most recently used prompts when choosing the next question.

## Running manually

For local testing or an immediate forced run:

```bash
python3 -m journey.run --force
```

Remember that `--force` can send more than one prompt on the same day.

## Security notes

- Keep the entries repository private.
- Never commit `.env`.
- Store `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ENTRIES_REPO`, and `ENTRIES_REPO_TOKEN` as GitHub Actions repository secrets.
- Limit the fine-grained personal access token to the entries repository and grant only `Contents: Read and write`.
- Treat the Telegram bot token and GitHub token as credentials. Revoke and replace either one if it is exposed.
- A non-obvious entries-repository name provides only minor additional obscurity. GitHub access controls and the restricted token are the security boundaries.
- This design keeps journal content out of the code repository, but the content is still stored by GitHub and messages still pass through Telegram.

## Troubleshooting

### `capture_chat_id.py` does not find a chat

Send a message directly to your bot, then run the script again.

### The workflow cannot push to the entries repository

Check that:

- `ENTRIES_REPO` contains both the GitHub username and repository name;
- `ENTRIES_REPO_TOKEN` is a fine-grained token with access to that repository;
- the token has `Contents: Read and write`; and
- all four values were added as repository secrets in the repository running the workflow.

### The workflow runs but no prompt arrives

Check:

- the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets;
- `JOURNEY_TIMEZONE` and `JOURNEY_SEND_HOUR` in `.github/workflows/daily.yml`; and
- whether a prompt has already been sent for the current local calendar day.

Use a manual workflow run or the local `--force` option when testing.

### I cannot push the workflow configuration

A clone of `bfk/journey` points at the original repository by default. If you are not a contributor to that repository, fork it into your own GitHub account, change your local `origin` to the fork, and push there. Add the Actions secrets to your fork.

## Repository separation at a glance

The repository running the workflow contains:

- the Python code;
- the prompt library;
- the GitHub Actions workflow; and
- no journal entries or committed credentials.

Your private entries repository contains:

- your dated journal entries; and
- `.state/state.json`, which allows the application to continue correctly across temporary Actions runners.

Keeping these repositories separate allows the code to be shared while the journal remains private.
