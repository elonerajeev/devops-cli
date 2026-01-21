#!/bin/bash
# Database Backup Script
# Usage: ./backup-db.sh [postgres|mysql] [database_name]

set -e

DB_TYPE=${1:-postgres}
DB_NAME=${2:-myapp}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/database}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=${RETENTION_DAYS:-7}

echo "========================================="
echo "       Database Backup Script           "
echo "========================================="
echo "Database Type: $DB_TYPE"
echo "Database Name: $DB_NAME"
echo "Backup Directory: $BACKUP_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

backup_postgres() {
    BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

    echo "Starting PostgreSQL backup..."

    if [ -n "$PGHOST" ]; then
        # Remote backup
        pg_dump -h "$PGHOST" -U "${PGUSER:-postgres}" "$DB_NAME" | gzip > "$BACKUP_FILE"
    else
        # Local backup (via docker if available)
        if docker ps --format '{{.Names}}' | grep -q postgres; then
            docker exec postgres pg_dump -U "${PGUSER:-postgres}" "$DB_NAME" | gzip > "$BACKUP_FILE"
        else
            pg_dump -U "${PGUSER:-postgres}" "$DB_NAME" | gzip > "$BACKUP_FILE"
        fi
    fi

    echo "Backup created: $BACKUP_FILE"
    echo "Size: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
}

backup_mysql() {
    BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

    echo "Starting MySQL backup..."

    if [ -n "$MYSQL_HOST" ]; then
        # Remote backup
        mysqldump -h "$MYSQL_HOST" -u "${MYSQL_USER:-root}" -p"${MYSQL_PASSWORD}" "$DB_NAME" | gzip > "$BACKUP_FILE"
    else
        # Local backup (via docker if available)
        if docker ps --format '{{.Names}}' | grep -q mysql; then
            docker exec mysql mysqldump -u "${MYSQL_USER:-root}" -p"${MYSQL_PASSWORD}" "$DB_NAME" | gzip > "$BACKUP_FILE"
        else
            mysqldump -u "${MYSQL_USER:-root}" -p"${MYSQL_PASSWORD}" "$DB_NAME" | gzip > "$BACKUP_FILE"
        fi
    fi

    echo "Backup created: $BACKUP_FILE"
    echo "Size: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
}

cleanup_old_backups() {
    echo ""
    echo "Cleaning up backups older than $RETENTION_DAYS days..."
    find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +$RETENTION_DAYS -delete

    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null | wc -l)
    echo "Remaining backups: $BACKUP_COUNT"
}

# Run backup based on database type
case $DB_TYPE in
    postgres|postgresql|pg)
        backup_postgres
        ;;
    mysql|mariadb)
        backup_mysql
        ;;
    *)
        echo "Error: Unsupported database type: $DB_TYPE"
        echo "Supported types: postgres, mysql"
        exit 1
        ;;
esac

# Cleanup old backups
cleanup_old_backups

echo ""
echo "========================================="
echo "       Backup Complete                  "
echo "========================================="
