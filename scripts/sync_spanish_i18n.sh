#!/usr/bin/env bash
# Extract new strings, apply Spanish fixes, compile .mo files.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 manage.py makemessages -l es --ignore=venv --ignore=.venv --no-location
python3 scripts/complete_spanish_i18n.py
python3 manage.py compilemessages
echo "Spanish i18n synced. Commit locale/es/LC_MESSAGES/django.po and django.mo."
