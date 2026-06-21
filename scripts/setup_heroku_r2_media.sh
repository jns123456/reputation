#!/usr/bin/env bash
# Configure Heroku forum image storage on Cloudflare R2.
#
# Prerequisites (Cloudflare dashboard):
#   1. R2 bucket (e.g. predictstamp-media)
#   2. API token with Object Read & Write on that bucket
#   3. Public access enabled — copy the *.r2.dev hostname (or custom domain)
#
# Usage:
#   export AWS_ACCESS_KEY_ID=...
#   export AWS_SECRET_ACCESS_KEY=...
#   export AWS_STORAGE_BUCKET_NAME=predictstamp-media
#   export AWS_S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
#   export AWS_S3_CUSTOM_DOMAIN=pub-xxxxxxxx.r2.dev
#   ./scripts/setup_heroku_r2_media.sh [app-name]
#
# Optional: AWS_S3_REGION_NAME=auto (default)

set -euo pipefail
APP="${1:-reputation-juan}"

required=(
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_STORAGE_BUCKET_NAME
  AWS_S3_ENDPOINT_URL
  AWS_S3_CUSTOM_DOMAIN
)

missing=()
for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("$var")
  fi
done

if ((${#missing[@]} > 0)); then
  echo "Missing required environment variables:"
  printf '  - %s\n' "${missing[@]}"
  echo
  echo "See docs/OPERATIONS.md → Forum media (Cloudflare R2)."
  exit 1
fi

if [[ "${AWS_S3_CUSTOM_DOMAIN}" == http* ]]; then
  echo "AWS_S3_CUSTOM_DOMAIN must not include https:// — use pub-xxxxxxxx.r2.dev"
  exit 1
fi

REGION="${AWS_S3_REGION_NAME:-auto}"

echo "==> Setting R2 media config on $APP..."
heroku config:set \
  USE_S3_MEDIA=True \
  AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  AWS_STORAGE_BUCKET_NAME="$AWS_STORAGE_BUCKET_NAME" \
  AWS_S3_ENDPOINT_URL="$AWS_S3_ENDPOINT_URL" \
  AWS_S3_REGION_NAME="$REGION" \
  AWS_S3_CUSTOM_DOMAIN="$AWS_S3_CUSTOM_DOMAIN" \
  -a "$APP"

echo "==> Verifying storage (upload + delete test object)..."
heroku run python manage.py check_media_storage -a "$APP"

echo "Done. Forum image uploads now persist on R2."
