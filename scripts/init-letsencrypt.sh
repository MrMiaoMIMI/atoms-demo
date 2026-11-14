#!/usr/bin/env bash
# First-time Let's Encrypt certificate for the nginx container.
#
# Usage:
#   CERTBOT_EMAIL=you@example.com ./scripts/init-letsencrypt.sh
#   FORCE=1 CERTBOT_EMAIL=you@example.com DOMAIN=hajimi.site ./scripts/init-letsencrypt.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

DOMAIN="${DOMAIN:-hajimi.site}"
EMAIL="${CERTBOT_EMAIL:-}"
FORCE="${FORCE:-0}"

if [ -z "$EMAIL" ]; then
    echo "缺少邮箱：CERTBOT_EMAIL=you@example.com ./scripts/init-letsencrypt.sh" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "未找到 docker，请先在服务器安装 Docker。" >&2
    exit 1
fi

mkdir -p certbot/conf certbot/www

if [ -f "certbot/conf/renewal/${DOMAIN}.conf" ] && [ "$FORCE" != "1" ]; then
    echo "已检测到 ${DOMAIN} 的证书，跳过签发。"
    echo "如需强制重新签发：FORCE=1 CERTBOT_EMAIL=${EMAIL} ./scripts/init-letsencrypt.sh"
    exit 0
fi

echo "[1/4] 启动 nginx（首次会自动生成临时自签名证书）..."
docker compose up -d web
sleep 3

echo "[2/4] 清理临时证书..."
rm -rf "certbot/conf/live/${DOMAIN}" \
       "certbot/conf/archive/${DOMAIN}" \
       "certbot/conf/renewal/${DOMAIN}.conf"

echo "[3/4] 申请 Let's Encrypt 证书..."
docker run --rm \
    -v "${PROJECT_DIR}/certbot/conf:/etc/letsencrypt" \
    -v "${PROJECT_DIR}/certbot/www:/var/www/certbot" \
    certbot/certbot certonly \
    --webroot -w /var/www/certbot \
    -d "${DOMAIN}" \
    --email "${EMAIL}" \
    --agree-tos --no-eff-email --non-interactive

echo "[4/4] 重载 nginx..."
docker compose exec -T web nginx -s reload

echo "完成：https://${DOMAIN}"
echo "请确认 backend/.env 包含："
echo "  PUBLIC_BASE_URL=https://${DOMAIN}"
echo "  AUTH_COOKIE_SECURE=1"
