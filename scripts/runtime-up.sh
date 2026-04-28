#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== RE Lore Oracle — Runtime ==="

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "ERROR: .env not found. Run: cp .env.example .env && edit .env"
  exit 1
fi

docker compose -f "$REPO_ROOT/docker-compose.yml" up -d --build

echo ""
echo "=== Runtime services started ==="
echo "  Frontend : http://localhost:3000"
echo "  API      : http://localhost:8000"
echo "  Neo4j    : http://localhost:7474"
echo "  Qdrant   : http://localhost:6333"
echo "  CLIP     : http://localhost:8001"
echo ""
echo "Tail logs: docker compose logs -f"
