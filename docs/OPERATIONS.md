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
- Pulse images on object storage: enable bucket versioning if takedown/audit matters.

## Forum media (Cloudflare R2)

Forum posts can include images (`pulse.Post.image`). Local dev writes to `media/`; **Heroku requires S3-compatible storage** — deploy checks fail if `USE_S3_MEDIA` is unset on a dyno.

### All-in-one CLI (recommended)

Requires **curl**, **python3**, and `CLOUDFLARE_API_TOKEN` (no Node/wrangler needed).

```bash
export CLOUDFLARE_API_TOKEN=<token with R2 Edit + Account API Tokens Edit>

./scripts/provision_r2_media.sh --heroku-app reputation-juan
```

| Step | Tool |
|------|------|
| Account ID | Cloudflare API `GET /accounts` |
| Create bucket | Cloudflare API `POST /accounts/{id}/r2/buckets` |
| Public URL (beta) | Cloudflare API `PUT .../domains/managed` |
| Public URL (prod) | Cloudflare API `POST .../domains/custom` |
| S3 credentials | Cloudflare API `POST /accounts/{id}/tokens` |
| Heroku config | `scripts/setup_heroku_r2_media.sh` |

`r2.dev` URLs are rate-limited — use a custom domain for heavy production traffic.

### Manual / dashboard alternative

1. **R2** → **Create bucket** → e.g. `predictstamp-media`.
2. **Manage R2 API tokens** → **Object Read & Write** on that bucket.
3. Bucket **Settings** → **Public access** → copy `*.r2.dev` or attach a custom domain.

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_STORAGE_BUCKET_NAME=predictstamp-media
export AWS_S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
export AWS_S3_CUSTOM_DOMAIN=pub-xxxxxxxx.r2.dev
./scripts/setup_heroku_r2_media.sh reputation-juan
```

### Verify

```bash
heroku run python manage.py check_media_storage -a reputation-juan
```

Uploads a tiny PNG, prints the public URL, and deletes the test object.

### Notes

| Topic | Detail |
|-------|--------|
| **ACL** | R2 ignores S3 object ACLs — public read is configured at bucket/domain level. |
| **CSP** | `img-src` already allows `https:`; custom media domains need no CSP change. |
| **Limits** | Default max upload 5 MB (`PULSE_MAX_IMAGE_BYTES`); JPEG/PNG/WebP/GIF only. |
| **AWS S3** | Omit `AWS_S3_ENDPOINT_URL`; set `AWS_S3_REGION_NAME` and optional `AWS_S3_CUSTOM_DOMAIN`. |

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
| **Pulse media** | Forum images are world-readable via the R2 public hostname or custom domain. R2 does not use S3 object ACLs. |
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
