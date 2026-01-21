#!/bin/bash
# Server Health Check Script
# Usage: ./server-health.sh

set -e

echo "========================================="
echo "       Server Health Check              "
echo "========================================="
echo "Hostname: $(hostname)"
echo "Date: $(date)"
echo ""

# CPU Usage
echo "[CPU Usage]"
top -bn1 | head -5 | tail -3
echo ""

# Memory Usage
echo "[Memory Usage]"
free -h
echo ""

# Disk Usage
echo "[Disk Usage]"
df -h | grep -E '^/dev|^Filesystem'
echo ""

# Top Processes
echo "[Top 5 CPU-consuming processes]"
ps aux --sort=-%cpu | head -6
echo ""

# Load Average
echo "[Load Average]"
uptime
echo ""

# Network Connections
echo "[Network Connections Summary]"
ss -s
echo ""

# Docker Status (if installed)
if command -v docker &> /dev/null; then
    echo "[Docker Status]"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker not running"
    echo ""
fi

# Systemd Failed Services
if command -v systemctl &> /dev/null; then
    echo "[Failed Services]"
    systemctl --failed --no-pager 2>/dev/null || echo "No systemd"
    echo ""
fi

# Recent errors in syslog
echo "[Recent Errors (last 10)]"
grep -i error /var/log/syslog 2>/dev/null | tail -5 || echo "No syslog access or no errors"

echo ""
echo "========================================="
echo "       Health Check Complete            "
echo "========================================="
