#!/usr/bin/env bash
set -e

pip install --break-system-packages -r requirements.txt

python manage.py collectstatic --noinput --clear

# Vercel's @vercel/static-build expects output in staticfiles_build/
mkdir -p staticfiles_build/static
cp -r staticfiles/* staticfiles_build/static/ 2>/dev/null || true
