# PredictStamp — Sentry autofix (100% Cursor)

Autonomous pipeline: Sentry issue → fix → test → commit → push → Heroku → verify → rollback or resolve.

## Activar en Cursor (pasos)

1. **Commit y push** este repo a `main` (los scripts deben estar en GitHub para el Cloud Agent).
2. Cursor → **Automations** → **New automation**.
3. Trigger: **Sentry** → *Issue created* + *Issue unresolved* → selecciona el proyecto PredictStamp.
4. Tools: habilita **MCP → sentry** (conectar OAuth si hace falta).
5. Repo: `jns123456/reputation`, branch `main`, **Cloud Agent** activado.
6. Copia el prompt de `automation/sentry-autofix.workflow.json` o referencia `automation/instructions.md`.
7. **Secrets** en Cloud Agent (Settings → Environment):

| Variable | Valor |
|----------|--------|
| `HEROKU_API_KEY` | API key de Heroku |
| `HEROKU_APP` | `reputation-juan` |
| `SITE_BASE_URL` | URL pública prod (ej. `https://predictstamp.app`) |
| `SENTRY_AUTH_TOKEN` | Token de integración interna Sentry |
| `SENTRY_ORG` | slug de la org en Sentry |

8. En Heroku: el remote `git` debe aceptar push (API key o deploy key). El script usa `git push heroku main`.
9. Guardar y activar la automation.

Opcional: en Sentry, conectar la integración **Cursor** para que los triggers lleguen en tiempo real.

## Triggers

- Sentry **issue created** (new errors)
- Sentry **issue unresolved** (regressions)

## Scripts (run by the agent)

| Script | Purpose |
|--------|---------|
| `preflight.py` | Denylist, diff size, secret scan |
| `deploy.py` | `git push origin main` + `git push heroku main` |
| `verify.py` | Poll `/health/` after deploy |
| `rollback.py` | Heroku rollback + git revert |
| `tag_issue.py` | Tag issue `autofix:deployed` / `autofix:skipped` |

## Safety

Denylist: `config/autofix_denylist.txt` — reputation scoring, migrations, secrets paths blocked.

## Manual test

```bash
export SITE_BASE_URL=https://predictstamp.app
python scripts/sentry_autofix/verify.py

git add -A && python scripts/sentry_autofix/preflight.py --staged
```
