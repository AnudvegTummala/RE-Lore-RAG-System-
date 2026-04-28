#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== RE Lore Oracle — Full Dev Stack ==="

# ── Validate env files ──────────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "ERROR: .env not found. Run: cp .env.example .env && edit .env"
  exit 1
fi
if [[ ! -f "$REPO_ROOT/pipeline/.env" ]]; then
  echo "ERROR: pipeline/.env not found. Run: cp pipeline/.env.example pipeline/.env && edit it"
  exit 1
fi

# ── Start runtime services (neo4j, qdrant, clip-service) ───────────────────
echo ""
echo ">> Starting infrastructure services..."
docker compose -f "$REPO_ROOT/docker-compose.yml" up -d neo4j qdrant clip-service

echo ">> Waiting for services to be healthy..."
docker compose -f "$REPO_ROOT/docker-compose.yml" wait neo4j qdrant clip-service || true
sleep 5

# ── Run pipeline ──────────────────────────────────────────────────────────
echo ""
echo ">> Running pipeline (scraper → ingestor)..."
bash "$REPO_ROOT/scripts/pipeline-run.sh"

# ── Start full runtime ────────────────────────────────────────────────────
echo ""
echo ">> Starting API and frontend..."
docker compose -f "$REPO_ROOT/docker-compose.yml" up -d

echo ""
echo "=== Stack is up ==="
echo "  Frontend : http://localhost:3000"
echo "  API      : http://localhost:8000"
echo "  Neo4j    : http://localhost:7474"
echo "  Qdrant   : http://localhost:6333"
