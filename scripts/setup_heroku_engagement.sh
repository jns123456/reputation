#!/usr/bin/env bash
# Configure Heroku engagement stack: VAPID (push), SITE_BASE_URL, optional Resend.
# Usage: ./scripts/setup_heroku_engagement.sh [app-name]
# Requires: heroku CLI, logged in, py-vapid in .venv

set -euo pipefail
APP="${1:-reputation-juan}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Generating VAPID keys (temporary files, not committed)..."
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
"$ROOT/.venv/bin/vapid" --gen --output-dir "$TMPDIR" 2>/dev/null || "$ROOT/.venv/bin/vapid" --gen
if [[ -f "$TMPDIR/private_key.pem" ]]; then
  PRIVATE_KEY="$(cat "$TMPDIR/private_key.pem")"
  PUBLIC_KEY="$("$ROOT/.venv/bin/vapid" --applicationServerKey --private-key "$TMPDIR/private_key.pem" | sed 's/^Application Server Key = //')"
elif [[ -f private_key.pem ]]; then
  PRIVATE_KEY="$(cat private_key.pem)"
  PUBLIC_KEY="$("$ROOT/.venv/bin/vapid" --applicationServerKey | sed 's/^Application Server Key = //')"
  rm -f private_key.pem public_key.pem
else
  echo "Failed to generate VAPID keys. Run: .venv/bin/pip install pywebpush && .venv/bin/vapid --gen"
  exit 1
fi

SITE_URL="${SITE_BASE_URL:-https://www.predictstamp.com}"

echo "==> Setting Heroku config on $APP..."
heroku config:set \
  SITE_BASE_URL="$SITE_URL" \
  ENGAGEMENT_EMAILS_ENABLED=True \
  VAPID_PUBLIC_KEY="$PUBLIC_KEY" \
  VAPID_PRIVATE_KEY="$PRIVATE_KEY" \
  VAPID_CLAIMS_EMAIL="mailto:admin@predictstamp.com" \
  DIGEST_SEND_HOUR_UTC=13 \
  STREAK_REMINDER_HOUR_UTC=22 \
  -a "$APP"

if [[ -n "${RESEND_API_KEY:-}" ]]; then
  echo "==> Setting RESEND_API_KEY..."
  heroku config:set \
    RESEND_API_KEY="$RESEND_API_KEY" \
    RESEND_FROM_EMAIL="${RESEND_FROM_EMAIL:-PredictStamp <onboarding@resend.dev>}" \
    -a "$APP"
else
  echo ""
  echo "Email: add RESEND_API_KEY (free at https://resend.com/api-keys) then re-run:"
  echo "  RESEND_API_KEY=re_xxx ./scripts/setup_heroku_engagement.sh $APP"
  echo "Or set SMTP vars: EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD"
fi

echo "==> Scaling worker dyno (Celery + Beat)..."
heroku ps:scale web=1 worker=1 -a "$APP"

echo ""
echo "Done. Push code if needed: git push heroku main"
echo "Verify: heroku config -a $APP | grep -E 'VAPID|SITE_BASE|RESEND'"
echo "Push test: open https://www.predictstamp.com/accounts/settings/alerts/ and enable push."
