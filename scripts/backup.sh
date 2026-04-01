#!/usr/bin/env bash
# =============================================================================
# Database backup script
# Usage: bash scripts/backup.sh
# Add to cron: 0 3 * * * cd /path/to/project && bash scripts/backup.sh
# =============================================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
BACKUP_DIR="./backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Load DB credentials
source "$ENV_FILE"

echo "Backing up database..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
    > "${BACKUP_DIR}/db_${TIMESTAMP}.dump"

# Compress
gzip "${BACKUP_DIR}/db_${TIMESTAMP}.dump"

# Clean old backups
find "$BACKUP_DIR" -name "db_*.dump.gz" -mtime +"$RETENTION_DAYS" -delete

SIZE=$(du -h "${BACKUP_DIR}/db_${TIMESTAMP}.dump.gz" | cut -f1)
echo "Backup complete: ${BACKUP_DIR}/db_${TIMESTAMP}.dump.gz (${SIZE})"
