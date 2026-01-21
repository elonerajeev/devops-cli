#!/bin/bash
# SSL Certificate Check Script
# Usage: ./ssl-check.sh domain.com [domain2.com ...]

set -e

WARN_DAYS=${WARN_DAYS:-30}
CRITICAL_DAYS=${CRITICAL_DAYS:-7}

echo "========================================="
echo "       SSL Certificate Check            "
echo "========================================="
echo "Warning threshold: $WARN_DAYS days"
echo "Critical threshold: $CRITICAL_DAYS days"
echo ""

check_ssl() {
    local domain=$1
    local port=${2:-443}

    echo "Checking: $domain:$port"

    # Get certificate info
    cert_info=$(echo | timeout 5 openssl s_client -servername "$domain" -connect "$domain:$port" 2>/dev/null | openssl x509 -noout -dates -subject 2>/dev/null)

    if [ -z "$cert_info" ]; then
        echo "  Status: ERROR - Could not retrieve certificate"
        echo ""
        return 1
    fi

    # Extract dates
    not_after=$(echo "$cert_info" | grep "notAfter" | cut -d= -f2)
    subject=$(echo "$cert_info" | grep "subject" | sed 's/subject=//')

    # Calculate days until expiry
    expiry_epoch=$(date -d "$not_after" +%s 2>/dev/null || date -jf "%b %d %T %Y %Z" "$not_after" +%s 2>/dev/null)
    current_epoch=$(date +%s)
    days_left=$(( (expiry_epoch - current_epoch) / 86400 ))

    # Determine status
    if [ $days_left -lt 0 ]; then
        status="EXPIRED"
        color="\033[0;31m"  # Red
    elif [ $days_left -lt $CRITICAL_DAYS ]; then
        status="CRITICAL"
        color="\033[0;31m"  # Red
    elif [ $days_left -lt $WARN_DAYS ]; then
        status="WARNING"
        color="\033[0;33m"  # Yellow
    else
        status="OK"
        color="\033[0;32m"  # Green
    fi

    echo -e "  Subject: $subject"
    echo -e "  Expires: $not_after"
    echo -e "  Days left: $days_left"
    echo -e "  Status: ${color}${status}\033[0m"
    echo ""
}

# Check if domains provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 domain.com [domain2.com ...]"
    echo ""
    echo "Examples:"
    echo "  $0 google.com"
    echo "  $0 example.com api.example.com"
    echo ""
    echo "Environment variables:"
    echo "  WARN_DAYS=30     Warning threshold (days)"
    echo "  CRITICAL_DAYS=7  Critical threshold (days)"
    exit 1
fi

# Check each domain
for domain in "$@"; do
    check_ssl "$domain"
done

echo "========================================="
echo "       Check Complete                   "
echo "========================================="
