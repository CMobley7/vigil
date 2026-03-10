# Vision: The Autonomous Daily Operations Center

To build a fully autonomous, cloud-hosted digital chief of staff that securely aggregates daily intelligence (financial, schedule-based, and spiritual) and proactively drafts communication. It leverages a strictly sandboxed LLM (via OpenClaw) to manage task prioritization, monitor specific investment portfolios, and nurture personal relationships while ensuring you remain in complete control of the final output via a secure, single-pane-of-glass Notion dashboard.

---

### Phase 1: Secure Infrastructure & Database (The Sandbox)

- **The Server:** Hetzner Cloud **CX23** — 2 vCPU, 4 GB RAM, 40 GB NVMe SSD, 20 TB traffic. ~€3.49/mo (~$42/yr). With PostgreSQL offloaded to Neon, the remaining RAM budget is: Coolify (~512 MB) + OpenClaw (~256 MB) + Actual Budget (~256 MB) ≈ 1 GB used, leaving ~3 GB headroom.
- **Database (Neon — Free Tier):** Use **Neon** serverless PostgreSQL instead of self-hosted. Free tier provides 0.5 GB storage, 100 compute-hours/month, `pgvector` support, and automatic scale-to-zero when idle. This offloads the heaviest RAM consumer from the VPS, enables automatic backups, and eliminates database maintenance. Enable `pgcrypto` for column-level encryption of sensitive data (e.g., raw Signal message history). _(Neon chosen over Supabase because Supabase pauses free-tier projects after 1 week of inactivity; Neon only scales to zero on idle connections and wakes instantly on query.)_
- **Extreme Security & Encryption:** Implement LUKS (Linux Unified Key Setup) for Full Disk Encryption on the VPS. Configure a "kill switch" script (`cryptsetup erase <device>`) that can instantly wipe the LUKS header, cryptographically shredding the drive in the event of a compromise.
- **Networking:** Connect the VPS to the existing UniFi Dream Router Wireguard VPN. Configure the firewall to aggressively block all inbound traffic except through the established Wireguard tunnel.
- **Container Management:** Install Coolify on the VPS (handles Docker, reverse proxy, and SSL automatically).
- **Orchestration (OpenClaw):** Deploy the OpenClaw container via Coolify, connecting it to the Neon PostgreSQL database via connection string. Route all LLM and image generation calls through **OpenRouter** (via API key) to enable seamless model swapping. Set **Claude Sonnet 4.6** as the default model for general reasoning and task execution.
- **Security Constraints:** Grant OpenClaw `read` access for local files and messaging APIs, unrestricted `web_fetch` for external REST APIs and general web research, and strictly deny all arbitrary `exec` commands.

### Phase 2: Data Ingestion (The Inputs)

#### One-Time Setup

- **Books, Devotionals & Reading Plans (The Calibre Pipeline):** 1. Install Kindle for Mac (v1.31 or v1.39) and immediately disable auto-updates. 2. Download **Good Morning Mercies** (morning devotional), the **ESV Bible**, and three study Bibles: the **Reformation Study Bible (ESV)**, the **John MacArthur Study Bible (ESV)**, and the **ESV Study Bible**. 3. Import the files into Calibre using the DeDRM plugin (v10.0.9) to strip the DRM protection. 4. Export the books to EPUB, then process the files through **Docling** (using MarkItDown as a lightweight fallback) to convert them into clean Markdown. 5. Prompt an LLM to convert the daily scripture reading plan text into a structured JSON file. Store all files locally on the VPS.
- **Contacts:** Export birthdays from contacts as `.ics` and convert to a structured JSON file via an LLM. Store locally on the VPS. _(Medication schedules and trash/recycling reminders are managed in Todoist.)_
- **Messaging Platform Authentication:** Authenticate OpenClaw's native bridged skills for Gmail, SMS (Android), WhatsApp, GroupMe, and Signal in read-only mode.

#### Recurring (Automated)

- **Messaging & Email Sweep:** Pull unread messages and emails across all authenticated platforms on each sweep cycle.
- **Financials (Actual Budget + SimpleFIN):** Deploy Actual Budget via Coolify, accessible over VPN at port 5006 for personal budgeting. Connect it to the **Fidelity HSA** and **Schwab PRSA** accounts using **SimpleFIN** ($15/yr) to automate daily syncing of balances and portfolio holdings. OpenClaw will query Actual Budget's local API. _(Additional accounts can be added later as needed.)_
- **Financial Health Monitor:** A Python script (`financial_monitor.py`) reads the local Markdown checklist of financial red-flag conditions (e.g., unusual charges, missed payments, low balances, dividend changes, allocation drift) and the synced Actual Budget data, then produces a structured summary the LLM can evaluate. On each morning sweep, the LLM reviews this summary against the checklist. If any condition is triggered, it surfaces a prioritized alert with a recommended action in the daily brief. _(Note: The Markdown checklist is kept as-is — no JSON conversion needed. The Python script handles the data formatting; the LLM handles the judgment.)_
- **Task Management (Todoist):** Connect OpenClaw to the Todoist REST API to pull the top prioritized tasks for the current day (includes medication schedules and trash/recycling reminders).
- **Weather:** Connect OpenClaw to **Open-Meteo** for the daily forecast. _(Open-Meteo is free with no API key required. Apple WeatherKit was considered but requires an Apple Developer Program membership at $99/yr.)_

### Phase 3: The Brain & Generation

- **Resilience & Fallbacks:** All API calls use **tenacity** for retry logic with exponential backoff. Fallback chain:
  - **LLM calls:** OpenRouter (primary) → direct Anthropic API (fallback) if OpenRouter is unreachable.
  - **Financial data:** SimpleFIN via Actual Budget (primary) → **yfinance** Python fallback script that pulls current prices from Yahoo Finance and generates the financial summary based on yesterday's report if SimpleFIN sync fails.
- **The Morning Sweep (6:30 AM → ready by 7:00 AM):** OpenClaw's internal cron (`HEARTBEAT.md`) triggers at 6:30 AM. Using **Sonnet 4.6** (via OpenRouter), it first runs carryover processing (pulling unreplied items from yesterday — see Phase 4), then aggregates unread messages/emails, today's passage from Good Morning Mercies, today's Bible reading with cross-referenced study notes from all three study Bibles, the JSON reading plan, the weather forecast, Todoist priorities (including medication and household reminders), the financial health monitor results, and the synced financial balances. The completed daily brief is delivered to Notion by 7:00 AM.
- **Chanry's Message & Image Prompts:** OpenClaw switches to **Claude Opus 4.6 with extended thinking** (via OpenRouter) for this task. Using a local text file containing hundreds of previous morning messages as a few-shot training prompt, the model generates a new letter-themed morning message utilizing specific adjectives and items. Based on this drafted message, it explicitly writes three distinct, highly detailed image generation prompts.
- **Image Generation:** OpenClaw passes those three prompts to Google's **Nano Banana** (latest model) via **OpenRouter** and retrieves the generated images.
- **Birthday Outreach:** Using Sonnet 4.6, the system cross-references the current date with the JSON contacts database to draft suggested birthday messages.
- **Drafted Replies:** For all messages and emails requiring a response, OpenClaw drafts replies using **Claude Opus 4.6 with extended thinking** (via OpenRouter) to ensure thoughtful, high-quality responses.
- **Periodic Sweeps (every 3 hours, 10:00 AM → 10:00 PM):** Throughout the day, OpenClaw runs a lighter sweep every three hours using **Sonnet 4.6** to summarize new incoming emails and draft suggested replies to new text messages based on the prior conversation context. Results are appended to the corresponding sub-pages in the daily brief. _(Sweep interval and end time are configurable.)_

### Phase 4: Output & The Daily Brief (Notion)

- **The Dashboard:** Set up a dedicated "Daily Briefs" database in Notion and generate an internal integration token. Each day's entry is a **parent page** created automatically by the Notion API.
- **Sub-Page Architecture:** Under each daily parent page, OpenClaw creates dedicated sub-pages for modular, at-a-glance navigation:
  - 📖 **Morning Bible Reading** — today's passage from Good Morning Mercies
  - 🌙 **Evening Bible Reading** — today's Bible reading passage with cross-referenced study notes from the Reformation Study Bible, MacArthur Study Bible, and ESV Study Bible
  - 💬 **Texts** — overall summary of all messages at the top, followed by individual message summaries with drafted replies
  - 📧 **Emails** — overall summary of all emails at the top, followed by individual email summaries with drafted replies or full email content
  - 🎂 **Birthdays** — today's birthdays with drafted outreach messages
  - 📈 **Stocks & Finances** — portfolio balances, allocation status, and financial health alerts
  - ✅ **To-Do List** — today's Todoist priorities and any carryover items
  - 💌 **Chanry's Message** — drafted morning message with three Nano Banana images for review and selection
  - 🌤️ **Weather & Reminders** — forecast and Todoist-managed reminders (medication, trash/recycling, etc.)
- **The Delivery:** Processing begins at 6:30 AM; the parent page and all sub-pages are populated and ready by 7:00 AM. Sub-pages with no content for the day (e.g., no birthdays) are **skipped** but noted on the parent page (e.g., "🎂 Birthdays — none today"). Periodic sweeps throughout the day append updates to the **Texts** and **Emails** sub-pages.
- **Reply Tracking & Carryover:** On each sweep, OpenClaw checks messaging and email platforms for sent replies (via read access). If a reply was sent, the corresponding drafted reply in the sub-page is updated to show the actual reply and marked with ~~strikethrough~~ (keeping a full record). Items the LLM determines do not require a response are summarized but not flagged for carryover. During the next morning's 6:30 AM processing, any messages or emails still awaiting a response are carried forward into the new day's **Texts** and **Emails** sub-pages, clearly marked as carryover items.
