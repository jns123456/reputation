# PredictStamp — Sentry autofix (100% Cursor)

Autonomous pipeline: Sentry poll → fix → test → commit → push → Heroku → verify → rollback or resolve.

## Por qué no usar trigger Sentry (naranja)

- Producción envía errores a **Sentry US cloud** (`ingest.us.sentry.io`), org **`fsc-ti`**, proyecto **`predictstamp`**.
- El trigger nativo de Cursor a veces queda en *Requires connection* aunque Integrations muestre Sentry conectado.
- **Solución:** trigger **cron cada 15 min** + `scripts/sentry_autofix/poll.py` (no requiere Connect en triggers).

## Activar en Cursor (3 minutos)

1. **Automations → New** (o edita la existente).
2. **Quita** triggers Sentry si siguen en naranja.
3. **+ Add Trigger → On a schedule → cada 15 minutos** (o importa `sentry-autofix.workflow.json`).
4. Repo: `jns123456/reputation`, branch `main`, Cloud Agent ON.
5. Tools: **+ Add Tool or MCP → sentry**.
6. Agent Instructions: copia el bloque `prompts` de `sentry-autofix.workflow.json`.
7. Cloud Agent env vars: copia `cloud-agent.env.example` y rellena tokens.
8. Save + Active.

Opcional: pedir a Cursor Agent **“open automation from sentry-autofix.workflow.json”** en Agents Window.

## Variables de entorno (Cloud Agent)

| Variable | Valor |
|----------|--------|
| `HEROKU_API_KEY` | Heroku API key |
| `HEROKU_APP` | `reputation-juan` |
| `SITE_BASE_URL` | URL prod |
| `SENTRY_AUTH_TOKEN` | Token con `event:read`, `project:read`, `org:read` |
| `SENTRY_ORG` | `fsc-ti` |
| `SENTRY_PROJECT` | `predictstamp` |
| `SENTRY_REGION_URL` | `https://us.sentry.io` |

## Scripts

| Script | Purpose |
|--------|---------|
| `poll.py` | Siguiente issue a arreglar (cron entrypoint) |
| `preflight.py` | Denylist + diff limits |
| `deploy.py` | push origin + heroku |
| `verify.py` | `/health/` |
| `rollback.py` | Heroku rollback + git revert |
| `tag_issue.py` | Nota + resolve en Sentry |

## Probar poll local

```bash
export SENTRY_AUTH_TOKEN=...
export SENTRY_ORG=fsc-ti
export SENTRY_REGION_URL=https://us.sentry.io
python scripts/sentry_autofix/poll.py
```
