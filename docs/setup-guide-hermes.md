# Setup Guide - Hermes Agent + Vigil

Last reviewed: 2026-05-16.

This is the preferred end-to-end runbook if you plan to run `hermes-agent`
instead of OpenClaw. It restores the original local preparation steps and keeps
the same VPS/security/data pipeline, but swaps the agent layer for Hermes
Gateway and Hermes Cron.

Estimated total time: about 9-14 hours for a careful first setup. If your book
exports, contacts, Todoist, and financial credentials are already prepared, the
practical server setup is closer to 4-6 hours.

## What You Are Building

- Vigil creates the deterministic Phase 1 daily brief in Anytype:
  Bible/devotional, weather, Todoist, finance, and birthdays.
- Hermes runs Phase 2 and Phase 3 LLM work:
  message/email summaries, drafted replies, financial editorial, morning
  message, and periodic follow-up checks.
- Anytype stores the daily brief locally on the VPS.
- Telegram is the recommended primary chat and delivery channel.
- Bank data uses OFX Direct Connect and local OFX/QFX statement imports.
- Brokerage data uses SnapTrade.
- Recession/economic indicators use FRED.

## Personal Data Gate

Complete this gate before using real email, messages, banking, brokerage, or
private contacts:

- Run the full test suite locally: `./scripts/check.sh`.
- Confirm `VIGIL_RUNTIME_DIR` points to a private directory, for example
  `/home/hermes/data/runtime`.
- Confirm runtime files are mode `0600` after a test run:
  `daily_brief_state.json` and `daily_brief_fm_output.json`.
- Keep Vigil credentials in `/home/hermes/.config/vigil/env` with mode `0600`.
- Let Hermes store its own secrets in `~/.hermes/.env` and non-secret config in
  `~/.hermes/config.yaml`.
- Start with fake or low-risk financial data until one full Phase 1 and Phase 2
  run completes cleanly.
- Do not paste secrets into Hermes prompts.
- Use legally obtained reading files. This guide does not include or recommend
  DRM bypass instructions.

## Assumptions

- Local prep machine: macOS, Linux, or WSL2.
- VPS: Ubuntu 24.04.
- VPS user in examples: `hermes`.
- Repo path: `/home/hermes/vigil`.
- Data path: `/home/hermes/data`.
- Private config path: `/home/hermes/.config/vigil/env`.
- Runtime path: `/home/hermes/data/runtime`.
- Timezone: `America/New_York`; change it consistently if you use another
  timezone.

Set the server timezone after the VPS exists:

```bash
sudo timedatectl set-timezone America/New_York
date
```

## Step 1 - Reading Content Pipeline

Time: about 2-3 hours one time.

Do this on your local machine before starting the paid VPS work.

### 1a. Install conversion tools

1. Install Calibre from <https://calibre-ebook.com/download>.
2. Install Python 3.12+ if your local machine does not already have it.
3. Install Docling:

   ```bash
   python3 -m pip install --user docling
   ```

4. Optional fallback if Docling struggles with a file:

   ```bash
   python3 -m pip install --user markitdown
   ```

### 1b. Prepare legally obtained source files

Export or download readable files that you are allowed to process. EPUB, PDF,
HTML, DOCX, and Markdown are reasonable inputs.

The code expects these final Markdown filenames:

```text
good_morning_mercies.md
esv_bible.md
reformation_study_bible.md
macarthur_study_bible.md
esv_study_bible.md
```

Create a local staging directory:

```bash
mkdir -p ~/vigil-setup/books
mkdir -p ~/vigil-setup/style
```

Convert each source file to Markdown:

```bash
docling convert ./source/good_morning_mercies.epub --to md --output ~/vigil-setup/books
docling convert ./source/esv_bible.epub --to md --output ~/vigil-setup/books
docling convert ./source/reformation_study_bible.epub --to md --output ~/vigil-setup/books
docling convert ./source/macarthur_study_bible.epub --to md --output ~/vigil-setup/books
docling convert ./source/esv_study_bible.epub --to md --output ~/vigil-setup/books
```

Rename the outputs to the exact filenames above.

### 1c. Create the reading plan

Create `~/vigil-setup/reading_plan.json` as an array of daily records:

```json
[
  {
    "date": "2026-01-01",
    "morning_devotional": "Day 1",
    "bible_reading": "Genesis 1-3"
  },
  {
    "date": "2026-01-02",
    "morning_devotional": "Day 2",
    "bible_reading": "Genesis 4-6"
  }
]
```

If you use an LLM to convert a reading plan, inspect the JSON before deploying:

```bash
python3 -m json.tool ~/vigil-setup/reading_plan.json >/dev/null
```

### 1d. Validate the Bible parser locally

After cloning this repo locally:

```bash
cd /path/to/vigil
uv sync --dev
VIGIL_DATA_DIR=~/vigil-setup \
READING_PLAN_PATH=~/vigil-setup/reading_plan.json \
BOOKS_DIR=~/vigil-setup/books \
uv run python -m vigil.bible
```

If the output is empty or missing passages:

1. Open the generated Markdown and inspect the heading format.
2. Prefer fixing the Markdown headings first.
3. If the source format is consistent but different from the parser, update
   `src/vigil/bible.py`.
4. Re-run `uv run pytest tests/test_bible.py`.

Do not proceed until this parser works on your real files.

## Step 2 - Contacts and Todoist

Time: about 30 minutes.

### 2a. Birthday contacts

Create `~/vigil-setup/contacts.json`:

```json
[
  {
    "name": "John Doe",
    "birthday": "1990-03-15",
    "relationship": "friend"
  },
  {
    "name": "Jane Smith",
    "birthday": "1985-07-22",
    "relationship": "family"
  }
]
```

Validate it:

```bash
python3 -m json.tool ~/vigil-setup/contacts.json >/dev/null
```

### 2b. Todoist

1. In Todoist, create recurring tasks for medications, trash/recycling, bills,
   appointments, and any other daily-operational items.
2. Copy your Todoist API token from Todoist settings.
3. Keep the token ready for Step 8.

Phase 1 uses the Todoist REST API directly through `vigil brief`. Phase 2 can
use Hermes tools or MCP integrations for creating, completing, and rescheduling
tasks after the base Hermes chat works.

## Step 3 - Voice Profiles

Time: about 1-2 hours.

### 3a. Morning message profile

1. Collect 15-30 morning messages you have actually written.
2. Separate each message with `---`.
3. Use `prompts/setup/generate_voice_profile.md` to distill the examples.
4. Save the result to `~/vigil-setup/style/morning_voice.md`.

### 3b. Reply style guide

1. Collect 15-30 real replies to friends, family, or coworkers.
2. Include the incoming message plus your reply where possible.
3. Separate each exchange with `---`.
4. Use `prompts/setup/generate_reply_style.md`.
5. Save the result to `~/vigil-setup/style/reply_style.md`.

These profiles keep the scheduled prompts smaller and make output easier to
review.

## Step 4 - Hetzner Server

Time: about 15 minutes.

1. Create a Hetzner Cloud account.
2. Create a project named `hermes`.
3. Create or upload an SSH key:

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/hetzner_hermes
   ```

4. Create a server:
   - Image: Ubuntu 24.04.
   - Type: CX23 or larger.
   - Location: choose the closest or cheapest region that fits your needs.
   - SSH key: select the key above.
5. Save the public IPv4 address.

This is the point where server costs begin.

## Step 5 - LUKS Disk Encryption

Time: about 30-45 minutes.

LUKS protects data at rest if the VPS disk is copied or the server is seized.
The first boot after installation usually needs a console unlock before you can
finish remote-unlock setup.

1. In Hetzner Console, enable Rescue mode with your SSH key.
2. Power-cycle the server into Rescue mode.
3. SSH in:

   ```bash
   ssh -i ~/.ssh/hetzner_hermes root@<server-public-ip>
   ```

4. Create `/autosetup`:

   ```bash
   cat > /autosetup <<'EOF'
   DRIVE1 /dev/sda
   BOOTLOADER grub
   HOSTNAME hermes
   PART /boot ext4 1G
   PART lvm vg0 all crypt
   LV vg0 root / ext4 all
   IMAGE /root/.oldroot/nfs/images/Ubuntu-2404-noble-amd64-base.tar.gz
   EOF
   ```

5. Run the installer:

   ```bash
   installimage -a -c /autosetup
   ```

6. Set a strong LUKS passphrase and store it in your password manager.
7. Reboot.
8. Use the Hetzner console for the first unlock if SSH is not available yet.
9. Install Dropbear for remote unlock:

   ```bash
   apt update
   apt install -y dropbear-initramfs
   echo 'YOUR_SSH_PUBLIC_KEY' >> /etc/dropbear/initramfs/authorized_keys
   update-initramfs -u
   ```

10. Optional emergency kill switch:

    ```bash
    cat > /root/kill-switch.sh <<'EOF'
    #!/usr/bin/env bash
    set -euo pipefail
    cryptsetup erase /dev/sda2
    sync
    reboot -f
    EOF
    chmod 700 /root/kill-switch.sh
    ```

Use the kill switch only if you truly intend permanent data loss.

## Step 6 - WireGuard and Firewall

Time: about 20-30 minutes.

The goal is to make admin and agent services reachable only through your VPN.

1. Create a WireGuard client profile on your home router or VPN server.
2. Install WireGuard on the VPS:

   ```bash
   apt update
   apt install -y wireguard ufw
   ```

3. Copy the client profile to `/etc/wireguard/wg0.conf`.
4. Start WireGuard:

   ```bash
   systemctl enable --now wg-quick@wg0
   wg show
   ```

5. Configure the firewall. Keep public SSH open until you have verified VPN SSH:

   ```bash
   ufw default deny incoming
   ufw default allow outgoing
   ufw allow OpenSSH
   ufw allow 51820/udp
   ufw allow from <wireguard-subnet>/24
   ufw enable
   ```

6. Verify you can SSH through the WireGuard IP.
7. Then restrict SSH to the VPN:

   ```bash
   ufw delete allow OpenSSH
   ufw allow from <wireguard-subnet>/24 to any port 22
   ufw status verbose
   ```

## Step 7 - Create User, Directories, and Upload Local Data

Time: about 20-30 minutes.

Create the service user and private directories:

```bash
adduser --disabled-password --gecos "" hermes
install -d -m 700 -o hermes -g hermes /home/hermes/data
install -d -m 700 -o hermes -g hermes /home/hermes/data/books
install -d -m 700 -o hermes -g hermes /home/hermes/data/style
install -d -m 700 -o hermes -g hermes /home/hermes/.config/vigil
install -d -m 700 -o hermes -g hermes /home/hermes/bin
install -d -m 750 -o hermes -g hermes /var/log/vigil
install -d -m 700 -o hermes -g hermes /home/hermes/.ssh
cp /root/.ssh/authorized_keys /home/hermes/.ssh/authorized_keys
chown hermes:hermes /home/hermes/.ssh/authorized_keys
chmod 600 /home/hermes/.ssh/authorized_keys
```

Upload the files prepared in Steps 1-3 from your local machine:

```bash
scp -i ~/.ssh/hetzner_hermes ~/vigil-setup/reading_plan.json hermes@<vps-wireguard-ip>:/home/hermes/data/
scp -i ~/.ssh/hetzner_hermes ~/vigil-setup/contacts.json hermes@<vps-wireguard-ip>:/home/hermes/data/
scp -i ~/.ssh/hetzner_hermes -r ~/vigil-setup/books/* hermes@<vps-wireguard-ip>:/home/hermes/data/books/
scp -i ~/.ssh/hetzner_hermes -r ~/vigil-setup/style/* hermes@<vps-wireguard-ip>:/home/hermes/data/style/
```

Verify permissions on the VPS:

```bash
find /home/hermes/data -maxdepth 2 -type f -ls
```

## Step 8 - Clone and Configure Vigil

Time: about 30-45 minutes.

Install base packages:

```bash
apt update
apt install -y git curl ca-certificates python3.12 python3.12-venv python3-pip
```

Install `uv` for the service user:

```bash
sudo -iu hermes
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

Clone and verify the repo:

```bash
git clone https://github.com/<your-github-username>/vigil.git /home/hermes/vigil
cd /home/hermes/vigil
uv sync --dev
./scripts/check.sh --fast
```

Create the private environment file:

```bash
umask 077
cp /home/hermes/vigil/.env.example /home/hermes/.config/vigil/env
chmod 600 /home/hermes/.config/vigil/env
```

Edit `/home/hermes/.config/vigil/env`:

```bash
VIGIL_DATA_DIR=/home/hermes/data
VIGIL_RUNTIME_DIR=/home/hermes/data/runtime
VIGIL_TIMEZONE=America/New_York

WEATHER_LAT=35.2271
WEATHER_LON=-80.8431
WEATHER_TZ=America/New_York

ANYTYPE_API_KEY=
ANYTYPE_SPACE_ID=
TODOIST_API_TOKEN=

SNAPTRADE_CONSUMER_KEY=
SNAPTRADE_CLIENT_ID=
SNAPTRADE_USER_ID=
SNAPTRADE_USER_SECRET=
FRED_API_KEY=
ACCOUNT_MAP='{"PCRA - ROTH":"Roth","PCRA - PRE-TAX":"Traditional","HSA":"HSA"}'

OFX_BANKS_CONFIG='[]'
OFX_STATEMENTS_DIR=/home/hermes/data/ofx-statements

BIRTHDAY_USE_LLM=false
OPENROUTER_API_KEY=
```

Create the runner:

```bash
cat > /home/hermes/bin/vigil-run <<'SH'
#!/usr/bin/env bash
set -euo pipefail
set -a
. /home/hermes/.config/vigil/env
set +a
cd /home/hermes/vigil
exec uv run "$@"
SH
chmod 700 /home/hermes/bin/vigil-run
```

Validate Vigil before adding agents:

```bash
/home/hermes/bin/vigil-run python -m vigil.bible
/home/hermes/bin/vigil-run python -m vigil.weather
```

## Step 9 - Anytype Local-First Storage

Time: about 20-30 minutes.

Return to an admin/root shell for this step if you are still in the `hermes`
login shell from Step 8.

Install Anytype Heart with a pinned release and checksum:

```bash
cd /home/hermes/vigil
sudo ANYTYPE_USER=hermes \
  ANYTYPE_VERSION=<pinned-version-tag> \
  ANYTYPE_SHA256=<release-tarball-sha256> \
  ./scripts/install-anytype.sh
sudo systemctl start anytype
sudo systemctl status anytype --no-pager
```

Only use `ANYTYPE_SKIP_CHECKSUM=true` for short-lived lab testing. For personal
data, pin the version and verify the checksum.

Create an API key:

```bash
sudo -u hermes -H anytype auth apikey create --name vigil-daily-briefs
```

List spaces:

```bash
curl -H "Authorization: Bearer <ANYTYPE_API_KEY>" \
  -H "Anytype-Version: 2025-11-08" \
  http://127.0.0.1:31012/v1/spaces
```

Put the API key and target space ID into `/home/hermes/.config/vigil/env`.

Do not expose Anytype port `31012` publicly.

## Step 10 - Install Hermes Agent

Time: about 20-30 minutes.

Install as the `hermes` user. On an Ubuntu VPS, use the git installer first
because it avoids system Python package-management conflicts:

```bash
sudo -iu hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
```

PyPI is also supported if you manage the Python environment yourself:

```bash
python3 -m pip install hermes-agent
hermes postinstall
```

Choose a provider and verify chat:

```bash
hermes model
hermes --tui
hermes doctor
```

Hermes requires a model with at least a 64K token context window. Use
`hermes model` for provider setup rather than manually editing secrets.

Recommended safety setting if terminal access is enabled:

```bash
hermes config set terminal.backend docker
```

## Step 11 - Hermes Gateway, Messaging, and Task Bridges

Time: about 45-90 minutes depending on channels.

Set up the gateway only after a normal Hermes chat works.

```bash
hermes gateway setup
hermes gateway status
hermes tools
```

Install the gateway so cron jobs continue to fire:

```bash
hermes gateway install
```

For a server-level service, use the system install only if you understand which
user owns `~/.hermes`:

```bash
sudo hermes gateway install --system
```

For early testing:

```bash
hermes gateway
```

### 11a. Telegram

1. In Telegram, message `@BotFather`.
2. Create a bot with `/newbot`.
3. Configure Telegram through `hermes gateway setup`.
4. Set the home channel/chat ID if Hermes asks for one.
5. Send a test message to the bot.
6. Confirm `hermes gateway status` shows Telegram as healthy.

### 11b. Gmail or email

Configure email only after Telegram works. Start read-only and keep send actions
manual until drafts are consistently correct.

### 11c. Todoist Phase 2

Phase 1 reads Todoist through `TODOIST_API_TOKEN`. For Phase 2 task mutation,
add the Todoist MCP server or equivalent Hermes tool after `vigil brief` is
already reading tasks correctly.

### 11d. Signal, WhatsApp, SMS/RCS, GroupMe

Configure these as optional channels after Telegram is reliable. Use linked
device flows where possible, keep webhooks VPN-only, and test each channel with
one harmless message before allowing scheduled jobs to read it.

## Step 12 - OFX Direct Connect and Statement Imports

Time: about 20-45 minutes.

OFX lets Vigil pull bank balances and transactions without Plaid or SimpleFIN.

1. Look up your bank at <https://www.ofxhome.com>.
2. Record URL, ORG, FID, account number, and account type.
3. Enable Direct Connect or Quicken access at the bank if required.
4. Add a one-line JSON array to `OFX_BANKS_CONFIG`:

   ```bash
   OFX_BANKS_CONFIG='[{"name":"BankA","url":"https://ofx.banka.com/ofx","org":"BankAOrg","fid":"12345","user":"bank-user","pass":"bank-pass","accounts":[{"id":"checking-acct-num","type":"CHECKING"}]}]'
   ```

5. Create the statement import directory:

   ```bash
   sudo -u hermes mkdir -p /home/hermes/data/ofx-statements
   chmod 700 /home/hermes/data/ofx-statements
   ```

6. Put manually downloaded `.ofx` or `.qfx` files in that directory when Direct
   Connect is unavailable.
7. Test:

   ```bash
   /home/hermes/bin/vigil-run vigil monitor
   ```

Never commit bank credentials.

## Step 13 - Brokerage, FRED, and Financial Checklist

Time: about 30-60 minutes.

1. Create or copy `/home/hermes/data/financial_checklist.md`.
2. Configure SnapTrade:

   ```bash
   SNAPTRADE_CLIENT_ID=...
   SNAPTRADE_CONSUMER_KEY=...
   SNAPTRADE_USER_ID=...
   SNAPTRADE_USER_SECRET=...
   ACCOUNT_MAP='{"PCRA - ROTH":"Roth","PCRA - PRE-TAX":"Traditional","HSA":"HSA"}'
   ```

3. Get a free FRED API key from
   <https://fred.stlouisfed.org/docs/api/api_key.html>.
4. Add `FRED_API_KEY` to `/home/hermes/.config/vigil/env`.
5. Run:

   ```bash
   /home/hermes/bin/vigil-run vigil monitor
   ```

Expected JSON includes `status`, `alerts`, `brokerage_data`, `bank_data`,
`recession_data`, and `daily_summary` fields. Partial data should degrade
gracefully instead of failing the whole monitor.

## Step 14 - Weather Module

Time: about 10-20 minutes.

Set these values in `/home/hermes/.config/vigil/env`:

```bash
WEATHER_LAT=35.2271
WEATHER_LON=-80.8431
WEATHER_TZ=America/New_York
VIGIL_TIMEZONE=America/New_York
```

Test:

```bash
/home/hermes/bin/vigil-run python -m vigil.weather
```

Expected output includes today's hourly forecast and a 10-day forecast.

## Step 15 - Phase 1 Daily Brief

Time: about 15-30 minutes.

Run manually first:

```bash
sudo -iu hermes
/home/hermes/bin/vigil-run vigil brief
```

Verify:

```bash
ls -l /home/hermes/data/runtime
cat /home/hermes/data/runtime/daily_brief_state.json
```

Both runtime JSON files should be private (`0600`) when present.

Schedule Phase 1:

```bash
sudo -u hermes crontab -e
```

Add:

```cron
30 6 * * * /home/hermes/bin/vigil-run vigil brief >> /var/log/vigil/phase1.log 2>&1
```

## Step 16 - Hermes Phase 2 and Phase 3 Cron

Time: about 30-45 minutes.

Hermes cron runs inside the Hermes Gateway. The gateway ticks the scheduler
about once per minute and stores job output under `~/.hermes/cron/output/`.

Create the morning sweep:

```bash
hermes cron create "40 6 * * *" \
  "$(cat /home/hermes/vigil/prompts/morning_sweep.md)" \
  --workdir /home/hermes/vigil \
  --deliver telegram \
  --name "vigil-morning-sweep"
```

Create the periodic sweep:

```bash
hermes cron create "5 10,13,16,19,22 * * *" \
  "$(cat /home/hermes/vigil/prompts/periodic_sweep.md)" \
  --workdir /home/hermes/vigil \
  --deliver telegram \
  --name "vigil-periodic-sweep"
```

Check jobs:

```bash
hermes cron list
hermes cron status
hermes cron tick
```

To test a job without waiting for the next scheduled time:

```bash
hermes cron run <job_id>
```

Hermes and Vigil should run as the same user in this guide so Hermes can read
the repo prompts and `VIGIL_RUNTIME_DIR`.

## Step 17 - End-to-End Verification

Time: about 1-2 hours.

### 17a. Phase 1

```bash
/home/hermes/bin/vigil-run vigil brief
cat /home/hermes/data/runtime/daily_brief_state.json
cat /home/hermes/data/runtime/daily_brief_fm_output.json | python3 -m json.tool | head -40
```

Verify in Anytype:

- Parent object exists with today's date.
- Morning Bible/devotional object has content.
- Evening Bible/study notes object has content.
- Weather object has hourly and 10-day sections.
- Todoist object has today's tasks.
- Finance object exists.
- Birthday object is present only when relevant.

### 17b. Phase 2

Run the morning sweep manually through Hermes before trusting cron:

```bash
cd /home/hermes/vigil
hermes chat -q "$(cat prompts/morning_sweep.md)"
```

Verify:

- Text and email summaries are created.
- Draft replies are clearly labeled as drafts.
- Financial editorial uses the cached monitor output.
- Phase 2 did not duplicate Phase 1 objects.
- Any failure is reported to Telegram with enough detail to debug.

### 17c. Periodic sweep

1. Send yourself a harmless test message.
2. Let Hermes draft a reply.
3. Manually send the reply.
4. Run the periodic prompt and confirm the item is marked handled.
5. Leave one item unresolved overnight and verify morning carryover.

### 17d. Failure drills

Run these once before relying on the system:

- Temporarily break `ANYTYPE_API_KEY`, run `vigil brief`, and confirm it fails
  loudly.
- Temporarily break OFX config, run `vigil brief`, and confirm the rest of the
  brief still completes.
- Stop Anytype, run `vigil brief`, and confirm the error is obvious.
- Restore everything and run `./scripts/check.sh`.

## Execution Order and Time Budget

| Step | Description | Time | Depends on |
| --- | --- | ---: | --- |
| 1 | Reading content pipeline | 2-3 hrs | None |
| 2 | Contacts and Todoist | 30 min | None |
| 3 | Voice profiles | 1-2 hrs | None |
| 4 | Hetzner server | 15 min | None |
| 5 | LUKS encryption | 30-45 min | Step 4 |
| 6 | WireGuard and firewall | 20-30 min | Steps 4-5 |
| 7 | User, directories, upload data | 20-30 min | Steps 1-6 |
| 8 | Clone and configure Vigil | 30-45 min | Step 7 |
| 9 | Anytype local storage | 20-30 min | Step 8 |
| 10 | Hermes install | 20-30 min | Step 8 |
| 11 | Gateway and channels | 45-90 min | Step 10 |
| 12 | OFX bank setup | 20-45 min | Step 8 |
| 13 | Brokerage/FRED/checklist | 30-60 min | Step 8 |
| 14 | Weather | 10-20 min | Step 8 |
| 15 | Phase 1 cron | 15-30 min | Steps 9, 12-14 |
| 16 | Hermes cron | 30-45 min | Steps 10-15 |
| 17 | End-to-end verification | 1-2 hrs | All |
| | Total first setup | 9-14 hrs | |

## References

- Hermes quickstart: <https://hermes-agent.nousresearch.com/docs/getting-started/quickstart>
- Hermes CLI docs: <https://hermes-agent.nousresearch.com/docs/user-guide/cli>
- Hermes cron docs: <https://hermes-agent.nousresearch.com/docs/user-guide/features/cron/>
- FRED API key docs: <https://fred.stlouisfed.org/docs/api/api_key.html>
- OFX directory: <https://www.ofxhome.com>
