#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and configure it."
  exit 1
fi

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

echo ">>> Pulling latest code..."
git pull

echo ">>> Pulling latest images..."
docker compose -f "$COMPOSE_FILE" --env-file .env pull 2>/dev/null || true

echo ">>> Recreating containers with current config..."
docker compose -f "$COMPOSE_FILE" --env-file .env up -d --remove-orphans

echo ">>> Done!"
docker compose -f "$COMPOSE_FILE" ps
