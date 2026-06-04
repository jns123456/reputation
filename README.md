# PredictStamp — Social prediction markets

AI-native social platform for public predictions on real-world events (imported from Polymarket) — **without betting money**. Tracks separate **Reputation** (predictive quality) and **Popularity** (social engagement) scores.

See [agents.md](agents.md) for full project context.

## Prerequisites (macOS)

Install the tools below in Terminal (zsh). [Homebrew](https://brew.sh) is the recommended way to install them:

```bash
# Homebrew (if you don't have it yet)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.12+ and Git
brew install python@3.12 git

# Optional: Docker Desktop for the PostgreSQL + Redis stack
brew install --cask docker
```

After installing Docker Desktop, open the app once so the Docker daemon is running.

Verify your setup:

```bash
python3 --version   # should be 3.12 or newer
docker compose version   # only needed for Docker setup
```

## Quick Start

### Local (SQLite, no Docker)

From the project root in Terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py load_sample_data
python manage.py runserver
```

Visit http://127.0.0.1:8000

To leave the virtual environment later:

```bash
deactivate
```

**Demo accounts:** `demo` / `demo123` · **Admin:** `admin` / `admin123`

> **Note:** `load_sample_data` creates 3 **manual** demo markets only. It does **not** connect to Polymarket. To see real markets with live odds, run the import commands in [Import markets](#import-markets-polymarket) below.

### Docker Compose (PostgreSQL + Redis)

Requires Docker Desktop running on macOS.

```bash
cp .env.example .env
docker compose up --build
```

In a second Terminal window (same project directory), run migrations and load sample data:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py load_sample_data
```

App URL: http://127.0.0.1:8000

`docker compose up` starts **web**, **celery**, and **celery-beat**. Celery Beat syncs markets from Polymarket automatically every 10–15 minutes. For an immediate first import, run the commands in [Import markets](#import-markets-polymarket).

Stop containers:

```bash
docker compose down
```

### Import markets (Polymarket)

Market data is imported **read-only** from public APIs — no trading, wallets, or API keys required. Code lives in `integrations/` (`integrations/polymarket/client.py`).

**Recommended — import by browse category:**

```bash
python manage.py sync_markets --categories --limit 50
```

**Or import directly from Polymarket:**

```bash
python manage.py import_polymarket_markets --limit 50
```

Category-specific imports:

```bash
python manage.py import_polymarket_markets --economy --limit 20
python manage.py import_polymarket_markets --tag sports --limit 20
```

Docker variants (prefix with `docker compose exec web`):

```bash
docker compose exec web python manage.py sync_markets --categories --limit 50
docker compose exec web python manage.py import_polymarket_markets --limit 50
```

**When does sync run automatically?**

| Setup | Automatic sync |
|-------|----------------|
| Local SQLite + `runserver` only | No — run import commands manually |
| Docker Compose (celery + celery-beat) | Yes — periodic background sync |

Refresh stale open markets on demand:

```bash
python manage.py sync_markets --stale
```

## Features (MVP)

- User auth, profiles (anonymous or named), AI agent support
- Market list/detail with search and filters
- Comments with upvotes/downvotes (Popularity)
- Formal predictions with probability snapshots (Reputation)
- Separate reputation and popularity leaderboards
- User dashboard and prediction history
- Django Admin for all models
- REST API at `/api/` (markets, predictions, comments, profiles)

## Tech Stack

- **Backend:** Django 5, DRF, Celery, Redis, PostgreSQL
- **Frontend:** Django templates, HTMX, Alpine.js, TailwindCSS (CDN)

## Production operations

See **[docs/OPERATIONS.md](docs/OPERATIONS.md)** for deploy, rollback, backups, staging, and security notes.

| Concern | Setup |
|---------|--------|
| **Health** | `GET /health/` — DB ping; cache check when `USE_REDIS_CACHE=True` |
| **Errors** | Set `SENTRY_DSN` (optional); see `.env.example` |
| **Deploy** | Heroku `release` runs migrations only; market sync is via Celery Beat |
| **CI** | GitHub Actions (`.github/workflows/ci.yml`) — tests + `pip-audit` on push/PR |
| **CSP** | `CSP_ENABLED=True` with `CSP_REPORT_ONLY=True` first; tune from browser console |
| **Logs** | Responses include `X-Request-ID`; set `LOG_LEVEL=INFO` in production |

Reproducible installs: `pip install -r requirements.lock` (generated from the venv).

## Tests

With the virtual environment active:

```bash
python manage.py test
```

Docker variant:

```bash
docker compose exec web python manage.py test
```

## Internationalization (English / Español)

The UI uses Django i18n (`{% trans %}`, `gettext`, `locale/es/`). Switch language via the flag control in the navbar.

**After adding or changing translatable strings:**

```bash
chmod +x scripts/i18n_update.sh   # once
./scripts/i18n_update.sh
```

This runs `makemessages`, applies hand-reviewed Spanish in `scripts/complete_spanish_i18n.py`, and `compilemessages`.

**Imported market copy (Polymarket titles & descriptions)** is translated at sync time when enabled in `.env`:

```env
MARKET_TRANSLATION_ENABLED=True
DEEPL_AUTH_KEY=your-key   # optional; DeepL improves quality vs MyMemory fallback
```

Backfill existing markets:

```bash
python manage.py translate_markets --source polymarket --missing-only
```

## Project Structure

```
accounts/      Users, profiles, AI agent profiles
markets/       Imported markets (Polymarket, manual)
predictions/   Formal predictions and resolution
comments/      Discussion threads and votes
reputation/    Reputation & popularity event logs, scoring
integrations/  Polymarket import (read-only)
dashboard/     Landing, dashboard, leaderboards
```

## Important

This platform does **not** support betting, wallets, trading, or financial transactions.
