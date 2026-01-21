#!/bin/bash
# Docker Cleanup Script - Remove unused Docker resources
# Usage: ./docker-cleanup.sh [--aggressive]

set -e

echo "========================================="
echo "       Docker Cleanup Script            "
echo "========================================="

AGGRESSIVE=false
if [ "$1" == "--aggressive" ]; then
    AGGRESSIVE=true
    echo "Mode: AGGRESSIVE (will remove all unused resources)"
else
    echo "Mode: SAFE (will only remove dangling resources)"
fi

echo ""

# Show current disk usage
echo "Current Docker disk usage:"
docker system df
echo ""

# Remove stopped containers
echo "Removing stopped containers..."
STOPPED=$(docker ps -aq -f status=exited | wc -l)
if [ "$STOPPED" -gt 0 ]; then
    docker rm $(docker ps -aq -f status=exited) 2>/dev/null || true
    echo "  Removed $STOPPED stopped containers"
else
    echo "  No stopped containers found"
fi

# Remove dangling images
echo "Removing dangling images..."
DANGLING=$(docker images -q -f dangling=true | wc -l)
if [ "$DANGLING" -gt 0 ]; then
    docker rmi $(docker images -q -f dangling=true) 2>/dev/null || true
    echo "  Removed $DANGLING dangling images"
else
    echo "  No dangling images found"
fi

# Remove unused volumes
echo "Removing unused volumes..."
docker volume prune -f

# Remove unused networks
echo "Removing unused networks..."
docker network prune -f

# Aggressive mode: remove all unused resources
if [ "$AGGRESSIVE" == true ]; then
    echo ""
    echo "AGGRESSIVE MODE: Removing all unused resources..."
    read -p "This will remove ALL unused images, containers, volumes, and networks. Continue? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker system prune -a -f --volumes
        echo "Aggressive cleanup completed!"
    else
        echo "Aggressive cleanup skipped"
    fi
fi

echo ""
echo "Cleanup completed!"
echo ""
echo "New Docker disk usage:"
docker system df
