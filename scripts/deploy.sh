#!/usr/bin/env bash
# =============================================================================
# First-time deploy script for SEO Platform
# Usage: bash scripts/deploy.sh
# =============================================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

echo "=== SEO Platform — Production Deploy ==="

# ------------------------------------------------------------------
# 1. Check prerequisites
# ------------------------------------------------------------------
for cmd in docker git openssl python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd is not installed." >&2
        exit 1
    fi
done

if ! docker compose version &>/dev/null; then
    echo "ERROR: docker compose v2 plugin is required." >&2
    exit 1
fi

# ------------------------------------------------------------------
# 2. Generate .env.prod if missing
# ------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    echo "Generating $ENV_FILE with random secrets..."
    cp .env.prod.example "$ENV_FILE"

    PG_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    REDIS_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    JWT_SECRET=$(openssl rand -hex 32)
    FERNET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    # Fill in generated values
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" "$ENV_FILE"
    sed -i "s|PASSWORD_HERE\(.*@postgres\)|${PG_PASS}\1|g" "$ENV_FILE"
    sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASS}|" "$ENV_FILE"
    sed -i "s|REDIS_PASSWORD_HERE|${REDIS_PASS}|g" "$ENV_FILE"
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${JWT_SECRET}|" "$ENV_FILE"
    sed -i "s|^FERNET_KEY=.*|FERNET_KEY=${FERNET}|" "$ENV_FILE"

    echo "Created $ENV_FILE — review it before continuing."
    echo "At minimum, set FLOWER_BASIC_AUTH to a strong password."
    echo ""
    read -rp "Press Enter to continue after reviewing $ENV_FILE..."
fi

# ------------------------------------------------------------------
# 3. Build and start
# ------------------------------------------------------------------
echo "Building images..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build

echo "Starting services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

# ------------------------------------------------------------------
# 4. Wait for API to be healthy
# ------------------------------------------------------------------
echo "Waiting for API to start..."
for i in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
        python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" &>/dev/null; then
        echo "API is up!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "WARNING: API did not respond within 30 attempts. Check logs:"
        echo "  docker compose -f $COMPOSE_FILE --env-file $ENV_FILE logs api"
    fi
    sleep 2
done

# ------------------------------------------------------------------
# 5. Seed admin user
# ------------------------------------------------------------------
echo "Seeding admin user..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
    python scripts/seed_admin.py || true

# ------------------------------------------------------------------
# 6. Done
# ------------------------------------------------------------------
echo ""
echo "=== Deploy complete ==="
echo ""
echo "Services:"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "Next steps:"
echo "  1. Open http://YOUR_SERVER_IP in browser"
echo "  2. Login: admin@example.com / changeme  (change password immediately!)"
echo "  3. Set up SSL — see scripts/setup-ssl.sh"
echo "  4. Configure Flower password in .env.prod (FLOWER_BASIC_AUTH)"
echo ""
echo "Useful commands:"
echo "  docker compose -f $COMPOSE_FILE --env-file $ENV_FILE logs -f        # follow logs"
echo "  docker compose -f $COMPOSE_FILE --env-file $ENV_FILE ps             # service status"
echo "  docker compose -f $COMPOSE_FILE --env-file $ENV_FILE restart api    # restart API"
