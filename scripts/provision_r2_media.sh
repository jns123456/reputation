#!/usr/bin/env bash
# Provision Cloudflare R2 for forum images (Cloudflare REST API + Heroku).
#
# Requires: curl, python3, CLOUDFLARE_API_TOKEN
# Optional: heroku CLI when --heroku-app is set
#
# Token permissions (https://dash.cloudflare.com/profile/api-tokens → Create Token):
#   - Account → Workers R2 Storage → Edit
#   - Account → Account API Tokens → Edit
#
# Usage:
#   export CLOUDFLARE_API_TOKEN=...
#   ./scripts/provision_r2_media.sh --heroku-app reputation-juan
#
# Production custom domain (predictstamp.com zone on Cloudflare):
#   ./scripts/provision_r2_media.sh --public-access domain \
#     --domain media.predictstamp.com --zone-id <zone_id> --heroku-app reputation-juan

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUCKET="predictstamp-media"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"
PUBLIC_ACCESS="dev-url"
CUSTOM_DOMAIN=""
ZONE_ID=""
HEROKU_APP="reputation-juan"

usage() {
  sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="$2"; shift 2 ;;
    --account-id) ACCOUNT_ID="$2"; shift 2 ;;
    --public-access) PUBLIC_ACCESS="$2"; shift 2 ;;
    --domain) CUSTOM_DOMAIN="$2"; shift 2 ;;
    --zone-id) ZONE_ID="$2"; shift 2 ;;
    --heroku-app) HEROKU_APP="$2"; shift 2 ;;
    --skip-heroku) HEROKU_APP=""; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "CLOUDFLARE_API_TOKEN is required." >&2
  echo "Create one at https://dash.cloudflare.com/profile/api-tokens" >&2
  echo "Permissions: Workers R2 Storage → Edit, Account API Tokens → Edit" >&2
  exit 1
fi

if [[ "$PUBLIC_ACCESS" == "domain" && ( -z "$CUSTOM_DOMAIN" || -z "$ZONE_ID" ) ]]; then
  echo "--domain and --zone-id are required when --public-access domain" >&2
  exit 1
fi

cf_api() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local args=(-fsS -X "$method" "https://api.cloudflare.com/client/v4${path}")
  args+=(-H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}")
  args+=(-H "Content-Type: application/json")
  if [[ -n "$data" ]]; then
    args+=(-d "$data")
  fi
  curl "${args[@]}"
}

cf_api_allow_409() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local tmp
  tmp="$(mktemp)"
  local status
  set +e
  status="$(curl -sS -o "$tmp" -w "%{http_code}" -X "$method" \
    "https://api.cloudflare.com/client/v4${path}" \
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
    -H "Content-Type: application/json" \
    ${data:+-d "$data"})"
  set -e
  if [[ "$status" == "409" ]]; then
    cat "$tmp"
    rm -f "$tmp"
    return 0
  fi
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "Cloudflare API ${method} ${path} failed (HTTP ${status}):" >&2
    cat "$tmp" >&2
    rm -f "$tmp"
    exit 1
  fi
  cat "$tmp"
  rm -f "$tmp"
}

resolve_account_id() {
  if [[ -n "$ACCOUNT_ID" ]]; then
    echo "$ACCOUNT_ID"
    return
  fi
  local response
  response="$(cf_api GET "/accounts?per_page=1")"
  python3 - "$response" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if not payload.get("success"):
    raise SystemExit(f"Could not list Cloudflare accounts: {payload}")
accounts = payload.get("result") or []
if not accounts:
    raise SystemExit("No Cloudflare accounts found for this token.")
print(accounts[0]["id"])
PY
}

lookup_permission_group_id() {
  local account_id="$1"
  local group_name="$2"
  local scope="$3"
  local response
  response="$(cf_api GET "/accounts/${account_id}/tokens/permission_groups?scope=${scope}")"
  python3 - "$response" "$group_name" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
target = sys.argv[2]
for group in payload.get("result", []):
    if group.get("name") == target:
        print(group["id"])
        raise SystemExit(0)
raise SystemExit(f"Permission group not found: {target}")
PY
}

create_r2_bucket() {
  local account_id="$1"
  local bucket_name="$2"
  local response
  response="$(cf_api_allow_409 POST "/accounts/${account_id}/r2/buckets" "{\"name\":\"${bucket_name}\"}")"
  python3 - "$response" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if payload.get("success"):
    print("created")
elif any(err.get("code") == 10004 for err in payload.get("errors", [])):
    print("exists")
else:
    raise SystemExit(f"Bucket create failed: {payload}")
PY
}

enable_r2_dev_url() {
  local account_id="$1"
  local bucket_name="$2"
  local response
  response="$(cf_api PUT "/accounts/${account_id}/r2/buckets/${bucket_name}/domains/managed" '{"enabled":true}')"
  python3 - "$response" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if not payload.get("success"):
    raise SystemExit(f"Enable r2.dev failed: {payload}")
domain = (payload.get("result") or {}).get("domain", "")
if not domain:
    raise SystemExit(f"No r2.dev domain in response: {payload}")
print(domain.removeprefix("https://").removeprefix("http://"))
PY
}

attach_custom_domain() {
  local account_id="$1"
  local bucket_name="$2"
  local domain="$3"
  local zone_id="$4"
  local body
  body="$(python3 - "$domain" "$zone_id" <<'PY'
import json, sys
print(json.dumps({"domain": sys.argv[1], "enabled": True, "zoneId": sys.argv[2]}))
PY
)"
  cf_api POST "/accounts/${account_id}/r2/buckets/${bucket_name}/domains/custom" "$body" >/dev/null
  echo "$domain"
}

create_r2_s3_credentials() {
  local account_id="$1"
  local bucket_name="$2"
  local write_group_id
  write_group_id="$(lookup_permission_group_id "$account_id" "Workers R2 Storage Bucket Item Write" "com.cloudflare.edge.r2.bucket")"
  local resource="com.cloudflare.edge.r2.bucket.${account_id}_default_${bucket_name}"
  local token_name="predictstamp-r2-${bucket_name}-$(date +%Y%m%d)"
  local body
  body="$(python3 - "$token_name" "$resource" "$write_group_id" <<'PY'
import json, sys
name, resource, group_id = sys.argv[1:4]
print(json.dumps({
    "name": name,
    "policies": [{
        "effect": "allow",
        "resources": {resource: "*"},
        "permission_groups": [{"id": group_id}],
    }],
}))
PY
)"
  local response
  response="$(cf_api POST "/accounts/${account_id}/tokens" "$body")"
  python3 - "$response" <<'PY'
import hashlib, json, sys
payload = json.loads(sys.argv[1])
if not payload.get("success"):
    raise SystemExit(f"Token creation failed: {payload}")
result = payload["result"]
print(result["id"])
print(hashlib.sha256(result["value"].encode("utf-8")).hexdigest())
PY
}

echo "==> Cloudflare account"
ACCOUNT_ID="$(resolve_account_id)"
echo "    Account ID: $ACCOUNT_ID"
ENDPOINT="https://${ACCOUNT_ID}.r2.cloudflarestorage.com"

echo "==> R2 bucket: $BUCKET"
bucket_status="$(create_r2_bucket "$ACCOUNT_ID" "$BUCKET")"
echo "    Bucket ${bucket_status}"

PUBLIC_HOST=""
case "$PUBLIC_ACCESS" in
  dev-url)
    echo "==> Enabling r2.dev public URL (beta; rate-limited — use custom domain in prod)"
    PUBLIC_HOST="$(enable_r2_dev_url "$ACCOUNT_ID" "$BUCKET")"
    echo "    Public host: $PUBLIC_HOST"
    ;;
  domain)
    echo "==> Attaching custom domain: $CUSTOM_DOMAIN"
    PUBLIC_HOST="$(attach_custom_domain "$ACCOUNT_ID" "$BUCKET" "$CUSTOM_DOMAIN" "$ZONE_ID")"
    echo "    Public host: $PUBLIC_HOST"
    ;;
  skip)
    PUBLIC_HOST="${AWS_S3_CUSTOM_DOMAIN:-}"
    if [[ -z "$PUBLIC_HOST" ]]; then
      echo "Set AWS_S3_CUSTOM_DOMAIN or use --public-access dev-url|domain" >&2
      exit 1
    fi
    ;;
  *)
    echo "Invalid --public-access: $PUBLIC_ACCESS" >&2
    exit 1
    ;;
esac

echo "==> Creating bucket-scoped S3 API credentials"
CREDS_OUTPUT="$(create_r2_s3_credentials "$ACCOUNT_ID" "$BUCKET")"
AWS_ACCESS_KEY_ID="$(printf '%s\n' "$CREDS_OUTPUT" | sed -n '1p')"
AWS_SECRET_ACCESS_KEY="$(printf '%s\n' "$CREDS_OUTPUT" | sed -n '2p')"

export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY
export AWS_STORAGE_BUCKET_NAME="$BUCKET"
export AWS_S3_ENDPOINT_URL="$ENDPOINT"
export AWS_S3_REGION_NAME="auto"
export AWS_S3_CUSTOM_DOMAIN="$PUBLIC_HOST"

echo
echo "==> R2 ready"
echo "    Endpoint:  $ENDPOINT"
echo "    Public URL: https://${PUBLIC_HOST}/"

if [[ -n "$HEROKU_APP" ]]; then
  echo
  echo "==> Configuring Heroku: $HEROKU_APP"
  AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    "$ROOT/scripts/setup_heroku_r2_media.sh" "$HEROKU_APP"
else
  echo
  echo "Run on Heroku:"
  echo "  AWS_SECRET_ACCESS_KEY='...' $ROOT/scripts/setup_heroku_r2_media.sh reputation-juan"
fi

echo
echo "Done."
