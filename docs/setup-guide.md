# Setup Guide — The Autonomous Daily Operations Center

Step-by-step instructions for deploying the full pipeline. Every step has been verified via internet research.

> [!CAUTION]
> **$0/yr data import strategy:** This plan uses **SnapTrade** (free tier, 5 connections) for brokerage data and **OFX Direct Connect** (free, built into most banks) for bank transactions. No Plaid, no SimpleFIN. See Step 12 and Step 13.

---

## Step 1 — Calibre Pipeline (Run on Mac)

**Time:** ~2-3 hours (one-time)

### 1a. Install Tools

1. Download **Kindle for Mac v1.39** from [archive.org](https://archive.org/details/kindle-for-mac) or a known mirror → install → **immediately disable auto-updates** (Kindle → Preferences → uncheck auto-update)
2. Download [Calibre](https://calibre-ebook.com/download_osx) → install
3. Download [DeDRM_tools_10.0.9.zip](https://github.com/noDRM/DeDRM_tools/releases/tag/v10.0.9) → unzip the outer zip (keep `DeDRM_plugin.zip` intact)
4. In Calibre → **Preferences** → **Plugins** → **Load plugin from file** → select `DeDRM_plugin.zip`
5. Also install **KFX Input** plugin: Preferences → Plugins → **Get plugins to enhance Calibre** → search for "KFX Input" → install

### 1b. Download and Process Books

1. Open Kindle for Mac → download all 5 books:
   - Good Morning Mercies
   - ESV Bible
   - Reformation Study Bible (ESV)
   - John MacArthur Study Bible (ESV)
   - ESV Study Bible
2. In Calibre → **Add books** → navigate to Kindle content folder (`~/Library/Application Support/Kindle/My Kindle Content/`) → import all 5
3. DeDRM automatically strips DRM during import — verify no errors in the import log
4. Select all 5 books → **Convert books** → Output format: **EPUB** → OK

### 1c. Convert to Markdown

1. Install Docling: `pip install docling`
2. Convert each EPUB to Markdown:
   ```bash
   docling convert good_morning_mercies.epub --to md --output ./markdown/
   docling convert esv_bible.epub --to md --output ./markdown/
   # repeat for all 5 books
   ```
3. If Docling struggles with any file, fallback to MarkItDown: `pip install markitdown`

### 1d. Generate Reading Plan JSON

1. Take the daily reading plan text and prompt an LLM to convert it to structured JSON:
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

### 1e. Transfer to VPS

1. SCP the files to the VPS (set `$VIGIL_DATA_DIR` first — e.g., `/home/openclaw/data`):
   ```bash
   scp -i ~/.ssh/hetzner_openclaw -r ./markdown/ root@<vps-wireguard-ip>:$VIGIL_DATA_DIR/books/
   scp -i ~/.ssh/hetzner_openclaw reading_plan.json root@<vps-wireguard-ip>:$VIGIL_DATA_DIR/
   ```

### 1f. Validate `vigil.bible` Parsing

The `vigil.bible` module was written against an assumed markdown format. After converting your EPUBs, you need to verify it can actually find passages in the real files.

1. Point `vigil.bible` at your converted markdown files locally:
   ```bash
   export READING_PLAN_PATH="./reading_plan.json"
   export BOOKS_DIR="./markdown/"
   uv run python -c "from vigil.bible import extract_today_reading; print(extract_today_reading())"
   ```
2. If the output is empty or errors:
   - Open one of the converted markdown files and check the heading format (e.g., `# Genesis 1` vs `## Chapter 1 — Genesis`)
   - Update `vigil/bible.py` to match the real heading patterns
   - Re-run the test suite: `uv run pytest tests/test_bible.py`
3. Repeat for the study Bible files — verify cross-referencing works for Reformation, MacArthur, and ESV study notes
4. Once parsing works, commit any changes to `src/vigil/bible.py` before deploying

---

## Step 2 — Contacts & Schedules

**Time:** ~30 min

### 2a. Birthday Contacts

1. Export birthday contacts from your phone as `.ics` file
2. Prompt an LLM to convert to JSON:
   ```json
   [
     { "name": "John Doe", "birthday": "1990-03-15", "relationship": "friend" },
     {
       "name": "Jane Smith",
       "birthday": "1985-07-22",
       "relationship": "family"
     }
   ]
   ```
3. Upload to VPS: `scp contacts.json root@<vps-ip>:$VIGIL_DATA_DIR/`

### 2b. Todoist Setup

1. In Todoist, create recurring tasks for:
   - Medication schedules (e.g., "Take medication" every day at 8 AM)
   - Trash/recycling reminders (e.g., "Take out trash" every Tuesday at 7 PM)
2. Get Todoist API Token: Todoist → **Settings** → **Integrations** → **Developer** → copy API token
3. Set env var: `export TODOIST_API_TOKEN="your-todoist-api-token"`

**Phase 1 (deterministic):** `vigil.anytype.todoist` uses the REST API to
fetch today's tasks and display them in the daily brief. This is handled
automatically by `vigil brief` — no MCP needed.

**Phase 2/3 (LLM):** The LLM uses the Todoist MCP server for task management
(completing tasks, adding new tasks, rescheduling). Install the
[official Todoist MCP](https://github.com/Doist/todoist-mcp) and configure
it in OpenClaw's MCP settings with your `TODOIST_API_TOKEN`.

---

## Step 3 — Generate Voice Profiles

**Time:** ~1-2 hours

### 3a. Morning Message Voice Profile

1. Compile 15-30 of your existing morning messages (texts, notes) into a
   single text file with `---` delimiters between messages.
2. Feed the messages to an LLM using the setup prompt at
   `prompts/setup/generate_voice_profile.md`.
3. Save the output as `style/morning_voice.md` in your data directory.
4. Upload to VPS:
   ```bash
   scp style/morning_voice.md root@<vps-ip>:$VIGIL_DATA_DIR/style/
   ```

### 3b. Reply Style Guide

1. Compile 15-30 of your replies to friends and contacts. Include the
   original message you were responding to for context. Use `---`
   delimiters between each exchange.
2. Feed the exchanges to an LLM using the setup prompt at
   `prompts/setup/generate_reply_style.md`.
3. Save the output as `style/reply_style.md` in your data directory.
4. Upload to VPS:
   ```bash
   scp style/reply_style.md root@<vps-ip>:$VIGIL_DATA_DIR/style/
   ```

> [!TIP]
> The voice profile approach distills your writing patterns into explicit
> instructions rather than relying on few-shot examples. This uses fewer
> tokens, produces more consistent output, and is easier to iterate on.
---

## Step 4 — Anytype Local-First Setup

**Time:** ~15 min

OpenClaw uses **Anytype** instead of Notion for all daily brief storage. Anytype is end-to-end encrypted and stores data locally on your VPS — no cloud account required.

1. Install the Anytype CLI on the VPS using the install script:
   ```bash
   sudo ./scripts/install-anytype.sh
   ```
   This auto-detects your architecture, downloads the latest release, installs
   the binary, and creates a systemd service. To pin a version:
   `sudo ANYTYPE_VERSION=v0.35.0 ./scripts/install-anytype.sh`

2. Start the Anytype headless server (the REST API runs on `http://127.0.0.1:31012`):
   ```bash
   # Add to systemd unit or start manually
   anytype serve &
   ```

3. Create an API key:
   ```bash
   anytype auth apikey create --name "openclaw-daily-briefs"
   # Output: your API key (e.g., eyJhbGc...)
   ```

4. Get your Space ID (Anytype calls workspaces "spaces"):
   ```bash
   curl -H "Authorization: Bearer <YOUR_API_KEY>" \
        -H "Anytype-Version: 2025-11-08" \
        http://127.0.0.1:31012/v1/spaces
   # Copy the id of the space where you want daily briefs (e.g., "space_abc123")
   ```

5. Store both values securely — you'll use them in Step 13c:
   - **API key** → `ANYTYPE_API_KEY`
   - **Space ID** → `ANYTYPE_SPACE_ID`

> [!IMPORTANT]
> Port 31012 must remain bound to `127.0.0.1` only. Never expose it publicly. The firewall rules in Step 7 already block external access.

---

> [!IMPORTANT]
> **Steps 5-16 require a running VPS.** Complete Steps 1-4 (free, local prep) before proceeding. Once you start Step 5, you begin paying for server time.

---

## Step 5 — Hetzner Account + CX23 Server

**Time:** ~15 min

1. Go to [hetzner.com/cloud](https://www.hetzner.com/cloud) → Sign up with email, verify, add payment method
2. In Hetzner Cloud Console → **Create Project** → name it `openclaw`
3. **Add SSH Key** (if you don't have one): `ssh-keygen -t ed25519 -f ~/.ssh/hetzner_openclaw`
4. Copy public key: `cat ~/.ssh/hetzner_openclaw.pub` → paste into Hetzner Cloud Console → SSH Keys
5. **Create Server:**
   - Location: **Falkenstein** (cheapest EU location)
   - Image: **Ubuntu 24.04**
   - Type: **CX23** (2 vCPU, 4 GB RAM, 40 GB NVMe)
   - SSH Key: select the one you added
   - Click **Create & Buy Now**
6. Note the server's **public IPv4 address**

---

## Step 6 — LUKS Full Disk Encryption

**Time:** ~30 min

LUKS encrypts your server's hard drive — if the server is seized or stolen, your data is unreadable without your passphrase.

1. In Hetzner Console → select your server → **Rescue** tab → **Enable Rescue** → select your SSH key
2. **Power cycle** the server (this boots into the rescue system)
3. SSH in: `ssh root@<server-ip> -i ~/.ssh/hetzner_openclaw`
4. Create install config:
   ```bash
   cat > /autosetup <<'EOF'
   DRIVE1 /dev/sda
   BOOTLOADER grub
   HOSTNAME openclaw
   PART /boot ext4 1G
   PART lvm vg0 all crypt
   LV vg0 root / ext4 all
   IMAGE /root/.oldroot/nfs/images/Ubuntu-2404-noble-amd64-base.tar.gz
   EOF
   ```
5. Run: `installimage -a -c /autosetup`
6. When prompted, set your LUKS encryption passphrase (store securely in password manager)
7. After install completes: `reboot`
8. **Remote unlock setup (Dropbear)** — to decrypt LUKS on reboot without console access:
   ```bash
   apt update && apt install dropbear-initramfs -y
   echo 'YOUR_SSH_PUBLIC_KEY' >> /etc/dropbear/initramfs/authorized_keys
   update-initramfs -u
   ```
9. Create the kill switch script:
   ```bash
   cat > /root/kill-switch.sh <<'EOF'
   #!/bin/bash
   cryptsetup erase /dev/sda2
   sync && reboot -f
   EOF
   chmod 700 /root/kill-switch.sh
   ```

   > [!CAUTION]
   > **This script permanently destroys ALL data on the server.** It erases the encryption key, making every file irrecoverable — even with the LUKS passphrase. Only use this in an emergency (e.g., server compromised, law enforcement seizure). There is **no undo**.

---

## Step 7 — WireGuard VPN (Connect VPS to Home Network)

**Time:** ~20 min

### On UniFi Dream Router:

1. Open UniFi Network → **Settings** → **VPN** → **VPN Server**
2. **Create New** → Type: **WireGuard** → Name: `openclaw-vps`
3. Select your WAN interface and port (default 51820 UDP)
4. Save (don't add clients yet)
5. Go to **Clients** → **Add Client** → Name: `hetzner-vps` → Select **Auto**
6. **Download the `.conf` file** — this is the client config for your VPS

### On the VPS:

7. SSH into VPS
8. Install WireGuard: `sudo apt update && sudo apt install wireguard -y`
9. Copy the downloaded `.conf` contents: `sudo nano /etc/wireguard/wg0.conf` → paste
10. Enable IP forwarding: `echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p`
11. Start: `sudo wg-quick up wg0`
12. Enable on boot: `sudo systemctl enable wg-quick@wg0`
13. Verify: `sudo wg show` (should show handshake with your UDR)

### Firewall (VPS):

14. Lock down the VPS:
    ```bash
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow from <wireguard-subnet>/24
    sudo ufw allow 51820/udp
    sudo ufw enable
    ```

---

## Step 8 — Install Coolify

**Time:** ~10 min

Coolify is a self-hosted alternative to Heroku or Vercel — it gives you a web dashboard to deploy and manage applications on your server without needing to know Docker commands.

1. SSH into VPS
2. Run the one-line installer:
   ```bash
   curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash
   ```
3. Wait for install to complete (~3-5 min) — it installs Docker, Traefik, and the Coolify dashboard
4. Access Coolify at `http://<vps-ip>:8000` (or via WireGuard IP)
5. Create your admin account on first login
6. **Important:** After setup, restrict port 8000 to WireGuard only:
   ```bash
   sudo ufw delete allow 8000
   sudo ufw allow from <wireguard-subnet>/24 to any port 8000
   ```

---

## Step 9 — Neon PostgreSQL Database

**Time:** ~10 min

1. Go to [neon.tech](https://neon.tech) → **Sign Up** (Google or email)
2. **Create Project:**
   - Name: `openclaw`
   - PostgreSQL version: **17**
   - Region: **AWS us-east-1** (or closest to Hetzner Falkenstein — **eu-central-1** if available)
3. Copy the **connection string** from the dashboard (format: `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`)
4. Open the **SQL Editor** and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pgcrypto;
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
5. Store the connection string securely — you'll need it for OpenClaw config

---

## Step 10 — Deploy OpenClaw via Coolify

**Time:** ~20 min

1. SSH into VPS
2. Clone OpenClaw:
   ```bash
   git clone https://github.com/openclaw/openclaw.git ~/openclaw
   cd ~/openclaw
   ```
3. Run the setup script: `./docker-setup.sh`
4. During onboarding, when prompted:
   - **AI Provider:** select **ChatGPT Plus OAuth** (`--auth-choice openai-codex`)
   - This bridges the $20/mo ChatGPT Plus subscription for GPT access
   - No per-token billing for primary LLM usage
5. Configure the Neon database connection in OpenClaw’s config (`~/.openclaw/config.json`):
   - Set the `DATABASE_URL` to your Neon connection string
6. Start: `docker compose up -d`
7. Check logs for `🦡 OPENCLAW READY` and note the Dashboard URL + auth token
8. Access the Control UI and save the auth token securely

### OpenRouter Setup (Fallback Models):

9. Go to [openrouter.ai](https://openrouter.ai) → Sign up → **Settings** → **API Keys** → create key
10. Add credits ($20 to start — fallback usage only)
11. Configure OpenRouter as the fallback provider in `~/.openclaw/config.json`:
    - Set `OPENROUTER_API_KEY` to your OpenRouter key
12. The key is used only when ChatGPT Plus OAuth fails or for specific fallback tasks

### LLM Model Strategy:

| Task | Primary (ChatGPT Plus OAuth) | Fallback (OpenRouter, reasoning on) |
|------|-----|---------|
| General summarization | GPT | Gemini Pro |
| Partner’s messages | GPT (special prompt + `morning_voice.md`) | Opus |
| General replies | GPT (special prompt + `reply_style.md`) | Sonnet |
| Image generation | — | — (9 text prompts only, no API image generation) |

### Security:

12. Set channel DM policy to `pairing` (unknown senders need approval)
13. Deny the `exec` command in OpenClaw permissions config
14. Ensure the Gateway is bound to `127.0.0.1`, not `0.0.0.0`

---

## Step 11 — Messaging Bridges (All Greenfield)

**Time:** ~45 min total

### 11a. Gmail

1. On **your existing Gmail account**, enable **2-Step Verification** if
   not already enabled.
2. Go to Google Account → **Security** → **App Passwords** → generate one for "Mail"
3. In OpenClaw, configure IMAP polling with the app password:
   - IMAP: `imap.gmail.com`, port 993, SSL (read-only)
   - Poll interval: 5 minutes
4. OpenClaw reads your inbox, summarizes emails, and drafts replies in
   Anytype. It does **not** send emails — you review and send manually.

> [!NOTE]
> No dedicated Gmail account is needed. OpenClaw reads from your existing
> inbox using IMAP with an App Password.

### 11b. WhatsApp

1. In OpenClaw dashboard → **Pairing** section
2. A QR code will appear
3. On your phone → WhatsApp → **Settings** → **Linked Devices** → **Link a Device** → scan the QR code
4. OpenClaw is now linked as a WhatsApp Web client

### 11c. Signal (Linked Device — No Second Number Needed)

1. SSH into VPS
2. Install Java (signal-cli requires it):
   ```bash
   sudo apt install default-jre -y
   ```
3. Download signal-cli from GitHub:
   ```bash
   # Check https://github.com/AsamK/signal-cli/releases for the latest version
   wget https://github.com/AsamK/signal-cli/releases/download/v0.13.x/signal-cli-0.13.x-Linux.tar.gz
   tar xf signal-cli-*.tar.gz
   sudo mv signal-cli-*/bin/signal-cli /usr/local/bin/
   sudo mv signal-cli-*/lib /usr/local/lib/signal-cli
   ```
4. Generate a linking URI (this links OpenClaw as a secondary device on YOUR number — like linking Signal Desktop):
   ```bash
   signal-cli link --name "OpenClaw-VPS"
   ```
5. This prints a `sgnl://linkdevice?uuid=...` URI. Convert it to a QR code:
   ```bash
   sudo apt install qrencode -y
   echo "sgnl://linkdevice?uuid=..." | qrencode -t ANSIUTF8
   ```
   Or paste the URI into any online QR code generator.
6. On your **Android phone** → Signal app → **Settings** → **Linked Devices** → **Link New Device** → scan the QR code
7. Approve the link on your phone
8. Verify: `signal-cli -u +1YOURNUMBER receive` (should receive recent messages)
9. Configure OpenClaw to use signal-cli as a channel. OpenClaw reads from signal-cli's message store.

> [!NOTE]
> This is the same as linking Signal Desktop. OpenClaw becomes a linked device on your existing number — it can read all your conversations and send messages as you. No second phone number needed.

### 11d. GroupMe

1. Install the community plugin: `openclaw channels add groupme`
2. Follow the interactive setup — it will guide you through:
   - Creating a GroupMe bot via [dev.groupme.com](https://dev.groupme.com)
   - Selecting the group
   - Configuring the webhook URL
3. Note: GroupMe Bot API does **not** support DMs, only group chats

### 11e. Text Messages — SMS/RCS (Android)

Since you're on Android, use the **SMS Gateway for Android** app to turn your phone into a text message bridge that OpenClaw can read from. The app captures both SMS and RCS messages — they're indistinguishable at the gateway level.

1. On your **Android phone**, install [SMS Gateway for Android](https://play.google.com/store/apps/details?id=com.sms.gateway) from the Play Store
2. Open the app → enable the SMS gateway service → note the **local IP** and **port** it provides (or use the cloud mode)
3. In the app settings:
   - Enable **webhook forwarding** for incoming SMS
   - Set the webhook URL to: `http://<vps-wireguard-ip>:<openclaw-gateway-port>/hooks/sms`
   - The app will POST incoming SMS messages to OpenClaw automatically
4. On the VPS, install the OpenClaw SMS gateway plugin:
   ```bash
   openclaw channels add sms-gateway
   ```
5. During setup, configure:
   - **Gateway URL:** the IP/port of your Android phone's SMS Gateway app (or cloud API endpoint)
   - **Webhook secret:** set a shared secret for authentication
6. Send yourself a test SMS → verify it appears in OpenClaw
7. **Keep the app running on your phone** — it must stay active to relay SMS messages

> [!TIP]
> The SMS Gateway app uses minimal battery. Enable Android's battery optimization exception for it to prevent the OS from killing it in the background: **Settings** → **Apps** → **SMS Gateway** → **Battery** → **Unrestricted**.

### 11f. Telegram (Primary Chat Interface)

Telegram is your primary way to interact with OpenClaw — mark Todoist tasks complete, request Anytype updates, query weather, check your portfolio, etc. OpenClaw has a **native Telegram channel plugin** as part of its hub-and-spoke Gateway architecture.

1. Open Telegram → search for [@BotFather](https://t.me/BotFather) (verified account with blue checkmark)
2. Send `/newbot` → follow the prompts:
   - **Display name:** e.g., "OpenClaw"
   - **Username:** must end in `_bot`, e.g., `openclaw_assistant_bot`
3. BotFather will reply with a **Bot Token** (a long string like `123456:ABC-DEF...`). Copy it.
4. Configure the Telegram channel in OpenClaw:
   ```bash
   openclaw config set telegram.bot_token "YOUR_BOT_TOKEN"
   ```
5. Get your Telegram chat ID:
   - Send any message to your new bot in Telegram
   - Run: `curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}` in the response — that's your chat ID
6. Restrict the bot to only respond to your chat:
   ```bash
   openclaw config set telegram.allowed_chat_ids "YOUR_CHAT_ID"
   ```
7. Restart the OpenClaw Gateway to activate the channel
8. **Pair your account:** Send `/start` or "Hello" to the bot in Telegram. The bot replies with a pairing code (e.g., `PAIR-ABC123`). Approve it:
   ```bash
   openclaw pairing approve telegram PAIR-ABC123
   ```
9. Verify: send a message to the bot → it should respond via the configured LLM

> [!NOTE]
> OpenClaw supports multiple channel plugins simultaneously (Telegram, WhatsApp, Signal, Discord, Slack, iMessage, email). Telegram is recommended as the primary interactive channel because it's fast, supports rich formatting, and works on all platforms.

---

## Step 12 — OFX Direct Connect (Bank Transactions)

**Time:** ~20 min

OFX Direct Connect is the same technology that Quicken, Mint, and other financial apps use to talk to your bank. It lets `vigil.financial.monitor` pull your account balances and recent transactions directly from your bank's servers — no third-party aggregator like Plaid, no monthly fees.

### Find Your Bank's OFX Settings:

1. Go to [ofxhome.com](https://www.ofxhome.com) → search for your bank(s)
2. For each bank, note these three values:
   - **OFX URL** — the bank's OFX server endpoint (e.g., `https://ofx.chase.com`)
   - **ORG** — the organization identifier (e.g., `B1`)
   - **FID** — the financial institution ID (e.g., `10898`)
3. If your bank isn't listed on ofxhome.com:
   - Check your bank's website for "Quicken Direct Connect" settings (same OFX credentials)
   - Download a `.qfx` or `.ofx` file from your bank's online portal → open in a text editor → the `ORG` and `FID` values are in the header
   - Contact your bank's support to request Direct Connect activation

### Gather Account Numbers:

4. For each bank account you want to monitor, note:
   - **Account number** (from your bank's online portal)
   - **Account type** — `CHECKING`, `SAVINGS`, or `MONEYMRKT`
5. You'll also need your **online banking username and password** for each bank

### Configure the `OFX_BANKS_CONFIG` Environment Variable:

6. Set the env var as a JSON array (add to `~/.bashrc` or `.env`):
   ```bash
   export OFX_BANKS_CONFIG='[
     {
       "name": "Chase",
       "url": "https://ofx.chase.com",
       "org": "B1",
       "fid": "10898",
       "user": "your-chase-username",
       "pass": "your-chase-password",
       "accounts": [
         {"id": "123456789", "type": "CHECKING"},
         {"id": "987654321", "type": "SAVINGS"}
       ]
     }
   ]'
   ```
   Add additional objects to the array for each bank.

### Test the Connection:

7. Run the financial monitor to verify OFX fetches work:
   ```bash
   uv run python -m vigil.financial.monitor
   ```
8. Check the JSON output — `bank_data` should contain your accounts and recent transactions. If it shows `null`, check stderr for OFX error messages.

> [!IMPORTANT]
> OFX Direct Connect uses your online banking credentials. Store them securely in environment variables or a `.env` file (already in `.gitignore`). Never commit credentials to version control.

> [!NOTE]
> Some banks may require you to enable "Direct Connect" or "Quicken access" in your online banking settings before OFX will work. If you get authentication errors, check your bank's help pages for Direct Connect setup instructions.

---

## Step 13 — Financial Health Monitor

**Time:** ~30 min

> [!NOTE]
> The `vigil.financial.monitor` module is **pre-built** and ready for deployment. You only need to port your checklist, transfer files, and configure environment variables.

### 13a. Prep — Port the Financial Checklist

1. Port your existing financial checklist to a clean Markdown file:

   ```markdown
   # Financial Health Checklist

   ## Red Flags

   - [ ] Any charge > $500 not from a known vendor
   - [ ] Account balance drops below $1,000
   - [ ] Dividend payment missed or reduced
   - [ ] Portfolio allocation drifts > 5% from target
   - [ ] Recurring payment fails

   ## Accounts

   - Fidelity HSA
   - Schwab PRSA
   ```

2. Upload to VPS: `scp financial_checklist.md root@<vps-ip>:$VIGIL_DATA_DIR/`

### 13b. Deploy Financial Monitor Scripts

The financial monitor is **pre-built** as 4 modules: `vigil.financial.monitor` (orchestrator), `vigil.config` (configuration), `vigil.financial.fetchers` (data fetching), and `vigil.financial.evaluators` (evaluation logic). It integrates the **Chairman's Final Portfolio Allocation** (all 7 tickers, 4 accounts) with OFX Direct Connect bank data, FRED recession indicators, and hyperscaler capex tracking.

1. Install dependencies on the VPS:

   ```bash
   uv sync  # deps defined in pyproject.toml
   ```

2. Clone the Vigil repo on the VPS:

   ```bash
   git clone https://github.com/<your-github-username>/vigil.git /home/openclaw/vigil
   cd /home/openclaw/vigil && uv sync --dev
   ```

   > [!NOTE]
   > Portfolio allocation targets are codified in `vigil.financial.evaluators`
   > — no separate document upload needed. Edit the Python constants to
   > change targets.

3. Get a free FRED API key:
   - Go to https://fred.stlouisfed.org/docs/api/api_key.html
   - Sign up / log in with a free FRED account
   - Request an API key (immediate, free)

4. Set environment variables (add to `~/.bashrc` or a `.env` file):

   ```bash
   export SNAPTRADE_CLIENT_ID="your-client-id"
   export SNAPTRADE_CONSUMER_KEY="your-consumer-key"
   export SNAPTRADE_USER_ID="openclaw-user"
   export SNAPTRADE_USER_SECRET="your-user-secret"
   export FRED_API_KEY="your-fred-api-key"
   # Account name mapping (SnapTrade account names → portfolio categories)
   export ACCOUNT_MAP='{"PCRA - ROTH": "Roth", "PCRA - PRE-TAX": "Traditional", "HSA": "HSA"}'
   # OFX bank config — JSON array supporting multiple banks, each with multiple accounts
   # Find URL/ORG/FID for each bank at ofxhome.org
   export OFX_BANKS_CONFIG='[
     {
       "name": "BankA",
       "url": "https://ofx.banka.com/ofx",
       "org": "BankAOrg",
       "fid": "12345",
       "user": "your-banka-username",
       "pass": "your-banka-password",
       "accounts": [
         {"id": "checking-acct-num", "type": "CHECKING"},
         {"id": "savings-acct-num", "type": "SAVINGS"}
       ]
     }
   ]'
   # Telegram bot token is configured via OpenClaw config (see Telegram section)
   # Weather location (Open-Meteo, free, no key needed)
   export WEATHER_LAT="35.2271"
   export WEATHER_LON="-80.8431"
   export WEATHER_TZ="America/New_York"
   # Data directory — all file paths (reading plan, books, contacts) derive from this
   export VIGIL_DATA_DIR="/home/openclaw/data"
   ```

5. Test: `uv run python -m vigil.financial.monitor`

**What the script monitors:**

- **Bank accounts** (via OFX Direct Connect): Low balances, large unknown transactions, failed payments
- **Portfolio drift** (via SnapTrade): Uses true portfolio weights from brokerage positions for exact drift detection against target allocations
- **Mid-year triggers** (from the Chairman's doc):
  - BTC < $50k → trim IBIT to 3%
  - BTC > $200k → trim IBIT to 4%, profits into COWZ
  - DXY > 105 → reduce VEA to 5%
  - NLR down 20%+ from high → buy the dip
  - AVUV trails S&P by 8%+ over 3 months → trim to 8%
- **Recession signals** (via FRED API):
  - Unemployment rate > 5% → raise COWZ to 20%
  - Yield curve inverted (10Y-2Y spread negative) → raise COWZ to 20%
  - Sahm Rule triggered (≥ 0.50) → CRITICAL recession alert
- **Hyperscaler capex** (via yfinance quarterly cash flows):
  - Tracks MSFT, AMZN, META, GOOGL quarterly capex
  - Flags if any cut capex >15% YoY → trim SMH to 18%
- **Daily summary**: Prices, daily change, 3-month returns for all 7 tickers + BTC + DXY + recession indicators + capex data

**Output categories:** `account` | `drift` | `trigger` | `recession` | `capex` | `system`

> [!IMPORTANT]
> **SnapTrade provides true portfolio weights.** The script pulls individual ETF holdings (ticker, shares, market value) from Schwab and Fidelity via SnapTrade, enabling exact drift detection and IBIT percentage tracking.

> [!NOTE]
> The script includes the portfolio targets hardcoded from the March 2026 allocation. If you rebalance or change targets, update the `OVERALL_TARGETS`, `ROTH_TARGETS`, `TRADITIONAL_TARGETS`, and `HSA_TARGETS` dicts in the script.

6. Test the script manually: `uv run python -m vigil.financial.monitor`

### 13c. Deploy Anytype Modules

The daily brief object builder is **pre-built** as 7 modules that create each Anytype sub-object without using the LLM. These run as Phase 1 of the morning sweep (see Step 15b).

1. Transfer all Anytype modules and their helpers to the VPS:

    git clone https://github.com/<your-github-username>/vigil.git /home/openclaw/vigil
    cd /home/openclaw/vigil && uv sync --dev

2. Set the additional environment variables (add to the same `.env` file from Step 13b):

   ```bash
   export ANYTYPE_API_KEY="your-anytype-api-key"                   # from Step 4
   export ANYTYPE_SPACE_ID="your-space-id"                         # from Step 4
   export TODOIST_API_TOKEN="your-todoist-api-token"               # from Step 2b
   export BIRTHDAY_USE_LLM="false"                                 # set to "true" to use Sonnet for birthday messages
   # CONTACTS_PATH, READING_PLAN_PATH, BOOKS_DIR all derive from VIGIL_DATA_DIR (set in Step 13b)
   ```

3. Test the Anytype writer:

   ```bash
   cd /home/openclaw/vigil && uv run vigil brief
   ```

   You should see JSON output with `parent_object_id` and `sub_objects`. Open Anytype on any device synced to your VPS — a new daily brief object should appear with Bible, weather, to-do, and finance sub-objects.

---

## Step 14 — Weather Module (`vigil.weather`)

**Time:** ~20 min

1. Dependencies are included in `pyproject.toml` — no separate install needed (`uv sync` covers it).

2. The weather module lives at `src/vigil/weather.py` (installed as part of the `vigil` package). It uses `httpx` (no numpy/pandas dependency) with a 10-second timeout.

3. **Update the coordinates** via env vars: `WEATHER_LAT`, `WEATHER_LON`, `WEATHER_TZ`
4. Test: `uv run python -m vigil.weather`
5. Verify the output includes today's hourly breakdown + 10-day forecast with WMO weather code emoji

---

## Step 15 — Configure OpenClaw Cron Jobs + RISEN Prompts

**Time:** ~30 min

All prompts below use the **RISEN framework** (Role, Instructions, Steps, End Goal, Narrowing) from the [prompt-architect](file:///home/cmobley/Documents/Projects/Reports/openclaw/tmp/claude-skill-prompt-architect/prompt-architect/SKILL.md) skill for maximum effectiveness.

### 15a. Create HEARTBEAT.md

On the VPS, create the heartbeat checklist:

The heartbeat checklist is version-controlled at `prompts/heartbeat.md`.
Copy it to the VPS:
```bash
scp prompts/heartbeat.md root@<vps-ip>:~/openclaw/workspace/HEARTBEAT.md
```

### 15b. Phase 1 — Deterministic Objects (6:30 AM)

`vigil brief` creates the daily brief parent object and all deterministic sub-objects (Bible, weather, to-do, finance, birthdays) without using the LLM. It writes a state file at `/tmp/daily_brief_state.json` that Phase 2 reads.

```bash
# Phase 1: deterministic objects (~1-2 min, no LLM cost)
crontab -e
# Add this line:
30 6 * * * cd /home/openclaw/vigil && /home/openclaw/.local/bin/uv run vigil brief >> /var/log/openclaw/phase1.log 2>&1
```

### 15c. Phase 2 — LLM Morning Sweep (6:40 AM)

The LLM reads the state file from Phase 1, then fills in the sub-pages that require intelligence: messages, drafted replies, financial editorial, and the morning message.

```bash
openclaw cron add \
  --name "morning-sweep" \
  --schedule "40 6 * * *" \
  --isolated \
  --prompt-file ~/openclaw/workspace/prompts/morning_sweep.md
```

The prompt file is version-controlled at `prompts/morning_sweep.md`.
Copy it to the VPS:
```bash
scp prompts/morning_sweep.md root@<vps-ip>:~/openclaw/workspace/prompts/
```

### 15d. Periodic Sweep Cron Job (Every 3 Hours)

```bash
openclaw cron add \
  --name "periodic-sweep" \
  --schedule "0 10,13,16,19,22 * * *" \
  --isolated \
  --prompt-file ~/openclaw/workspace/prompts/periodic_sweep.md
```

The prompt file is version-controlled at `prompts/periodic_sweep.md`.
Copy it to the VPS:
```bash
scp prompts/periodic_sweep.md root@<vps-ip>:~/openclaw/workspace/prompts/
```

---

## Step 16 — End-to-End Verification

**Time:** ~1-2 hours

### 16a. Test Phase 1 (Deterministic Objects)

Run `vigil brief` manually and verify the output:

```bash
cd /home/openclaw/vigil && uv run vigil brief
```

1. Verify the state file was created:
   ```bash
   cat /tmp/daily_brief_state.json
   ```
   - [ ] `space_id` matches your Anytype space
   - [ ] `parent_object_id` is a valid Anytype object ID
   - [ ] `sub_objects.morning_bible` is not null
   - [ ] `sub_objects.evening_bible` is not null
   - [ ] `sub_objects.weather` is not null
   - [ ] `sub_objects.todoist` is not null
   - [ ] `sub_objects.finance` is not null (object exists but is **empty** — this is intentional)
   - [ ] `sub_objects.birthdays` is null (expected if no birthdays today) or a valid ID

2. Verify the FM cache was created:
   ```bash
   cat /tmp/daily_brief_fm_output.json | python3 -m json.tool | head -20
   ```
   - [ ] Contains `brokerage_data` and `bank_data` keys

3. Open Anytype (on any synced device) and verify:
   - [ ] Parent object exists with today's date as title
   - [ ] 📖 Morning Bible Reading has devotional text
   - [ ] 🌙 Evening Bible Reading has ESV text + 3 study note toggles
   - [ ] 🌤️ Weather has hourly + 10-day Markdown tables
   - [ ] ✅ To-Do List has Todoist tasks
   - [ ] 📈 Stocks & Finances object exists but is **empty** (no content yet)
   - [ ] 🎂 Birthdays skipped if no birthdays today

### 16b. Test Phase 2 (LLM Sweep)

Manually trigger the morning sweep via the OpenClaw CLI:

```bash
openclaw run --prompt-file ~/openclaw/workspace/prompts/morning_sweep.md
```

1. Verify LLM-created sub-objects:
   - [ ] 💬 Texts sub-object shows message summaries with drafted replies
   - [ ] 📧 Emails sub-object shows email summaries with drafted replies
   - [ ] 💌 Morning Message has a drafted message + 3 Nano Banana images
   - [ ] 📈 Stocks & Finances now has 🔴 Action Items + 🌍 Economy Snapshot editorial at the **top**, followed by portfolio, balances, and transaction tables **below**

2. Verify Phase 2 did NOT duplicate Phase 1 objects:
   - [ ] Only one 📖 Morning Bible Reading exists (not two)
   - [ ] Only one 🌤️ Weather exists (not two)

### 16c. Test Periodic Sweep

3. **Test reply tracking:** Send yourself a test message, let OpenClaw draft a reply, then manually send the reply. On the next periodic sweep, verify it's marked with ~~strikethrough~~
4. **Test carryover:** Leave a message unreplied overnight. Next morning, verify it appears as a carryover item marked "⏳ CARRYOVER"

### 16d. Test Failure Modes

5. **Phase 1 failure:** Temporarily break the `ANYTYPE_API_KEY` → run `vigil brief` → verify it exits with an error. Then trigger Phase 2 → verify the LLM sends a Telegram alert and creates a partial brief.
6. **Financial monitor failure:** Temporarily break OFX config → run `vigil brief` → verify the finance sub-object is still created (empty) and the state file still has all other sub-objects.
7. **Weather script:** Run `uv run python -m vigil.weather` manually → verify JSON output includes today's hourly + 10-day forecast.

---

## Execution Order Summary

Follow the steps in order — Steps 1-4 are free local prep, Steps 5-16 require the VPS.

| Step | Description                      | Duration        | Dependencies             |
| ---- | -------------------------------- | --------------- | ------------------------ |
| 1    | Calibre pipeline (Mac)           | 2-3 hrs         | None                     |
| 2    | Contacts & Schedules             | 30 min          | None                     |
| 3    | Compile morning messages         | 1-2 hrs         | None                     |
| 4    | Anytype local-first setup        | 15 min          | None                     |
| 5    | Hetzner account + server         | 15 min          | None                     |
| 6    | LUKS encryption                  | 30 min          | Step 5                   |
| 7    | WireGuard VPN                    | 20 min          | Steps 5-6                |
| 8    | Coolify                          | 10 min          | Steps 5-7                |
| 9    | Neon PostgreSQL                  | 10 min          | None (parallel with 5-8) |
| 10   | OpenClaw deployment              | 20 min          | Steps 8-9                |
| 11   | Messaging bridges                | 45 min          | Step 10                  |
| 12   | OFX Direct Connect banks         | 20 min          | Step 5                   |
| 13a-b| Financial monitor                | 30 min          | Steps 10, 12             |
| 13c  | Anytype modules                  | 15 min          | Steps 4, 13a-b           |
| 14   | Weather script                   | 20 min          | Step 10                  |
| 15   | Cron jobs (Phase 1 + 2) + RISEN  | 30 min          | Steps 10-14              |
| 16   | E2E verification                 | 1-2 hrs         | All                      |
|      | **Total estimated time**         | **~9-13 hours** |                          |

