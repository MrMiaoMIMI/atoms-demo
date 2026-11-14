#!/usr/bin/env bash
# Renew the certificate and reload nginx. Safe to run from cron.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p certbot/conf certbot/www

docker run --rm \
    -v "${PROJECT_DIR}/certbot/conf:/etc/letsencrypt" \
    -v "${PROJECT_DIR}/certbot/www:/var/www/certbot" \
    certbot/certbot renew --webroot -w /var/www/certbot --quiet

docker compose exec -T web nginx -s reload
