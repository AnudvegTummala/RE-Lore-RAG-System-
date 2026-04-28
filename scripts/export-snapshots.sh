#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPORT_DIR="$REPO_ROOT/data/snapshots/$(date +%Y%m%d_%H%M%S)"

echo "=== RE Lore Oracle — Export Snapshots ==="
mkdir -p "$EXPORT_DIR"

# ── Neo4j dump ────────────────────────────────────────────────────────────
echo ""
echo ">> Exporting Neo4j dump..."
docker compose -f "$REPO_ROOT/docker-compose.yml" exec neo4j \
  neo4j-admin database dump neo4j --to-path=/tmp/neo4j_dump.dump 2>/dev/null || \
  echo "  (neo4j-admin dump skipped — neo4j may not be running)"

docker compose -f "$REPO_ROOT/docker-compose.yml" cp \
  neo4j:/tmp/neo4j_dump.dump "$EXPORT_DIR/neo4j.dump" 2>/dev/null || true

# ── Qdrant snapshot ───────────────────────────────────────────────────────
echo ""
echo ">> Creating Qdrant snapshots..."
for collection in lore_text concept_art; do
  curl -sf -X POST "http://localhost:6333/collections/${collection}/snapshots" \
    -o "$EXPORT_DIR/qdrant_${collection}_snapshot.json" && \
    echo "  Snapshot created for: $collection" || \
    echo "  Skipped: $collection (Qdrant not running or collection not found)"
done

echo ""
echo "=== Snapshots exported to: $EXPORT_DIR ==="
