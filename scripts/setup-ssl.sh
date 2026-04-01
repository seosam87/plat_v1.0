#!/usr/bin/env bash
# =============================================================================
# Set up Let's Encrypt SSL certificate
# Usage: bash scripts/setup-ssl.sh your-domain.com your@email.com
# =============================================================================
set -euo pipefail

DOMAIN="${1:?Usage: $0 <domain> <email>}"
EMAIL="${2:?Usage: $0 <domain> <email>}"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

echo "=== SSL Setup for ${DOMAIN} ==="

# ------------------------------------------------------------------
# 1. Update nginx config with actual domain
# ------------------------------------------------------------------
echo "Updating nginx config with domain: ${DOMAIN}"
sed -i "s|YOUR_DOMAIN|${DOMAIN}|g" nginx/conf.d/app.conf

# ------------------------------------------------------------------
# 2. Ensure nginx is running (HTTP mode)
# ------------------------------------------------------------------
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d nginx

# ------------------------------------------------------------------
# 3. Issue certificate
# ------------------------------------------------------------------
echo "Requesting certificate from Let's Encrypt..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm certbot \
    certbot certonly \
    --webroot \
    -w /var/www/certbot \
    -d "${DOMAIN}" \
    --email "${EMAIL}" \
    --agree-tos \
    --no-eff-email

# ------------------------------------------------------------------
# 4. Enable HTTPS in nginx config
# ------------------------------------------------------------------
echo "Enabling HTTPS config..."
CONF="nginx/conf.d/app.conf"

# Uncomment the HTTPS redirect block
sed -i '/^# server {$/,/^# }$/s/^# //' "$CONF"

# Uncomment the HTTPS server block
sed -i '/^# server {$/,/^# }$/s/^# //' "$CONF"

# ------------------------------------------------------------------
# 5. Reload nginx
# ------------------------------------------------------------------
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec nginx nginx -s reload

echo ""
echo "=== SSL setup complete ==="
echo "Site is now available at: https://${DOMAIN}"
echo ""
echo "Certificate auto-renewal is handled by the certbot container."
echo "Update GSC_REDIRECT_URI in ${ENV_FILE} to https://${DOMAIN}/gsc/callback"
