# PredictStamp — Production operations

## Health and readiness

- **Liveness:** `GET /health/` returns `200` when PostgreSQL responds.
- **Cache:** When `USE_REDIS_CACHE=True`, the health check also pings Redis.
- Load balancers should use `/health/` and pass `X-Request-ID` (optional) for log correlation.

## Error monitoring

1. Create a Sentry project and copy the DSN.
2. Set `SENTRY_DSN` in Heroku/config.
3. Optional: `SENTRY_ENVIRONMENT=production`, `SENTRY_TRACES_SAMPLE_RATE=0.1`.

## Deploy (Heroku)

| Phase | Command |
|-------|---------|
| **Release** | `python manage.py migrate --noinput` only |
| **Web** | Gunicorn via `Procfile` |
| **Worker** | Celery worker |
| **Beat** | Celery beat (market sync, agent trust, optional emails) |

Market import runs on **Celery Beat**, not on release — deploys no longer depend on Polymarket uptime.

Manual catch-up after deploy:

```bash
heroku run python manage.py sync_markets --categories --limit 48
```

## Rollback

1. Roll back the Heroku release (previous slug).
2. If a migration was applied, plan a reverse migration or forward-fix — never delete reputation events or resolved predictions.
3. Verify `/health/` and Sentry error rate.

## Backups

- Use managed PostgreSQL automated backups (Heroku Postgres, RDS, etc.).
- Test restore on a staging app at least quarterly.
- Pulse images on S3: enable bucket versioning if takedown/audit matters.

## Staging

Maintain a staging app with:

- Separate `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`
- `DEBUG=False`, `SENTRY_ENVIRONMENT=staging`
- Same `Procfile` process types as production
- Promote to production only after CI green + smoke test on staging

## Security notes

| Topic | Guidance |
|-------|----------|
| **Redis TLS** | Heroku `rediss://` may use `ssl_cert_reqs=CERT_NONE` — acceptable inside provider network; avoid public Redis endpoints. |
| **Pulse media** | `AWS_DEFAULT_ACL=public-read` — URLs are world-readable by design for social posts. |
| **CSP** | Enable `CSP_ENABLED=True` with `CSP_REPORT_ONLY=True` first; fix violations, then enforce. |
| **API raw payloads** | `?include_raw=1` on `/api/markets/{slug}/` requires a **staff** user. |

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs tests against PostgreSQL and `pip-audit` on every push/PR.

Local reproducible install:

```bash
pip install -r requirements.lock
```

## Logs

- `LOG_LEVEL=INFO` in production.
- Each response includes `X-Request-ID`; `django.request` logs include `request_id=…` when the filter is active.
