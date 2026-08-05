# Production-Ready Telegram Bot

A clean, modular, production-grade Telegram bot built with **aiogram 3.x**, async SQLAlchemy, and SQLite (PostgreSQL-ready).

Designed for real deployments: environment-based secrets, rate limiting, admin ACL, structured logging, and Docker support.

---

## Features

- Fully asynchronous (aiogram 3 + asyncio)
- Clean architecture (handlers → services → repositories → models)
- Automatic user registration and profile storage
- Admin-only commands with dual-check filter (env + database)
- Rate limiting (sliding window) to prevent abuse
- Auth middleware (auto-register, block enforcement)
- Logging middleware (console + file)
- Reply keyboard menu
- Environment-based configuration (no hardcoded secrets)
- SQLite by default, PostgreSQL-ready
- Docker & docker-compose ready (non-root container user)
- Exception handling and graceful failure paths

---

## Requirements

- Python **3.12+**
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- (Optional) Docker & Docker Compose for containerized runs

---

## Project Structure

```
production-telegram-bot/
├── main.py                 # Application entry point
├── config.py               # Settings (pydantic-settings)
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── LICENSE                 # MIT
├── README.md
├── ARCHITECTURE.md         # Detailed architecture notes
├── bot/
│   ├── handlers/           # Command & message handlers
│   ├── keyboards/          # Reply keyboards
│   ├── middlewares/        # Rate limit, logging, auth
│   ├── filters/            # IsAdmin filter
│   ├── services/           # Business logic
│   ├── repositories/       # Data access
│   ├── database/           # Models + engine
│   ├── localization/       # Message templates
│   ├── utils/              # Logger helpers
│   └── states/             # FSM package (ready for extension)
├── logs/                   # Runtime logs (created automatically)
└── data/                   # SQLite database (created automatically)
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/atemmokhtar2-blip/production-telegram-bot.git
cd production-telegram-bot

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` with your values:

```env
BOT_TOKEN=123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
LOG_LEVEL=INFO
```

| Variable       | Required | Description |
|----------------|----------|-------------|
| `BOT_TOKEN`    | Yes      | Token from @BotFather |
| `ADMIN_IDS`    | No       | Comma-separated Telegram user IDs with admin rights |
| `DATABASE_URL` | No       | Default: local SQLite. For PostgreSQL use `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `LOG_LEVEL`    | No       | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`) |

> Never commit the real `.env` file. It is ignored by git.

For PostgreSQL, also install the driver:

```bash
pip install asyncpg
```

---

## Running

### Local (polling)

```bash
python main.py
```

The bot will:

1. Validate `BOT_TOKEN`
2. Create `data/` and the SQLite database (if needed)
3. Create tables automatically
4. Start long-polling

### Docker

```bash
cp .env.example .env
# Edit .env with your real BOT_TOKEN and ADMIN_IDS

docker compose up -d --build

# Follow logs
docker compose logs -f bot

# Stop
docker compose down
```

---

## Available Commands

| Command    | Description                      | Access   |
|------------|----------------------------------|----------|
| `/start`   | Start the bot and register       | Everyone |
| `/help`    | Show help message                | Everyone |
| `/profile` | Show your profile                | Everyone |
| `/stats`   | Total registered users           | Admin    |
| `/users`   | List recent users (up to 20)     | Admin    |

Reply keyboard buttons mirror the same actions.

---

## Libraries

| Package              | Version   | Purpose                          |
|----------------------|-----------|----------------------------------|
| aiogram              | 3.13.1    | Telegram Bot API framework       |
| SQLAlchemy           | 2.0.35    | Async ORM                        |
| aiosqlite            | 0.20.0    | Async SQLite driver              |
| pydantic             | 2.9.2     | Data validation                  |
| pydantic-settings    | 2.5.2     | Environment configuration        |
| python-dotenv        | 1.0.1     | `.env` file loading              |

Optional for PostgreSQL: `asyncpg`

---

## Logs

- Console: INFO and above (configurable via `LOG_LEVEL`)
- File: `logs/bot.log`

Sensitive data (tokens, full message bodies) is not written to logs.

---

## Updating the Project

```bash
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
# Restart the process or: docker compose up -d --build
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `BOT_TOKEN is not set or is still the example value` | Copy `.env.example` → `.env` and set a real token from @BotFather |
| `BOT_TOKEN appears malformed` | Token must look like `digits:alphanumeric` (length ≥ 30) |
| Database / permission errors under Docker | Ensure `data/` and `logs/` are writable; compose mounts them as volumes |
| Admin commands ignored | Add your Telegram numeric user ID to `ADMIN_IDS` in `.env`, then restart |
| Rate limit messages | Default: 20 messages / 60 seconds per user; temporary block after excess |
| ModuleNotFoundError | Activate the virtualenv and run `pip install -r requirements.txt` |

---

## Stopping

- Local: `Ctrl+C`
- Docker: `docker compose down`

---

## License

MIT License — see [LICENSE](LICENSE).


---

## Deploy on Railway

1. Push this repo to GitHub (already done if using the project remote).
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Select this repository.
4. Add variables in Railway **Variables**:

| Variable | Value |
|----------|--------|
| `BOT_TOKEN` | Your token from @BotFather |
| `ADMIN_IDS` | Your Telegram user id (optional) |
| `LOG_LEVEL` | `INFO` |
| `AI_MODEL` | `gpt-4o-mini` (optional) |

5. (Optional) Add a **PostgreSQL** plugin. Railway will inject `DATABASE_URL` — the bot auto-converts it to `postgresql+asyncpg://`.
6. Deploy. The start command is `python main.py` (polling worker).

### Local check before deploy

```bash
cp .env.example .env
# edit BOT_TOKEN
pip install -r requirements.txt
python main.py
```

### Create a bot from a description

In Telegram:

1. `/create` or button **🤖 إنشاء بوت**
2. Send a detailed Arabic/English description
3. The **11-agent pipeline** designs the bot (Master → Architect → Backend → Review → Security → QA → Debug → Perf → Docs → Release → Orchestrator)
