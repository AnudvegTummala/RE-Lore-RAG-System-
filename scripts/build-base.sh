#!/usr/bin/env bash
# Builds the re-lore-base image that api and clip-service inherit from.
# Must be run once before "docker compose build" or "docker compose up --build".
#
# Usage:
#   bash scripts/build-base.sh              # auto-detect GPU
#   bash scripts/build-base.sh cpu          # force CPU wheel
#   bash scripts/build-base.sh cuda         # force CUDA wheel
set -euo pipefail

TORCH_DEVICE="${1:-auto}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Building re-lore-base (TORCH_DEVICE=$TORCH_DEVICE)..."
DOCKER_BUILDKIT=1 docker build \
    --build-arg TORCH_DEVICE="$TORCH_DEVICE" \
    -t re-lore-base \
    -t ghcr.io/mhamdashfaque/re-lore-base:latest \
    "$REPO_ROOT/runtime/base"

echo "Done. re-lore-base is ready."
