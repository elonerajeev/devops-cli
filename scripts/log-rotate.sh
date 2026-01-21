#!/bin/bash
# Log Rotation and Cleanup Script
# Usage: ./log-rotate.sh [log_directory]

set -e

LOG_DIR=${1:-/var/log}
MAX_SIZE_MB=${MAX_SIZE_MB:-100}
RETENTION_DAYS=${RETENTION_DAYS:-30}
COMPRESS_DAYS=${COMPRESS_DAYS:-1}

echo "========================================="
echo "       Log Rotation & Cleanup           "
echo "========================================="
echo "Log directory: $LOG_DIR"
echo "Max file size: ${MAX_SIZE_MB}MB"
echo "Retention: $RETENTION_DAYS days"
echo "Compress after: $COMPRESS_DAYS days"
echo ""

# Check if directory exists
if [ ! -d "$LOG_DIR" ]; then
    echo "Error: Directory $LOG_DIR does not exist"
    exit 1
fi

# Show current disk usage
echo "[Current disk usage]"
du -sh "$LOG_DIR" 2>/dev/null || echo "Cannot read directory"
echo ""

# Find and compress old uncompressed logs
echo "[Compressing logs older than $COMPRESS_DAYS day(s)]"
find "$LOG_DIR" -name "*.log" -mtime +$COMPRESS_DAYS -exec gzip -v {} \; 2>/dev/null || true
echo ""

# Delete old compressed logs
echo "[Removing logs older than $RETENTION_DAYS days]"
find "$LOG_DIR" -name "*.gz" -mtime +$RETENTION_DAYS -delete -print 2>/dev/null || true
find "$LOG_DIR" -name "*.log.*" -mtime +$RETENTION_DAYS -delete -print 2>/dev/null || true
echo ""

# Rotate large log files
echo "[Rotating files larger than ${MAX_SIZE_MB}MB]"
MAX_SIZE_BYTES=$((MAX_SIZE_MB * 1024 * 1024))
find "$LOG_DIR" -name "*.log" -size +${MAX_SIZE_MB}M -exec sh -c '
    for f do
        timestamp=$(date +%Y%m%d_%H%M%S)
        mv "$f" "${f}.${timestamp}"
        touch "$f"
        echo "Rotated: $f -> ${f}.${timestamp}"
    done
' sh {} + 2>/dev/null || true
echo ""

# Clean up empty files
echo "[Removing empty log files]"
find "$LOG_DIR" -name "*.log" -empty -delete -print 2>/dev/null || true
echo ""

# Show new disk usage
echo "[New disk usage]"
du -sh "$LOG_DIR" 2>/dev/null || echo "Cannot read directory"

echo ""
echo "========================================="
echo "       Rotation Complete                "
echo "========================================="
