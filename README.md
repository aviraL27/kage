# Kage (影) — Personal Command Center Agent

A self-hosted, lightweight personal command center Telegram bot powered by an LLM with tool calling, persistent memory, and scheduled jobs.

> **Budget**: ₹0 (100% free-tier & open-source components).

---

## Features

- **Morning Briefing**: Sends a daily digest at 7:30 AM IST covering today's calendar events, pending tasks, unread emails, and GitHub notifications.
- **Natural Language Assistant**: Understands commands like *"remind me to review PRs tomorrow 6pm"* and *"what's due this week?"*.
- **Persistent Reminders & Tasks**: Backed by SQLite and APScheduler with an SQLite job store that survives bot restarts.
- **Persistent Memory**: Retains user preferences and facts across sessions.
- **MCP Extensibility**: Tools exposed as Model Context Protocol (FastMCP) servers.
- **Strict Security**:
  - Hard Telegram user ID allowlist (drops unauthorized messages).
  - Read-only external integrations (Google Calendar, Gmail, GitHub).
  - Explicit inline confirmation buttons for state-modifying actions.
  - Prompt injection protection against untrusted email/web content.

---

## Architecture Overview

```
                        +----------------------------+
                        |     Telegram User          |
                        +--------------+-------------+
                                       |
                                       v
                        +----------------------------+
                        |  Telegram Bot (Allowlist)  |
                        +--------------+-------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
    +-------------------------------+       +-------------------------------+
    |       LLM Adapter Layer       |       |     APScheduler Service       |
    |  (Gemini / Groq / Ollama)     |       |   (SQLite JobStore, IST tz)   |
    +--------------+----------------+       +---------------+---------------+
                   |                                        |
                   v                                        v
    +-------------------------------+       +-------------------------------+
    |         Tool Registry         |       |      Daily Morning Brief      |
    |    (Strict Pydantic Schema)   |       |      & Scheduled Reminders    |
    +--------------+----------------+       +-------------------------------+
                   |
     +-------------+-------------+-------------+
     |             |             |             |
     v             v             v             v
  [Tasks &     [Memory &     [Google API    [GitHub API]
  Reminders]    Preferences]  (Calendar/Gmail
                               Read-Only)]
```

---

## Roadmap & Implementation Phases

- [ ] **Phase 0**: Environment inspection, project structure, virtualenv, base repo setup.
- [ ] **Phase 1**: Telegram bot skeleton with allowlist & LLM adapter (Gemini free tier).
- [ ] **Phase 2**: SQLite task tracking & APScheduler persistent reminders with unit tests.
- [ ] **Phase 3**: Google Calendar & Gmail OAuth (read-only) + GitHub notifications.
- [ ] **Phase 4**: Morning brief scheduled at 7:30 AM IST + on-demand `/brief`.
- [ ] **Phase 5**: Persistent memory (user facts and preferences stored in SQLite).
- [ ] **Phase 6**: FastMCP server conversion & MCP client integration.
- [ ] **Phase 7**: Evaluation test suite (20+ test scenarios), accuracy reporting, final documentation.

---

## Getting Started

### Prerequisites
- Python 3.11+
- Git

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/aviraL27/kage.git
   cd kage
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Telegram bot token, allowed user ID, and API keys
   ```

5. Run the bot:
   ```bash
   python -m kage.bot.main
   ```
