#!/bin/sh
# Runs from /docker-entrypoint.d before nginx starts. Lets the container boot
# with a temporary self-signed certificate so the HTTP-01 challenge can be
# served; scripts/init-letsencrypt.sh replaces it with the real certificate.
set -eu

DOMAIN="${DOMAIN:-hajimi.site}"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

if [ ! -s "${CERT_DIR}/fullchain.pem" ] || [ ! -s "${CERT_DIR}/privkey.pem" ]; then
    echo "No TLS certificate for ${DOMAIN}; generating a temporary self-signed certificate."
    mkdir -p "${CERT_DIR}"
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "${CERT_DIR}/privkey.pem" \
        -out "${CERT_DIR}/fullchain.pem" \
        -subj "/CN=${DOMAIN}"
fi
