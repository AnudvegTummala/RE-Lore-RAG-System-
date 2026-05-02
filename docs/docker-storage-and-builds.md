# Docker Storage Management & Build Reference

## The Storage Blowup Problem (Fedora Linux + Docker Desktop)

### Root cause

Docker Desktop on Linux runs a QEMU/KVM virtual machine. All image layers, build
cache, and container writable layers live inside a virtual disk image at:

```
~/.docker/desktop/vms/0/data/Docker.raw
```

This file **grows when you add layers but never shrinks when you delete images.**
`docker system prune -a` clears the internal filesystem but the `.raw` file on your
host keeps its peak size. That's why you see "30 GB removed" with no change to
actual disk usage — the space was freed *inside* the VM, not returned to the host.

---

## Fix: Reclaim Space Without Nuking ~/.docker

**Step 1 — Prune everything inside Docker first:**

```bash
docker system prune -a --volumes
```

**Step 2 — Compact the VM disk image** (run after Docker Desktop is fully stopped):

```bash
docker run --rm --privileged --pid=host docker/desktop-reclaim-space
```

Or via the UI: **Docker Desktop → Settings → Resources → Disk image location → Clean / Reclaim space**
(available in Docker Desktop ≥ 4.18).

**Step 3 — Set a disk size cap** so it can never grow unbounded again:

Docker Desktop UI → **Settings → Resources → Virtual disk limit** → set to ~40 GB.

---

## Routine Habits for Repeated Rebuild Workflows

```bash
# After each build session — prune dangling/untagged intermediate layers:
docker image prune -f

# Before a clean rebuild — wipe everything (images, cache, volumes, stopped containers):
docker system prune -a --volumes
```

Use `--no-cache` only when you actually need a fully fresh build. Without it, Docker
reuses unchanged layers and rebuilds are incremental (much smaller disk impact).

---

## Quick Reference

| Problem | Fix |
|---|---|
| `.raw` file won't shrink after pruning | Run `docker/desktop-reclaim-space` or use the UI reclaim button |
| Disk grows unbounded over time | Set a virtual disk cap in Docker Desktop → Resources |
| Build cruft accumulating | `docker image prune -f` after each session |
| Full storage emergency | `docker system prune -a --volumes`, then reclaim space |
| Never nuke `~/.docker/desktop` again | The reclaim-space tool is the correct fix |

---

## Build & Run Commands for This Project

### Runtime stack (Neo4j, Qdrant, clip-service, API)

```bash
# Start all runtime services
docker compose up -d

# Rebuild one service after code changes
docker compose build api

# Tail logs for a specific service
docker compose logs -f api

# Stop everything
docker compose down
```

### Pipeline: Scraper

The scraper has its own `docker-compose.yml` under `pipeline/` and uses
`network_mode: host` to reach the runtime services on localhost. Make sure
the runtime stack is up first and `pipeline/.env` is configured.

```bash
# Build the scraper image (required after requirements.txt or code changes)
docker compose -f pipeline/docker-compose.yml build scraper

# Run the full scraper (all categories, default MAX_PAGES=500)
docker compose -f pipeline/docker-compose.yml run --rm scraper

# Tail logs while running
docker compose -f pipeline/docker-compose.yml logs -f scraper
```

**Smoke test — single category, small page cap:**

```bash
docker compose -f pipeline/docker-compose.yml run --rm \
  -e SCRAPE_TARGET=games \
  -e MAX_PAGES=20 \
  scraper
```

This scrapes ≤20 game pages, then runs the Wikipedia supplement pass on those files.
Fast end-to-end verification before committing to the full run (~3.5 hours).

### Pipeline: Ingestor

Run after the scraper has populated `data/raw/`.

```bash
# Build the ingestor image
docker compose -f pipeline/docker-compose.yml build ingestor

# Run the ingestor
docker compose -f pipeline/docker-compose.yml run --rm ingestor
```

> **Note:** The CLIP service is slow to start — model load takes 2–3 minutes.
> Wait for `health: healthy` in `docker ps` before running the ingestor,
> otherwise image embedding will fail with connection refused.

### Wipe and restart from scratch

```bash
# Wipe Neo4j and Qdrant volumes (data only, not images)
bash scripts/reset-db.sh

# If checkpoint is out of sync after a volume wipe, delete the relevant state files:
# data/state/graph_loader.json
# data/state/text_embedder.json
# data/state/image_embedder.json
# Then re-run the ingestor.
```

---

## Testing the Scraper Changes (Groups 1 & 2)

Run these in order:

```bash
# 1. Build the updated scraper image (picks up new requirements.txt + code changes)
docker compose -f pipeline/docker-compose.yml build scraper

# 2. Smoke test — games only, 20 pages
docker compose -f pipeline/docker-compose.yml run --rm \
  -e SCRAPE_TARGET=games \
  -e MAX_PAGES=20 \
  scraper

# 3. Inspect output
ls data/raw/markdown/games/
cat data/raw/manifests/scrape_manifest.json

# 4. Check a file for Wikipedia supplement
head -80 data/raw/markdown/games/<any-file>.md | grep -A5 "Wikipedia Summary"

# 5. Check that no film-universe pages slipped through (should return nothing)
grep -rl "anderson-characters\|film-creatures\|wildstorm" data/raw/markdown/ || echo "Clean"

# 6. Full run when satisfied
docker compose -f pipeline/docker-compose.yml run --rm scraper
```
