# Implementation Plan — The Autonomous Daily Operations Center

Derived from [Plan.md](file:///home/cmobley/Documents/Projects/Reports/openclaw/Plan.md). Every step has been verified via internet research.

> [!CAUTION]
> **$0/yr data import strategy:** This plan uses **SnapTrade** (free tier, 5 connections) for brokerage data and **OFX Direct Connect** (free, built into most banks) for bank transactions. No Plaid, no SimpleFIN. See Step 9 and Step 13.

---

## Step 1 — Hetzner Account + CX23 Server

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

## Step 2 — LUKS Full Disk Encryption

**Time:** ~30 min

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

---

## Step 3 — WireGuard VPN (Connect VPS to Home Network)

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

## Step 4 — Install Coolify

**Time:** ~10 min

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

## Step 5 — Neon PostgreSQL Database

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

## Step 6 — Deploy OpenClaw via Coolify

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

## Step 7 — Messaging Bridges (All Greenfield)

**Time:** ~45 min total

### 7a. Gmail

1. Create a **dedicated Gmail account** for OpenClaw (e.g., `openclaw.bot@gmail.com`)
2. Enable **2-Step Verification** on the account
3. Go to Google Account → **Security** → **App Passwords** → generate one for "Mail"
4. In OpenClaw, configure IMAP/SMTP polling with the app password:
   - IMAP: `imap.gmail.com`, port 993, SSL
   - SMTP: `smtp.gmail.com`, port 587, TLS
   - Poll interval: 5 minutes

### 7b. WhatsApp

1. In OpenClaw dashboard → **Pairing** section
2. A QR code will appear
3. On your phone → WhatsApp → **Settings** → **Linked Devices** → **Link a Device** → scan the QR code
4. OpenClaw is now linked as a WhatsApp Web client

### 7c. Signal (Linked Device — No Second Number Needed)

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

### 7d. GroupMe

1. Install the community plugin: `openclaw channels add groupme`
2. Follow the interactive setup — it will guide you through:
   - Creating a GroupMe bot via [dev.groupme.com](https://dev.groupme.com)
   - Selecting the group
   - Configuring the webhook URL
3. Note: GroupMe Bot API does **not** support DMs, only group chats

### 7e. SMS (Android)

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

---

## Step 8 — Notion Account + Integration

**Time:** ~15 min

1. Go to [notion.so](https://www.notion.so) → Sign up (free plan is sufficient)
2. Create a workspace
3. Create a top-level page called **"Daily Briefs"**
4. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New Integration**
   - Name: `OpenClaw Daily Brief`
   - Associated workspace: your workspace
   - Capabilities: **Read, Update, Insert content**
5. Copy the **Internal Integration Token** (starts with `ntn_`)
6. Go back to your "Daily Briefs" page → click `...` → **Connections** → **Add Connection** → select your integration
7. Store the integration token — OpenClaw will use it to create pages via the Notion API

---

## Step 9 — Actual Budget + SimpleFIN

**Time:** ~30 min

### Deploy Actual Budget:

1. In Coolify dashboard → **New Project** → **New Service**
2. Search for **Actual Budget** in the service list (it's a listed Coolify service)
3. Deploy — Coolify will pull the `actualbudget/actual-server` Docker image
4. **Expose the dashboard on your VPN only:** In Coolify's service settings, set the port mapping to bind to the WireGuard interface IP:
   ```
   <wireguard-ip>:5006:5006
   ```
   For example, if your VPS's WireGuard IP is `10.0.0.2`:
   ```
   10.0.0.2:5006:5006
   ```
   This means Actual Budget is accessible at `http://10.0.0.2:5006` — but **only** when you're connected to your WireGuard VPN. It's invisible from the public internet.
5. Also allow port 5006 through UFW for VPN traffic only:
   ```bash
   sudo ufw allow from <wireguard-subnet>/24 to any port 5006
   ```
6. Access Actual Budget at `http://<wireguard-ip>:5006` from your phone/laptop while on VPN
7. Create your budget and set a password

### Connect Bank Accounts via SimpleFIN ($15/yr):

1. Go to [simplefin.org](https://simplefin.org) → **Sign Up** → pay $15/yr (or $1.50/mo)
2. After signup, click **Create a SimpleFIN Token**
3. **Add your banks:** Click **Add Connection** → search for **Fidelity** → log in with your Fidelity credentials → authorize. Repeat for **Schwab**.
4. Copy your **SimpleFIN Access URL** (a long URL that looks like `https://beta-bridge.simplefin.org/simplefin/...`)
5. In Actual Budget → **Settings** → **Linked Accounts** → **Link with SimpleFIN**
6. Paste your SimpleFIN Access URL
7. Actual Budget will discover your Fidelity HSA and Schwab PRSA accounts → map them to your budget accounts
8. Click **Sync** → verify transactions appear
9. SimpleFIN syncs once daily automatically. You can manually sync anytime from Actual Budget.

> [!NOTE]
> You can now use Actual Budget for personal budgeting anytime from your phone/laptop over VPN at `http://<wireguard-ip>:5006`.

---

## Step 10 — Calibre Pipeline (Run on Mac)

**Time:** ~2-3 hours (one-time)

### 10a. Install Tools

1. Download **Kindle for Mac v1.39** from [archive.org](https://archive.org/details/kindle-for-mac) or a known mirror → install → **immediately disable auto-updates** (Kindle → Preferences → uncheck auto-update)
2. Download [Calibre](https://calibre-ebook.com/download_osx) → install
3. Download [DeDRM_tools_10.0.9.zip](https://github.com/noDRM/DeDRM_tools/releases/tag/v10.0.9) → unzip the outer zip (keep `DeDRM_plugin.zip` intact)
4. In Calibre → **Preferences** → **Plugins** → **Load plugin from file** → select `DeDRM_plugin.zip`
5. Also install **KFX Input** plugin: Preferences → Plugins → **Get plugins to enhance Calibre** → search for "KFX Input" → install

### 10b. Download and Process Books

1. Open Kindle for Mac → download all 5 books:
   - Good Morning Mercies
   - ESV Bible
   - Reformation Study Bible (ESV)
   - John MacArthur Study Bible (ESV)
   - ESV Study Bible
2. In Calibre → **Add books** → navigate to Kindle content folder (`~/Library/Application Support/Kindle/My Kindle Content/`) → import all 5
3. DeDRM automatically strips DRM during import — verify no errors in the import log
4. Select all 5 books → **Convert books** → Output format: **EPUB** → OK

### 10c. Convert to Markdown

1. Install Docling: `pip install docling`
2. Convert each EPUB to Markdown:
   ```bash
   docling convert good_morning_mercies.epub --to md --output ./markdown/
   docling convert esv_bible.epub --to md --output ./markdown/
   # repeat for all 5 books
   ```
3. If Docling struggles with any file, fallback to MarkItDown: `pip install markitdown`

### 10d. Generate Reading Plan JSON

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

### 10e. Transfer to VPS

1. SCP the files to the VPS:
   ```bash
   scp -i ~/.ssh/hetzner_openclaw -r ./markdown/ root@<vps-wireguard-ip>:/home/openclaw/data/books/
   scp -i ~/.ssh/hetzner_openclaw reading_plan.json root@<vps-wireguard-ip>:/home/openclaw/data/
   ```

---

## Step 11 — Contacts & Schedules

**Time:** ~30 min

### 11a. Birthday Contacts

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

### 11b. Todoist Setup

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

## Step 12 — Compile Morning Messages

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

### 13b. Deploy `financial_monitor.py`

The script is **pre-built** at [financial_monitor.py](file:///home/cmobley/Documents/Projects/Reports/openclaw/financial_monitor.py). It integrates the **Chairman's Final Portfolio Allocation** (all 7 tickers, 4 accounts) with Actual Budget bank data, FRED recession indicators, and hyperscaler capex tracking.

1. Install dependencies on the VPS:

   ```bash
   uv sync  # deps defined in pyproject.toml
   ```

2. Transfer the script + portfolio doc to the VPS:

   ```bash
   scp -i ~/.ssh/hetzner_openclaw financial_monitor.py root@<vps-wireguard-ip>:/home/openclaw/data/scripts/
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

- **Bank accounts** (via Actual Budget/actualpy): Low balances, large unknown transactions, failed payments
- **Portfolio drift** (via yfinance): Flags when any ticker moves >20% in 3 months, suggesting weight drift
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

---

## Step 14 — Weather Script (`weather_fetch.py`)

**Time:** ~20 min

1. Dependencies are included in `pyproject.toml` — no separate install needed (`uv sync` covers it).

2. The `weather_fetch.py` script is a standalone file at `/home/openclaw/data/scripts/weather_fetch.py`. It uses `requests` directly (no numpy/pandas dependency) with a 10-second timeout.

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

### 15b. Morning Sweep Cron Job (6:30 AM)

```bash
openclaw cron add \
  --name "morning-sweep" \
  --schedule "30 6 * * *" \
  --isolated \
  --prompt-file ~/openclaw/workspace/prompts/morning_sweep.md
```

Create the prompt file at `~/openclaw/workspace/prompts/morning_sweep.md`:

```markdown
ROLE:
You are a meticulous executive assistant and daily operations coordinator. You have
complete read access to all messaging platforms, financial data, calendar data, and
local files. You are trusted to aggregate sensitive information and present it in a
clear, actionable daily brief.

INSTRUCTIONS:
Execute the full morning sweep to produce the daily brief. Process data sources in
the order specified below. Use Claude Sonnet 4.6 (via OpenRouter) for all general
aggregation and summarization. Switch to Claude Opus 4.6 with extended thinking
(via OpenRouter) for drafting ALL replies and for Chanry's message. Use Google's
Nano Banana (latest, via OpenRouter) for image generation. All output goes to Notion.

STEPS:

1. CARRYOVER — Query yesterday's Notion daily brief. Identify any messages or emails
   in the Texts and Emails sub-pages that are still awaiting a response (not marked
   with strikethrough). Collect these as carryover items.

2. MESSAGES & EMAILS — Pull all unread messages from Gmail, SMS, WhatsApp, Signal,
   and GroupMe. For each message: note the sender, timestamp, platform, and content.
   Group by platform. Write a 1-2 sentence summary of each message.

3. DRAFTED REPLIES — For every message or email that requires a response (including
   carryover items), switch to Opus 4.6 with extended thinking and draft a thoughtful,
   high-quality reply. Match the tone and style of the original conversation.

4. MORNING DEVOTIONAL — Read today's entry from Good Morning Mercies using the JSON
   reading plan at /home/openclaw/data/reading_plan.json. Look up the corresponding
   passage in /home/openclaw/data/books/good_morning_mercies.md.

5. EVENING BIBLE READING — From the JSON reading plan, identify today's Bible reading.
   Look up the passage in /home/openclaw/data/books/esv_bible.md. Then cross-reference
   study notes for the same passage from all three study Bibles:
   - /home/openclaw/data/books/reformation_study_bible.md
   - /home/openclaw/data/books/macarthur_study_bible.md
   - /home/openclaw/data/books/esv_study_bible.md

6. WEATHER — Run `python3 /home/openclaw/data/scripts/weather_fetch.py`. Parse the
   JSON output. Summarize: today's conditions (high/low, precipitation chance, wind),
   hourly breakdown of notable changes, and the 10-day outlook highlighting any days
   that need planning (rain, extreme temps, etc.).

7. TODOIST — Query the Todoist REST API for today's tasks, sorted by priority.
   Include medication reminders and trash/recycling tasks.

8. FINANCIAL HEALTH — Run `python3 /home/openclaw/data/scripts/financial_monitor.py`.
   Parse the JSON output. If any red-flag conditions are triggered, surface them as
   prioritized alerts with recommended actions. If no flags, note "All clear."

9. BIRTHDAYS — Read /home/openclaw/data/contacts.json. Check if any contacts have a
   birthday matching today's date. If yes, draft a personalized birthday message
   using Sonnet 4.6.

10. CHANRY'S MESSAGE — Switch to Opus 4.6 with extended thinking. Read the few-shot
    examples at /home/openclaw/data/morning_messages.txt. Using the established
    letter-themed style with specific adjectives and items, generate a new morning
    message. Then write three distinct, highly detailed image generation prompts
    that complement the message's theme and imagery.

11. IMAGE GENERATION — Pass the three prompts from Step 10 to Google's Nano Banana
    (latest model, via OpenRouter). Retrieve all three generated images.

12. NOTION DELIVERY — Create today's parent page in the "Daily Briefs" database
    using the Notion API. Then create these sub-pages under it:
    - 📖 Morning Bible Reading — content from Step 4
    - 🌙 Evening Bible Reading — content from Step 5
    - 💬 Texts — overall summary at top, then individual summaries + drafted replies;
      carryover items clearly marked as "⏳ CARRYOVER"
    - 📧 Emails — overall summary at top, then individual summaries + drafted replies;
      carryover items clearly marked as "⏳ CARRYOVER"
    - 🎂 Birthdays — drafted messages from Step 9 (if none: skip sub-page, note
      "🎂 Birthdays — none today" on parent page)
    - 📈 Stocks & Finances — balances + any alerts from Step 8
    - ✅ To-Do List — Todoist priorities from Step 7
    - 💌 Chanry's Message — drafted message + embed all 3 images
    - 🌤️ Weather & Reminders — forecast summary from Step 6 + Todoist reminders

END GOAL:
A complete, populated Notion daily brief with all sub-pages filled, delivered by
7:00 AM. Every message and email that needs a reply has a drafted reply using
Opus 4.6. Chanry's message has 3 generated images ready for review. The parent
page clearly shows which sub-pages have content and which were skipped.

NARROWING:

- Do NOT send any replies automatically — only draft them for review
- Do NOT skip any data source — if a source fails, note the failure in the sub-page
- Do NOT use Sonnet for drafted replies — always use Opus 4.6 with extended thinking
- Do NOT create empty sub-pages — skip them and note on parent page instead
- Avoid summarizing messages that are already short (< 2 sentences) — include verbatim
- Do NOT include raw JSON in Notion — always format data as human-readable text
- Stay within the 7:00 AM deadline — if a non-critical step fails, skip it and note
```

### 15c. Periodic Sweep Cron Job (Every 3 Hours)

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

1. **Manually trigger the morning sweep** via the OpenClaw CLI or dashboard
2. Verify each component produces output:
   - [ ] Notion parent page created with correct date
   - [ ] Morning Bible Reading sub-page populated from Good Morning Mercies
   - [ ] Evening Bible Reading sub-page populated with study notes
   - [ ] Texts sub-page shows message summaries with drafted replies
   - [ ] Emails sub-page shows email summaries with drafted replies
   - [ ] Birthdays sub-page shows today's birthdays (or "none today" on parent)
   - [ ] Stocks & Finances sub-page shows balances and financial health alerts
   - [ ] To-Do List sub-page shows Todoist priorities
   - [ ] Chanry's Message sub-page has a drafted message + 3 Nano Banana images
   - [ ] Weather & Reminders sub-page has hourly + 10-day forecast + Todoist reminders
3. **Test reply tracking:** Send yourself a test message, let OpenClaw draft a reply, then manually send the reply. On the next periodic sweep, verify it's marked with ~~strikethrough~~
4. **Test carryover:** Leave a message unreplied overnight. Next morning, verify it appears as a carryover item marked "⏳ CARRYOVER"
5. **Test fallbacks:**
   - Temporarily invalidate the OpenRouter API key → verify it falls back to direct Anthropic
   - Disconnect SimpleFIN → verify yfinance fallback generates a report
6. **Test financial monitor:** Add a test transaction that triggers a red-flag condition → verify an alert appears
7. **Test weather script:** Run `weather_fetch.py` manually → verify JSON output includes today's hourly + 10-day forecast

---

## Execution Order Summary

| Order | Step                       | Duration        | Dependencies             |
| ----- | -------------------------- | --------------- | ------------------------ |
| 1     | Hetzner account + server   | 15 min          | None                     |
| 2     | LUKS encryption            | 30 min          | Step 1                   |
| 3     | WireGuard VPN              | 20 min          | Steps 1-2                |
| 4     | Coolify                    | 10 min          | Steps 1-3                |
| 5     | Neon PostgreSQL            | 10 min          | None (parallel with 1-4) |
| 6     | OpenClaw deployment        | 20 min          | Steps 4-5                |
| 7     | Messaging bridges          | 45 min          | Step 6                   |
| 8     | Notion setup               | 15 min          | None (parallel)          |
| 9     | Actual Budget + SimpleFIN  | 30 min          | Step 4                   |
| 10    | Calibre pipeline (Mac)     | 2-3 hrs         | None (parallel)          |
| 11    | Contacts & Todoist         | 30 min          | Step 6                   |
| 12    | Morning messages           | 1-2 hrs         | None (parallel)          |
| 13    | Financial monitor (collab) | 1 hr            | Steps 6, 9               |
| 14    | Weather script             | 20 min          | Step 6                   |
| 15    | Cron jobs + RISEN prompts  | 30 min          | Steps 6-14               |
| 16    | E2E verification           | 1-2 hrs         | All                      |
|       | **Total estimated time**   | **~9-13 hours** |                          |
