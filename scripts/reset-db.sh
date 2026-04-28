#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== RE Lore Oracle — Reset Databases ==="
echo ""
echo "WARNING: This will permanently delete all data in Neo4j and Qdrant."
read -r -p "Are you sure? Type 'yes' to confirm: " confirm

if [[ "$confirm" != "yes" ]]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo ">> Stopping runtime services..."
docker compose -f "$REPO_ROOT/docker-compose.yml" down

echo ">> Removing named volumes..."
docker volume rm re-lore-rag-system-_neo4j_data re-lore-rag-system-_qdrant_data 2>/dev/null || \
  docker volume rm re-lore-oracle_neo4j_data re-lore-oracle_qdrant_data 2>/dev/null || \
  echo "  (volumes may already be removed or named differently — check: docker volume ls)"

echo ""
echo "=== Databases reset. Run pipeline-run.sh to repopulate. ==="
