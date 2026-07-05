#!/bin/bash

DB="/home/claude-runner/ai-trading-system/logs/decisions.db"
BACKUP_DIR="/home/claude-runner/backups/ai-trading-system"
DATE=$(date +%Y-%m-%d_%H-%M)
BACKUP_FILE="$BACKUP_DIR/decisions_$DATE.db"

cp "$DB" "$BACKUP_FILE"

# Zostaw tylko ostatnie 7 kopii, starsze usuń
ls -t "$BACKUP_DIR"/decisions_*.db | tail -n +8 | xargs -r rm

echo "[$DATE] Backup zapisany: $BACKUP_FILE"
