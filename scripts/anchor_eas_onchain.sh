#!/usr/bin/env bash
# One-time: enable EAS on-chain anchoring on Heroku and anchor the genesis batch.
# Usage (run locally, never commit the key):
#   ./scripts/anchor_eas_onchain.sh 0xYOUR_PRIVATE_KEY
set -euo pipefail

APP="${HEROKU_APP:-reputation-juan}"
PRIVATE_KEY="${1:-}"

if [[ -z "$PRIVATE_KEY" ]]; then
  echo "Usage: $0 0xYOUR_PRIVATE_KEY" >&2
  exit 1
fi

if [[ "$PRIVATE_KEY" != 0x* ]]; then
  echo "Private key must start with 0x" >&2
  exit 1
fi

echo "Setting Heroku config (key is not printed)..."
heroku config:set \
  EAS_ANCHOR_PRIVATE_KEY="$PRIVATE_KEY" \
  EAS_ONCHAIN_ANCHOR_ENABLED=True \
  -a "$APP"

echo "Registering EAS schema on Base..."
heroku run "python manage.py register_eas_daily_schema" -a "$APP"

echo "Anchoring full-history batch..."
heroku run "python manage.py anchor_attestation_batch --historical" -a "$APP"

echo "Done. Check https://www.predictstamp.com/proof/ and Basescan for your relayer wallet."
