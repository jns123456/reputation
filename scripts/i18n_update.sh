#!/usr/bin/env bash
# Refresh Spanish translations after changing trans/blocktrans strings or gettext in Python.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 manage.py makemessages -l es --no-obsolete --ignore=.venv --ignore=node_modules
python3 scripts/complete_spanish_i18n.py
python3 manage.py compilemessages

echo "i18n update complete."
