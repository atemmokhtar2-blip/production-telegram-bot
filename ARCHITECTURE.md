PROJECT OVERVIEW

A production-ready Telegram bot built with aiogram 3.x. The system provides user onboarding, profile management, basic interaction (echo), administrative statistics, and user listing. It uses clean architecture layers (handlers → services → repositories → database), asynchronous processing throughout, SQLite as the default persistence layer (PostgreSQL-ready), structured logging, middleware-based authentication and request logging, and role-based access control. The design prioritizes maintainability, security, and the ability to scale features without rewriting core modules.

---

FEATURES

- Automatic user registration on first interaction
- User profile storage and display
- Start command with welcome message and main reply keyboard
- Help command and keyboard button
- Profile command and keyboard button
- Free-text echo responses
- Admin-only statistics (total registered users)
- Admin-only recent users listing
- Role detection (admin via environment configuration + database flag)
- Automatic profile update when username or full name changes
- User blocking capability (middleware enforcement)
- Structured request logging (update ID + user ID)
- Exception logging with full stack traces
- Environment-based configuration (no hardcoded secrets)
- Database schema auto-creation on startup
- Reply keyboard navigation
- Graceful handling of missing or invalid tokens
- Support for future FSM-based multi-step flows
- Extensible middleware chain
- Extensible filter system for permissions

Hidden / derived features:
- Idempotent user creation (get-or-create pattern)
- Session isolation per request via async session factory
- Non-blocking I/O for all database and Telegram API calls
- Clean separation allowing independent testing of each layer
- Ready path for rate limiting and spam protection middleware
- Ready path for localization expansion beyond English
- Ready path for PostgreSQL without code changes in business logic

---

USER FLOW

Start:
1. User sends /start or presses Start in Telegram.
2. Auth middleware intercepts, performs get-or-create on the user.
3. If user is blocked → reply with block message and stop.
4. Handler sends personalized welcome text + main reply keyboard.
5. Logging middleware records the update.

Help:
1. User sends /help or presses “ℹ️ Help”.
2. Handler returns the static help text listing all commands.
3. No database write occurs.

Profile:
1. User sends /profile or presses “👤 Profile”.
2. Handler reads the already-injected db_user object.
3. Formats and returns ID, username, full name, admin status, registration timestamp.

Echo:
1. User sends any plain text that does not start with “/”.
2. Handler echoes the text back with a prefix.
3. No database interaction.

Stats (Admin only):
1. User sends /stats or presses “📊 Stats”.
2. IsAdminFilter evaluates environment admin IDs and database is_admin flag.
3. If not admin → filter rejects (message ignored by admin router).
4. If admin → service counts users and returns formatted statistics.

Users list (Admin only):
1. User sends /users.
2. Same admin filter as above.
3. Service retrieves up to 20 most recent users.
4. Handler formats a list of telegram_id + username + full_name.

Error paths:
- Missing or example BOT_TOKEN → process exits with clear log message.
- Database connection failure → exception logged, request fails gracefully.
- Blocked user → polite block message, no further processing.
- Unexpected exception in any handler → generic user-facing error + full exception logged.

Success paths:
- Every successful handler ends with a single Telegram reply.
- User record is always up-to-date after AuthMiddleware.

Admin actions:
- View global user count.
- View recent user list.
- (Architecture ready for future block/unblock commands.)

---

SYSTEM FLOW

1. main.py loads configuration, initializes logging, creates database tables, constructs Bot + Dispatcher.
2. LoggingMiddleware is registered on the update level; AuthMiddleware is registered on the message level.
3. Incoming Update → LoggingMiddleware logs metadata → passes to next middleware.
4. AuthMiddleware:
   - Opens async session.
   - Calls UserService.get_or_create.
   - UserService → UserRepository → SQLAlchemy query / insert.
   - Injects db_user into handler data.
   - Checks is_blocked; aborts if true.
5. Dispatcher routes the update to the appropriate Router (start / help / admin / echo).
6. Admin router is pre-filtered by IsAdminFilter (environment + database check).
7. Handler executes, may call services for additional data, then answers the user.
8. Any exception bubbles to LoggingMiddleware which records the full traceback.
9. Session is closed by the context manager after the request.

Module communication:
- Handlers depend only on services and injected data.
- Services depend only on repositories.
- Repositories depend only on SQLAlchemy session and models.
- No circular imports; configuration is injected via settings singleton.
- Middlewares and filters are pure and side-effect limited to logging / auth.

---

FOLDER STRUCTURE

```
telegram_bot/
├── main.py
├── config.py
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
├── bot/
│   ├── __init__.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── help.py
│   │   ├── echo.py
│   │   └── admin.py
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── reply.py
│   ├── middlewares/
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   └── auth.py
│   ├── filters/
│   │   ├── __init__.py
│   │   └── admin.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── user_service.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── user_repository.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── models.py
│   ├── states/
│   │   └── __init__.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── logger.py
│   └── localization/
│       ├── __init__.py
│       └── en.py
├── logs/
│   └── .gitkeep
└── data/                  # created at runtime for SQLite
```

---

DATABASE DESIGN

Single table for the current scope (extensible later).

Table: users
- id                  INTEGER PRIMARY KEY AUTOINCREMENT
- telegram_id         BIGINT UNIQUE NOT NULL INDEXED
- username            VARCHAR(255) NULL
- full_name           VARCHAR(255) NULL
- is_admin            BOOLEAN NOT NULL DEFAULT FALSE
- is_blocked          BOOLEAN NOT NULL DEFAULT FALSE
- created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
- updated_at          TIMESTAMPTZ NOT NULL DEFAULT now() ON UPDATE now()

Indexes:
- UNIQUE INDEX on telegram_id (primary lookup key)
- Implicit primary key index on id

Relationships:
- None required for current features. Future tables (e.g. messages, settings) will reference users.telegram_id or users.id.

---

BOT COMMANDS

/start  
/help  
/profile  
/stats          (admin only)  
/users          (admin only)

---

CALLBACKS

None in the current scope.  
Architecture reserves callback_data namespace for future inline keyboards (e.g. admin:block:{id}, admin:unblock:{id}, settings:lang:en).

---

FSM STATES

No active FSM states in the current scope.  
Architecture provides an empty states package ready for future multi-step flows (e.g. admin broadcast, user settings wizard).

---

PERMISSIONS

- Guest / Unregistered: treated as first-time user; automatically promoted to User on /start.
- User: can use /start, /help, /profile, free-text echo. Cannot access admin commands.
- Admin: all User permissions + /stats + /users. Identified by presence in ADMIN_IDS environment variable or is_admin=true in database.
- Blocked: any role can be blocked; AuthMiddleware short-circuits the request.

Future roles (Moderator, Owner, Developer) can be added by extending the is_admin flag into a role enum without breaking existing code.

---

SECURITY

- BOT_TOKEN never hardcoded; loaded exclusively from environment.
- ADMIN_IDS loaded from environment; never exposed to clients.
- All user input treated as untrusted (text is echoed only after basic presence check).
- No eval/exec or dynamic code execution.
- SQL injection prevented by SQLAlchemy parameterized queries.
- Session objects are request-scoped and closed automatically.
- Blocked users are rejected before any business logic runs.
- Admin checks performed in both filter and service layers (defense in depth).
- Logging never writes tokens or full message content of sensitive nature.
- .env is git-ignored; only .env.example is committed.
- Rate limiting and spam protection are architecturally reserved for a future middleware.

---

ERROR HANDLING

- Missing / placeholder BOT_TOKEN → process exits with ERROR log before polling starts.
- Database connectivity or schema errors → exception logged; startup fails fast.
- User not found during update → repository returns None; service creates new record.
- Concurrent registration race → unique constraint on telegram_id; retry logic can be added later.
- Telegram API errors (network, flood) → aiogram raises; LoggingMiddleware captures full traceback.
- Handler-level exceptions → caught locally, user receives generic “unexpected error” message, full exception logged.
- Blocked user → explicit message, no further processing, no exception raised.
- Invalid callback or unknown command → falls through to echo or is ignored by router filters.
- Recovery strategy: fail-fast on startup configuration errors; degrade gracefully on per-request errors.

---

LOGGING

- Startup: configuration load, database initialization success/failure.
- Every incoming update: update_id + user_id (INFO).
- User creation / profile update (INFO).
- Admin actions (INFO).
- Blocked user attempts (WARNING).
- All unhandled exceptions with full stack trace (ERROR / EXCEPTION).
- aiogram and SQLAlchemy engine loggers suppressed to WARNING to reduce noise.
- Dual output: console + rotating file under logs/bot.log.

---

CONFIGURATION

Required / supported environment variables:

- BOT_TOKEN                 (required)
- ADMIN_IDS                 (comma-separated integers, optional)
- DATABASE_URL              (default: sqlite+aiosqlite:///./data/bot.db)
- LOG_LEVEL                 (default: INFO)

Future candidates (not yet used): REDIS_URL, RATE_LIMIT_PER_MINUTE, WEBHOOK_HOST, WEBHOOK_PATH, SENTRY_DSN.

---

DEPENDENCIES

- aiogram==3.13.1
- aiosqlite==0.20.0
- SQLAlchemy==2.0.35
- python-dotenv==1.0.1
- pydantic==2.9.2
- pydantic-settings==2.5.2

Optional for PostgreSQL: asyncpg

---

DEVELOPMENT PLAN

Phase 1 – Foundation  
- Project skeleton, configuration, logging, database models and session factory.

Phase 2 – Core user path  
- Auth middleware, UserRepository, UserService, /start, /help, /profile, echo, reply keyboard.

Phase 3 – Admin layer  
- IsAdminFilter, admin router, /stats, /users.

Phase 4 – Hardening  
- Full exception handling, structured logging, .gitignore, README, LICENSE, environment validation.

Phase 5 – Production readiness  
- Dockerfile / docker-compose (optional), health-check endpoint readiness, metrics hooks, rate-limit middleware placeholder.

Phase 6 – Extensibility  
- FSM package activation, localization expansion, additional admin commands (block/unblock), callback system.

---

FILE RESPONSIBILITIES

main.py  
Purpose: Application entry point.  
Inputs: Environment variables.  
Outputs: Running long-polling process.  
Dependencies: config, bot.database, bot.handlers, bot.middlewares, bot.utils.

config.py  
Purpose: Typed settings loaded from environment.  
Inputs: .env / OS environment.  
Outputs: Settings singleton.  
Dependencies: pydantic-settings.

bot/utils/logger.py  
Purpose: Logging configuration and factory.  
Inputs: LOG_LEVEL.  
Outputs: Configured root logger + named loggers.  
Dependencies: config.

bot/database/base.py  
Purpose: Engine, session factory, Base declarative class, init_db.  
Inputs: DATABASE_URL.  
Outputs: Async engine and session maker.  
Dependencies: config, SQLAlchemy.

bot/database/models.py  
Purpose: ORM entity definitions.  
Inputs: None.  
Outputs: User model.  
Dependencies: bot.database.base.

bot/repositories/user_repository.py  
Purpose: Pure data-access methods for User.  
Inputs: AsyncSession, telegram_id, optional fields.  
Outputs: User instances or counts.  
Dependencies: models, logger.

bot/services/user_service.py  
Purpose: Business logic for user lifecycle.  
Inputs: AsyncSession, Telegram User object.  
Outputs: User domain objects, stats dict.  
Dependencies: repository, config, logger.

bot/middlewares/logging.py  
Purpose: Log every update and capture exceptions.  
Inputs: Update, handler.  
Outputs: Pass-through + log records.  
Dependencies: logger.

bot/middlewares/auth.py  
Purpose: Register/update user, inject db_user, enforce block list.  
Inputs: Message, handler.  
Outputs: db_user in data or early abort.  
Dependencies: service, logger.

bot/filters/admin.py  
Purpose: Boolean decision whether the actor is an administrator.  
Inputs: Message or CallbackQuery.  
Outputs: True / False.  
Dependencies: service, config.

bot/handlers/start.py  
Purpose: Handle /start.  
Inputs: Message, db_user.  
Outputs: Welcome message + keyboard.  
Dependencies: localization, keyboards, logger.

bot/handlers/help.py  
Purpose: Handle /help and Help button.  
Inputs: Message.  
Outputs: Help text.  
Dependencies: localization, logger.

bot/handlers/echo.py  
Purpose: Handle /profile and free-text messages.  
Inputs: Message, db_user.  
Outputs: Profile card or echoed text.  
Dependencies: localization, logger.

bot/handlers/admin.py  
Purpose: Handle /stats and /users.  
Inputs: Message.  
Outputs: Statistics or user list.  
Dependencies: service, localization, logger, IsAdminFilter.

bot/handlers/__init__.py  
Purpose: Aggregate all routers.  
Inputs: None.  
Outputs: Root handlers Router.  
Dependencies: individual handler routers.

bot/keyboards/reply.py  
Purpose: Construct reply keyboards.  
Inputs: None.  
Outputs: ReplyKeyboardMarkup / ReplyKeyboardRemove.  
Dependencies: aiogram types.

bot/localization/en.py  
Purpose: Static message templates.  
Inputs: Format kwargs.  
Outputs: Formatted strings.  
Dependencies: None.

All __init__.py files  
Purpose: Public API exports and package markers.  
Inputs / Outputs: Re-exports of primary symbols.

---

QUALITY RULES

Architecture adheres to:
- Clean Architecture (handlers → services → repositories → infrastructure)
- SOLID (single responsibility per module, open for extension via new handlers/filters)
- DRY (shared localization, shared service methods)
- KISS (minimal moving parts for the current feature set)
- Full async/await path from Telegram update to database
- Dependency injection via constructor (services/repositories) and aiogram data injection (db_user)
- Production concerns: logging, configuration isolation, graceful error surfaces, schema migration readiness
- Testability: each layer can be unit-tested in isolation with mocked sessions or services
- Scalability path: replace MemoryStorage with Redis, add connection pooling, introduce rate-limit middleware, switch to webhook mode without touching business logic
