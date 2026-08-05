# Production-Ready Telegram Bot

A clean, modular, production-grade Telegram bot built with **aiogram 3.x**, async SQLAlchemy, and SQLite (PostgreSQL-ready).

## Features

- Fully asynchronous (aiogram 3 + asyncio)
- Clean architecture (handlers / services / repositories / models)
- User registration & profile storage
- Admin-only commands with filter
- Logging middleware + structured file/console logs
- Auth middleware (auto-register users, block support)
- Reply keyboard menu
- Environment-based configuration
- SQLite by default, easy switch to PostgreSQL
- Proper exception handling everywhere
- Type hints and modern Python 3.12+ style

## Project Structure

```
telegram_bot/
├── main.py                 # Entry point
├── config.py               # Settings (pydantic-settings)
├── .env.example
├── requirements.txt
├── bot/
│   ├── handlers/           # Message & command handlers
│   ├── keyboards/          # Reply & inline keyboards
│   ├── middlewares/        # Logging, Auth
│   ├── filters/            # Custom filters (IsAdmin)
│   ├── services/           # Business logic
│   ├── repositories/       # Data access layer
│   ├── database/           # Models + engine
│   ├── localization/       # Message texts
│   ├── utils/              # Logger helpers
│   └── states/             # FSM states (ready for extension)
└── logs/
```

## Installation

```bash
# Clone or extract the project
cd telegram_bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env`:

```env
BOT_TOKEN=your_real_bot_token_from_BotFather
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
LOG_LEVEL=INFO
```

- `BOT_TOKEN` — required (get it from @BotFather)
- `ADMIN_IDS` — comma-separated Telegram user IDs that have admin rights
- `DATABASE_URL` — leave as-is for SQLite, or use  
  `postgresql+asyncpg://user:pass@host:5432/dbname` for PostgreSQL  
  (you will also need `asyncpg` in requirements)

## Running

```bash
python main.py
```

The bot will:

1. Create the `data/` directory and SQLite database
2. Create tables automatically
3. Start long-polling

## Available Commands

| Command     | Description                          | Access   |
|-------------|--------------------------------------|----------|
| `/start`    | Start bot & register user            | Everyone |
| `/help`     | Show help message                    | Everyone |
| `/profile`  | Show your profile                    | Everyone |
| `/stats`    | Total registered users               | Admin    |
| `/users`    | List recent users                    | Admin    |

Reply keyboard buttons work the same way.

## Logs

- Console output (INFO+)
- File: `logs/bot.log`

## Extending

- Add new handlers under `bot/handlers/` and include them in `bot/handlers/__init__.py`
- Add FSM states in `bot/states/`
- Switch to PostgreSQL by changing `DATABASE_URL` and installing `asyncpg`
- Add more middlewares or filters as needed

## License

MIT
```

## Docker

```bash
# Copy environment file and edit it
cp .env.example .env
# Edit .env with your real BOT_TOKEN and ADMIN_IDS

# Build and run
docker compose up -d --build

# View logs
docker compose logs -f bot

# Stop
docker compose down
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full software architecture document.
