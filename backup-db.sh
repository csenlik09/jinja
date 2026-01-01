#!/bin/bash

# Backup database before major changes
# Usage: ./backup-db.sh [version-tag]

VERSION=$1
REMOTE_HOST="172.16.20.201"
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d-%H%M%S)

if [ -z "$VERSION" ]; then
    VERSION="backup-$DATE"
fi

mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "Backing up Database"
echo "Version: $VERSION"
echo "=========================================="

echo ""
echo "[1/2] Copying database from server..."
scp $REMOTE_HOST:/root/jinja/database.db "$BACKUP_DIR/database-$VERSION.db"

echo ""
echo "[2/2] Creating backup archive..."
tar -czf "$BACKUP_DIR/full-backup-$VERSION.tar.gz" \
    -C "$BACKUP_DIR" "database-$VERSION.db" \
    2>/dev/null || true

echo ""
echo "✅ Backup completed!"
echo "   Database: $BACKUP_DIR/database-$VERSION.db"
echo "   Archive: $BACKUP_DIR/full-backup-$VERSION.tar.gz"
echo ""
echo "To restore:"
echo "   scp $BACKUP_DIR/database-$VERSION.db $REMOTE_HOST:/root/jinja/database.db"
