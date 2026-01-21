#!/bin/bash
# Docker Compose Deployment Script
# Usage: ./deploy-docker.sh [service_name]

set -e

SERVICE=${1:-}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}
ENV_FILE=${ENV_FILE:-.env}

echo "========================================="
echo "       Docker Compose Deployment        "
echo "========================================="
echo "Compose file: $COMPOSE_FILE"
echo "Environment: $ENV_FILE"
echo "Service: ${SERVICE:-all}"
echo ""

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: $COMPOSE_FILE not found"
    exit 1
fi

# Load environment file if exists
if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
fi

# Pull latest images
echo ""
echo "[1/4] Pulling latest images..."
if [ -n "$SERVICE" ]; then
    docker compose -f "$COMPOSE_FILE" pull "$SERVICE"
else
    docker compose -f "$COMPOSE_FILE" pull
fi

# Build if necessary
echo ""
echo "[2/4] Building images (if needed)..."
if [ -n "$SERVICE" ]; then
    docker compose -f "$COMPOSE_FILE" build --pull "$SERVICE"
else
    docker compose -f "$COMPOSE_FILE" build --pull
fi

# Deploy
echo ""
echo "[3/4] Deploying..."
if [ -n "$SERVICE" ]; then
    docker compose -f "$COMPOSE_FILE" up -d --remove-orphans "$SERVICE"
else
    docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
fi

# Health check
echo ""
echo "[4/4] Checking deployment status..."
sleep 5

docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "========================================="
echo "       Deployment Complete              "
echo "========================================="

# Show logs hint
echo ""
echo "View logs with:"
if [ -n "$SERVICE" ]; then
    echo "  docker compose logs -f $SERVICE"
else
    echo "  docker compose logs -f"
fi
