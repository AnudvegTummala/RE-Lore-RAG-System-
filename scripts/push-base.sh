#!/usr/bin/env bash
# Pushes the pre-built re-lore-base image to GHCR so teammates can pull
# instead of building from scratch.
#
# Prerequisites:
#   1. Run scripts/build-base.sh first
#   2. Authenticate: echo $GITHUB_TOKEN | docker login ghcr.io -u <username> --password-stdin
#
# Usage:
#   bash scripts/push-base.sh
set -euo pipefail

echo "Pushing re-lore-base to GHCR..."
docker push ghcr.io/mhamdashfaque/re-lore-base:latest

echo "Done. Teammates can now run:"
echo "  docker pull ghcr.io/mhamdashfaque/re-lore-base:latest"
