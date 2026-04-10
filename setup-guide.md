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

1. SCP the files to the VPS:
   ```bash
   scp -i ~/.ssh/hetzner_openclaw -r ./markdown/ root@<vps-wireguard-ip>:/home/openclaw/data/books/
   scp -i ~/.ssh/hetzner_openclaw reading_plan.json root@<vps-wireguard-ip>:/home/openclaw/data/
   ```

### 1f. Validate `bible_reading.py` Parsing

The `bible_reading.py` script was written against an assumed markdown format. After converting your EPUBs, you need to verify it can actually find passages in the real files.

1. Point `bible_reading.py` at your converted markdown files locally:
   ```bash
   export READING_PLAN_PATH="./reading_plan.json"
   export BOOKS_DIR="./markdown/"
   uv run python -c "from bible_reading import get_todays_reading; print(get_todays_reading())"
   ```
2. If the output is empty or errors:
   - Open one of the converted markdown files and check the heading format (e.g., `# Genesis 1` vs `## Chapter 1 — Genesis`)
   - Update `bible_reading.py` to match the real heading patterns
   - Re-run the test suite: `uv run pytest tests/test_bible_reading.py`
3. Repeat for the study Bible files — verify cross-referencing works for Reformation, MacArthur, and ESV study notes
4. Once parsing works, commit any changes to `bible_reading.py` before deploying

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
3. Upload to VPS: `scp contacts.json root@<vps-ip>:/home/openclaw/data/`

### 2b. Todoist Setup

1. In Todoist, create recurring tasks for:
   - Medication schedules (e.g., "Take medication" every day at 8 AM)
   - Trash/recycling reminders (e.g., "Take out trash" every Tuesday at 7 PM)
2. Get Todoist API Token: Todoist → **Settings** → **Integrations** → **Developer** → copy API token
3. Set env var: `export TODOIST_API_TOKEN="your-todoist-api-token"`
4. Configure the Todoist MCP server for OpenClaw (provides full CRUD: complete
   tasks, add tasks, reschedule). No Python script needed.
   Install the [official Todoist MCP SDK](https://github.com/Doist/todoist-mcp) and
   configure it in OpenClaw's MCP settings with your `TODOIST_API_TOKEN`.

---

## Step 3 — Compile Morning Messages

**Time:** ~1-2 hours

1. Locate your existing morning messages (texts, notes, documents)
2. Compile them into a single text file with clear delimiters:

   ```
   --- Message 2026-01-01 ---
   Good morning my beautiful...

   --- Message 2026-01-02 ---
   Rise and shine my gorgeous...
   ```

3. Upload to VPS: `scp morning_messages.txt root@<vps-ip>:/home/openclaw/data/`
4. This file serves as the few-shot training prompt for Opus 4.6

---

## Step 4 — Notion Account + Integration

**Time:** ~15 min

1. Go to [notion.so](https://www.notion.so) → Sign up (free plan is sufficient)
2. Create a workspace
3. Create a **full-page database** called **"Daily Briefs"**:
   - Click **+ New page** in the sidebar → select **Table** (not "Empty page")
   - Name it **"Daily Briefs"**
   - This creates a database (a structured container that `notion_writer.py` can add entries to)
4. **Get the Database ID** — you'll need this for the `NOTION_DAILY_BRIEFS_DB` env var:
   - Open the Daily Briefs database in your browser
   - The URL looks like: `https://www.notion.so/your-workspace/Daily-Briefs-abc123def456...`
   - The **32-character hex string** after the page name (e.g., `abc123def456...`) is your database ID
   - Copy it — you'll paste it into the `.env` file in Step 13c
5. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New Integration**
   - Name: `OpenClaw Daily Brief`
   - Associated workspace: your workspace
   - Capabilities: **Read, Update, Insert content**
6. Copy the **Internal Integration Token** (starts with `ntn_`) — this is your `NOTION_TOKEN`
7. Go back to your "Daily Briefs" database → click `...` → **Connections** → **Add Connection** → select your integration (this grants the integration permission to read and write to this database)
8. Store both values securely — you'll use them in Step 13c:
   - **Integration token** (`ntn_...`) → `NOTION_TOKEN`
   - **Database ID** (32-char hex) → `NOTION_DAILY_BRIEFS_DB`

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
   - **AI Provider:** select **OpenRouter**
   - **API Key:** paste your OpenRouter API key
   - **Default Model:** enter `anthropic/claude-sonnet-4-6`
5. Configure the Neon database connection in OpenClaw's config (`~/.openclaw/config.json`):
   - Set the `DATABASE_URL` to your Neon connection string
6. Start: `docker compose up -d`
7. Check logs for `🦞 OPENCLAW READY` and note the Dashboard URL + auth token
8. Access the Control UI and save the auth token securely

### OpenRouter Setup:

9. Go to [openrouter.ai](https://openrouter.ai) → Sign up → **Settings** → **API Keys** → create key
10. Add credits ($20 to start)
11. The key was already configured during step 4 above

### Security:

12. Set channel DM policy to `pairing` (unknown senders need approval)
13. Deny the `exec` command in OpenClaw permissions config
14. Ensure the Gateway is bound to `127.0.0.1`, not `0.0.0.0`

---

## Step 11 — Messaging Bridges (All Greenfield)

**Time:** ~45 min total

### 11a. Gmail

1. Create a **dedicated Gmail account** for OpenClaw (e.g., `openclaw.bot@gmail.com`)
2. Enable **2-Step Verification** on the account
3. Go to Google Account → **Security** → **App Passwords** → generate one for "Mail"
4. In OpenClaw, configure IMAP/SMTP polling with the app password:
   - IMAP: `imap.gmail.com`, port 993, SSL
   - SMTP: `smtp.gmail.com`, port 587, TLS
   - Poll interval: 5 minutes

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

### 11e. SMS (Android)

Since you're on Android, use the **SMS Gateway for Android** app to turn your phone into an SMS bridge that OpenClaw can read from.

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

Telegram is your primary way to interact with OpenClaw — mark Todoist tasks complete, request Notion updates, query weather, check your portfolio, etc. OpenClaw has a **native Telegram channel plugin** as part of its hub-and-spoke Gateway architecture.

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

OFX Direct Connect is the same technology that Quicken, Mint, and other financial apps use to talk to your bank. It lets `financial_monitor.py` pull your account balances and recent transactions directly from your bank's servers — no third-party aggregator like Plaid, no monthly fees.

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
   uv run python financial_monitor.py
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
> The `financial_monitor.py` script is **pre-built** and ready for deployment. You only need to port your checklist, transfer files, and configure environment variables.

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

2. Upload to VPS: `scp financial_checklist.md root@<vps-ip>:/home/openclaw/data/`

### 13b. Deploy Financial Monitor Scripts

The financial monitor is **pre-built** as 4 modules: [financial_monitor.py](file:///home/cmobley/Documents/Projects/Reports/openclaw/financial_monitor.py) (orchestrator), [fm_config.py](file:///home/cmobley/Documents/Projects/Reports/openclaw/fm_config.py) (configuration), [fm_fetchers.py](file:///home/cmobley/Documents/Projects/Reports/openclaw/fm_fetchers.py) (data fetching), and [fm_evaluators.py](file:///home/cmobley/Documents/Projects/Reports/openclaw/fm_evaluators.py) (evaluation logic). It integrates the **Chairman's Final Portfolio Allocation** (all 7 tickers, 4 accounts) with OFX Direct Connect bank data, FRED recession indicators, and hyperscaler capex tracking.

1. Install dependencies on the VPS:

   ```bash
   uv sync  # deps defined in pyproject.toml
   ```

2. Transfer the scripts + portfolio doc to the VPS:

   ```bash
   scp -i ~/.ssh/hetzner_openclaw financial_monitor.py fm_config.py fm_fetchers.py fm_evaluators.py root@<vps-wireguard-ip>:/home/openclaw/data/scripts/
   scp -i ~/.ssh/hetzner_openclaw 2026_chairman_final_portfolio.md root@<vps-wireguard-ip>:/home/openclaw/data/
   ```

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
   # Bible reading plan paths
   export READING_PLAN_PATH="/home/openclaw/data/reading_plan.json"
   export BOOKS_DIR="/home/openclaw/data/books"
   ```

5. Test: `python3 /home/openclaw/data/scripts/financial_monitor.py`

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

6. Test the script manually: `python3 /home/openclaw/data/scripts/financial_monitor.py`

### 13c. Deploy Notion Modules

The daily brief page builder is **pre-built** as 7 modules that create each Notion sub-page without using the LLM. These run as Phase 1 of the morning sweep (see Step 15b).

1. Transfer all Notion modules and their helper to the VPS:

   ```bash
   scp -i ~/.ssh/hetzner_openclaw \
     notion_client.py \
     notion_bible.py \
     notion_weather.py \
     notion_todoist.py \
     notion_finance.py \
     notion_birthdays.py \
     notion_writer.py \
     bible_reading.py \
     root@<vps-wireguard-ip>:/home/openclaw/data/scripts/
   ```

2. Set the additional environment variables (add to the same `.env` file from Step 13b):

   ```bash
   export NOTION_TOKEN="ntn_your-notion-integration-token"        # from Step 4
   export NOTION_DAILY_BRIEFS_DB="your-32-char-database-id"       # from Step 4
   export TODOIST_API_TOKEN="your-todoist-api-token"               # from Step 2b
   export CONTACTS_PATH="/home/openclaw/data/contacts.json"        # from Step 2a
   export BIRTHDAY_USE_LLM="false"                                 # set to "true" to use Sonnet for birthday messages
   ```

3. Test the Notion writer:

   ```bash
   cd /home/openclaw/data/scripts && uv run python3 notion_writer.py
   ```

   You should see JSON output with `parent_page_id` and `sub_pages`. Check your Notion workspace — a new daily brief page should appear with Bible, weather, to-do, and finance sub-pages.

---

## Step 14 — Weather Script (`weather_fetch.py`)

**Time:** ~20 min

1. Dependencies are included in `pyproject.toml` — no separate install needed (`uv sync` covers it).

2. The `weather_fetch.py` script is a standalone file at `/home/openclaw/data/scripts/weather_fetch.py`. It uses `httpx` (no numpy/pandas dependency) with a 10-second timeout.

3. **Update the coordinates** via env vars: `WEATHER_LAT`, `WEATHER_LON`, `WEATHER_TZ`
4. Test: `uv run python /home/openclaw/data/scripts/weather_fetch.py`
5. Verify the output includes today's hourly breakdown + 10-day forecast with WMO weather code emoji

---

## Step 15 — Configure OpenClaw Cron Jobs + RISEN Prompts

**Time:** ~30 min

All prompts below use the **RISEN framework** (Role, Instructions, Steps, End Goal, Narrowing) from the [prompt-architect](file:///home/cmobley/Documents/Projects/Reports/openclaw/tmp/claude-skill-prompt-architect/prompt-architect/SKILL.md) skill for maximum effectiveness.

### 15a. Create HEARTBEAT.md

On the VPS, create the heartbeat checklist:

```bash
cat > ~/openclaw/workspace/HEARTBEAT.md <<'HEARTBEAT_EOF'
# Heartbeat Checklist

If nothing needs attention, reply HEARTBEAT_OK.

## Checks
1. Check all messaging platforms (Gmail, SMS, WhatsApp, Signal, GroupMe) for unread messages
2. If any messages require a response, summarize each and draft a reply
3. Use Claude Opus 4.6 with extended thinking (via OpenRouter) for all drafted replies
4. Append any updates to today's Notion daily brief — Texts and Emails sub-pages
5. If no updates, reply HEARTBEAT_OK
HEARTBEAT_EOF
```

### 15b. Phase 1 — Deterministic Pages (6:30 AM)

`notion_writer.py` creates the daily brief parent page and all deterministic sub-pages (Bible, weather, to-do, finance, birthdays) without using the LLM. It writes a state file at `/tmp/daily_brief_state.json` that Phase 2 reads.

```bash
# Phase 1: deterministic pages (~1-2 min, no LLM cost)
crontab -e
# Add this line:
30 6 * * * cd /home/openclaw/data/scripts && /home/openclaw/.local/bin/uv run python3 notion_writer.py >> /var/log/openclaw/phase1.log 2>&1
```

### 15c. Phase 2 — LLM Morning Sweep (6:40 AM)

The LLM reads the state file from Phase 1, then fills in the sub-pages that require intelligence: messages, drafted replies, financial editorial, and Chanry's message.

```bash
openclaw cron add \
  --name "morning-sweep" \
  --schedule "40 6 * * *" \
  --isolated \
  --prompt-file ~/openclaw/workspace/prompts/morning_sweep.md
```

Create the prompt file at `~/openclaw/workspace/prompts/morning_sweep.md`:

```markdown
ROLE:
You are a meticulous executive assistant and daily operations coordinator.
You have complete read access to all messaging platforms (Gmail, SMS,
WhatsApp, Signal, GroupMe) via built-in tools, and read-write access to
Notion and Todoist via MCP. You are trusted to aggregate sensitive
information and present it in a clear, actionable daily brief.

Today's deterministic sub-pages (Bible, weather, to-do, finance tables,
birthdays) have already been created by notion_writer.py. Your job is to
fill in the sub-pages that require intelligence: messages, replies,
financial editorial, and Chanry's message.

INSTRUCTIONS:
Process only the LLM-dependent portions of the daily brief. Use Claude
Sonnet 4.6 (via OpenRouter) for general summarization. Switch to Claude
Opus 4.6 with extended thinking (via OpenRouter) for drafting ALL replies
and Chanry's message. Use Google's Nano Banana (latest, via OpenRouter)
for image generation. All output goes to Notion under the parent page
created by Phase 1.

STEPS:

1. STATE FILE HANDOFF — Read /tmp/daily_brief_state.json.
   → If found: extract parent_page_id and sub_pages dict. Proceed to Step 2.
   → If missing: re-run `python3 /home/openclaw/data/scripts/notion_writer.py`.
     → If that succeeds: read the state file again, proceed to Step 2.
     → If that also fails: send a Telegram alert to the user:
       "⚠️ Morning brief Phase 1 failed: {error}. Creating partial brief."
       Create a NEW parent page in the Daily Briefs database, proceed to
       Step 2. The brief will be missing deterministic sub-pages.

2. CARRYOVER — Query yesterday's Notion daily brief page. In the 💬 Texts
   and 📧 Emails sub-pages, identify items that are still awaiting a
   response (not marked with strikethrough). For each carryover item:
   a. Check if the sender sent a NEW follow-up message since yesterday.
   b. If yes → flag as "needs fresh draft" (original context changed).
   c. If no → flag as "still pending" (carry forward the existing draft
      text verbatim — do NOT re-draft).

3. MESSAGES & EMAILS — Pull all messages and emails received since the
   last daily brief that the user has NOT replied to. Use time-based
   filtering, not "unread" status (user may have glanced at messages
   without replying). For each message: note sender, timestamp, platform,
   and content. Group by platform. Write a 1-2 sentence summary of each.

4. DRAFTED REPLIES — For every NEW message or email that requires a
   response, AND for carryover items flagged "needs fresh draft" in
   Step 2, switch to Opus 4.6 with extended thinking and draft a
   thoughtful, high-quality reply. Match the tone and style of the
   original conversation. Skip carryover items flagged "still pending" —
   their existing draft is already sufficient.

5. FINANCIAL EDITORIAL — Read the financial monitor output cached at
   /tmp/daily_brief_fm_output.json (written by Phase 1 alongside the state
   file — avoids re-running financial_monitor.py, which is expensive due to
   API calls to SnapTrade, FRED, and yfinance). Parse the JSON and write two
   sections, then APPEND them to the empty 📈 Stocks & Finances page
   (use sub_pages.finance page ID from the state file):

   **🔴 Action Items** (top of page):
   - List any HIGH or CRITICAL alerts with their recommended action text.
   - If no HIGH/CRITICAL alerts, write: "✅ All clear — no action needed."

   **🌍 Economy Snapshot** (below action items):
   - Unemployment rate, yield curve spread, CPI inflation %, Sahm rule.
   - BTC price and DXY index.
   - Add a 1-sentence editorial take (e.g., "Economy stable" or "Yield
     curve inverted — historically precedes recessions within 12 months").

   The page is empty at this point — Phase 1 created it but left it
   unpopulated. Step 9 will append the data tables below your editorial.

   If /tmp/daily_brief_fm_output.json is missing (Phase 1 finance step
   failed), run `python3 /home/openclaw/data/scripts/financial_monitor.py`
   as a fallback.

6. CHANRY'S MESSAGE — Switch to Opus 4.6 with extended thinking. Read the
   few-shot examples at /home/openclaw/data/morning_messages.txt. Using
   the established letter-themed style with specific adjectives and items,
   generate a new morning message. Then write three distinct, highly
   detailed image generation prompts that complement the message's theme.

7. IMAGE GENERATION — Pass the three prompts from Step 6 to Google's Nano
   Banana (latest model, via OpenRouter). Retrieve all three images.

8. NOTION DELIVERY — Under the parent page from Step 1, create these
   sub-pages (the deterministic sub-pages already exist):
   - 💬 Texts — overall summary at top, then individual summaries +
     drafted replies. Carryover items clearly marked as "⏳ CARRYOVER"
     with their existing or newly drafted reply.
   - 📧 Emails — same structure as Texts.
   - 💌 Chanry's Message — drafted message text + embed all 3 images.

9. FINANCE TABLES — Run:
     python3 /home/openclaw/data/scripts/notion_finance.py
   This appends the portfolio, account balances, and transaction tables
   BELOW the editorial content you added in Step 5. The data is read
   from /tmp/daily_brief_fm_output.json (cached by Phase 1). If this
   step fails, log the error and continue — the editorial is already
   delivered, and the user can view raw data in financial_monitor.py.

END GOAL:
A complete Notion daily brief delivered by 7:00 AM with all sub-pages
populated. Deterministic sub-pages (Bible, weather, to-do, finance tables,
birthdays) are filled by Phase 1. LLM sub-pages (texts, emails, Chanry's
message) are filled by Phase 2. Every message and email needing a reply
has a draft using Opus 4.6. The 📈 finance page has action items and
economy editorial at the top, with data tables appended below by
`notion_finance.py`. Chanry's message includes 3 generated images.

NARROWING:
- Do NOT send any replies automatically — only draft them for review,
  because the user needs to review and edit before sending.
- Do NOT re-draft carryover items that are "still pending" — the user
  chose not to send the previous draft; re-drafting wastes Opus tokens
  and may produce a worse reply without the original context.
- Do NOT use Sonnet for drafted replies — always use Opus 4.6 with
  extended thinking, because reply quality is the highest-value output.
- Do NOT create empty sub-pages — skip them and note on parent page
  instead (e.g., "💬 Texts — no new messages").
- Do NOT recreate sub-pages that Phase 1 already built (Bible, weather,
  to-do, birthdays) — if the state file exists, those pages are already
  populated. The 📈 finance page is created empty by Phase 1; write
  editorial to it in Step 5, then run `notion_finance.py` in Step 9.
- Do NOT append finance tables before writing editorial — Step 9 must
  run AFTER Step 5, or the tables will appear above the editorial.
- Do NOT include raw JSON in Notion — always format as human-readable
  text, tables, or callouts.
- Do NOT attempt to fix notion_writer.py if it fails — send a Telegram
  alert and proceed with the partial brief. Debugging scripts during the
  morning sweep risks delaying the entire brief past the 7:00 AM deadline.
- Avoid summarizing messages shorter than 2 sentences — include verbatim.
- Stay within the 7:00 AM deadline — if a non-critical step fails, skip
  it, note the failure on the parent page, and continue.
```

### 15d. Periodic Sweep Cron Job (Every 3 Hours)

```bash
openclaw cron add \
  --name "periodic-sweep" \
  --schedule "0 10,13,16,19,22 * * *" \
  --isolated \
  --prompt-file ~/openclaw/workspace/prompts/periodic_sweep.md
```

Create the prompt file at `~/openclaw/workspace/prompts/periodic_sweep.md`:

```markdown
ROLE:
You are a real-time communications assistant performing a periodic check-in. Your job
is to catch new messages and emails that arrived since the last sweep and append
updates to the existing daily brief.

INSTRUCTIONS:
Run a lighter version of the morning sweep. Focus only on new messages, emails, and
reply tracking. Use Sonnet 4.6 for summarization. Switch to Opus 4.6 with extended
thinking for all drafted replies. Append results to today's existing Notion sub-pages.

STEPS:

1. IDENTIFY TODAY'S BRIEF — Find today's parent page in the "Daily Briefs" Notion
   database.

2. NEW MESSAGES — Pull unread messages from all platforms (Gmail, SMS, WhatsApp,
   Signal, GroupMe) that arrived since the last sweep. Summarize each new message.

3. DRAFT REPLIES — For any new message or email requiring a response, switch to
   Opus 4.6 with extended thinking and draft a reply. Match conversation tone.

4. REPLY TRACKING — Check all messaging and email platforms for replies that were
   actually sent (via read access). For each sent reply:
   - Find the corresponding drafted reply in the Notion sub-page
   - Update it to show the actual reply that was sent
   - Mark the drafted reply with ~~strikethrough~~
   - Keep both versions for a complete record

5. APPEND TO NOTION — Add new message summaries and drafted replies to the bottom
   of the existing 💬 Texts and 📧 Emails sub-pages. Mark new entries with the
   current timestamp.

END GOAL:
Today's Notion daily brief is updated with all new messages, fresh drafted replies,
and reply tracking status. The Texts and Emails sub-pages show a complete, timestamped
record of the day's communications.

NARROWING:

- Do NOT recreate the parent page or other sub-pages — only append to Texts and Emails
- Do NOT re-summarize messages from previous sweeps
- Do NOT send any replies — only draft them
- Do NOT use Sonnet for drafted replies — always use Opus 4.6 with extended thinking
- Avoid duplicating messages already in the sub-page
- If no new messages exist, do not modify the Notion page at all
```

---

## Step 16 — End-to-End Verification

**Time:** ~1-2 hours

### 16a. Test Phase 1 (Deterministic Pages)

Run `notion_writer.py` manually and verify the output:

```bash
cd /home/openclaw/data/scripts && uv run python3 notion_writer.py
```

1. Verify the state file was created:
   ```bash
   cat /tmp/daily_brief_state.json
   ```
   - [ ] `parent_page_id` is a valid Notion page ID
   - [ ] `sub_pages.morning_bible` is not null
   - [ ] `sub_pages.evening_bible` is not null
   - [ ] `sub_pages.weather` is not null
   - [ ] `sub_pages.todoist` is not null
   - [ ] `sub_pages.finance` is not null (page exists but is **empty** — this is intentional)
   - [ ] `sub_pages.birthdays` is null (expected if no birthdays today) or a valid ID

2. Verify the FM cache was created:
   ```bash
   cat /tmp/daily_brief_fm_output.json | python3 -m json.tool | head -20
   ```
   - [ ] Contains `brokerage_data` and `bank_data` keys

3. Open Notion and verify:
   - [ ] Parent page exists with today's date as title
   - [ ] 📖 Morning Bible Reading has devotional text
   - [ ] 🌙 Evening Bible Reading has ESV text + 3 study note toggles
   - [ ] 🌤️ Weather has hourly + 10-day tables
   - [ ] ✅ To-Do List has Todoist tasks
   - [ ] 📈 Stocks & Finances page exists but is **empty** (no blocks yet)
   - [ ] 🎂 Birthdays skipped if no birthdays today

### 16b. Test Phase 2 (LLM Sweep)

Manually trigger the morning sweep via the OpenClaw CLI:

```bash
openclaw run --prompt-file ~/openclaw/workspace/prompts/morning_sweep.md
```

1. Verify LLM-created sub-pages:
   - [ ] 💬 Texts sub-page shows message summaries with drafted replies
   - [ ] 📧 Emails sub-page shows email summaries with drafted replies
   - [ ] 💌 Chanry's Message has a drafted message + 3 Nano Banana images
   - [ ] 📈 Stocks & Finances now has 🔴 Action Items + 🌍 Economy Snapshot editorial at the **top**, followed by portfolio, balances, and transaction tables **below**

2. Verify Phase 2 did NOT duplicate Phase 1 pages:
   - [ ] Only one 📖 Morning Bible Reading exists (not two)
   - [ ] Only one 🌤️ Weather exists (not two)

### 16c. Test Periodic Sweep

3. **Test reply tracking:** Send yourself a test message, let OpenClaw draft a reply, then manually send the reply. On the next periodic sweep, verify it's marked with ~~strikethrough~~
4. **Test carryover:** Leave a message unreplied overnight. Next morning, verify it appears as a carryover item marked "⏳ CARRYOVER"

### 16d. Test Failure Modes

5. **Phase 1 failure:** Temporarily break the `NOTION_TOKEN` → run `notion_writer.py` → verify it exits with an error. Then trigger Phase 2 → verify the LLM sends a Telegram alert and creates a partial brief.
6. **Financial monitor failure:** Temporarily break OFX config → run `notion_writer.py` → verify the finance sub-page is still created (empty) and the state file still has all other sub-pages.
7. **Weather script:** Run `weather_fetch.py` manually → verify JSON output includes today's hourly + 10-day forecast.

---

## Execution Order Summary

Follow the steps in order — Steps 1-4 are free local prep, Steps 5-16 require the VPS.

| Step | Description                      | Duration        | Dependencies             |
| ---- | -------------------------------- | --------------- | ------------------------ |
| 1    | Calibre pipeline (Mac)           | 2-3 hrs         | None                     |
| 2    | Contacts & Schedules             | 30 min          | None                     |
| 3    | Compile morning messages         | 1-2 hrs         | None                     |
| 4    | Notion/app setup                 | 15 min          | None                     |
| 5    | Hetzner account + server         | 15 min          | None                     |
| 6    | LUKS encryption                  | 30 min          | Step 5                   |
| 7    | WireGuard VPN                    | 20 min          | Steps 5-6                |
| 8    | Coolify                          | 10 min          | Steps 5-7                |
| 9    | Neon PostgreSQL                  | 10 min          | None (parallel with 5-8) |
| 10   | OpenClaw deployment              | 20 min          | Steps 8-9                |
| 11   | Messaging bridges                | 45 min          | Step 10                  |
| 12   | OFX Direct Connect banks         | 20 min          | Step 5                   |
| 13a-b| Financial monitor                | 30 min          | Steps 10, 12             |
| 13c  | Notion modules                   | 15 min          | Steps 4, 13a-b           |
| 14   | Weather script                   | 20 min          | Step 10                  |
| 15   | Cron jobs (Phase 1 + 2) + RISEN  | 30 min          | Steps 10-14              |
| 16   | E2E verification                 | 1-2 hrs         | All                      |
|      | **Total estimated time**         | **~9-13 hours** |                          |

