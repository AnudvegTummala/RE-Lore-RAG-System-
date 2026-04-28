#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_DIR="$REPO_ROOT/pipeline"

echo "=== RE Lore Oracle — Data Pipeline ==="

if [[ ! -f "$PIPELINE_DIR/.env" ]]; then
  echo "ERROR: pipeline/.env not found."
  echo "  Run: cp pipeline/.env.example pipeline/.env && edit it"
  exit 1
fi

# ── Build images ──────────────────────────────────────────────────────────
echo ""
echo ">> Building pipeline images..."
docker compose -f "$PIPELINE_DIR/docker-compose.yml" build

# ── Run scraper ───────────────────────────────────────────────────────────
echo ""
echo ">> Running scraper..."
docker compose -f "$PIPELINE_DIR/docker-compose.yml" run --rm scraper

echo ">> Scraper finished."

# ── Run ingestor ──────────────────────────────────────────────────────────
echo ""
echo ">> Running ingestor..."
docker compose -f "$PIPELINE_DIR/docker-compose.yml" run --rm ingestor

echo ">> Ingestor finished."
echo ""
echo "=== Pipeline complete. Neo4j and Qdrant are loaded. ==="
