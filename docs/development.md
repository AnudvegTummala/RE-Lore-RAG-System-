# Development Guide

Command reference for contributors. See [architecture.md](architecture.md) for system design rationale.

---

## Environment Setup

Two env files are required — copy and fill in before first run:

```bash
cp .env.example .env                   # runtime: GROQ_API_KEY, NEO4J_PASSWORD
cp pipeline/.env.example pipeline/.env # pipeline: NEO4J_PASSWORD (same value)
```

| Variable | File | Description |
|---|---|---|
| `GROQ_API_KEY` | `.env` | Groq API key — get one at console.groq.com |
| `NEO4J_PASSWORD` | both | Must match across both files |
| `GROQ_MODEL` | `.env` | Defaults to `llama-3.3-70b-versatile` |
| `TORCH_DEVICE` | `.env` | `auto` (default), `cpu`, or `cuda` — controls PyTorch wheel at build time |

---

## Docker (full stack)

```bash
# Build the shared base image first (heavy ML deps — run once)
bash scripts/build-base.sh              # auto-detects CPU vs CUDA
bash scripts/build-base.sh cpu          # force CPU wheel (~250MB)
bash scripts/build-base.sh cuda         # force CUDA wheel (~1.5GB)

# Start all runtime services
docker compose up -d

# Tail logs for a specific service
docker compose logs -f api
docker compose logs -f clip-service

# Rebuild one service after code changes (base layer is cached, fast)
docker compose build api
docker compose up -d api

# Wipe Neo4j and Qdrant volumes and start fresh
bash scripts/reset-db.sh
```

---

## Data Pipeline

Run once after runtime services are healthy. Runtime services must be up first.

```bash
# Run scraper then ingestor in sequence
bash scripts/pipeline-run.sh

# Or run individually
docker compose -f pipeline/docker-compose.yml run --rm scraper
docker compose -f pipeline/docker-compose.yml run --rm ingestor
```

Checkpoints live at `data/state/`. If you wipe a database volume, delete the matching checkpoint file before re-running or the ingestor will skip already-"done" steps against an empty database:

```bash
rm data/state/graph_loader.json     # re-run Neo4j graph loading
rm data/state/text_embedder.json    # re-run Qdrant text embedding
rm data/state/image_embedder.json   # re-run Qdrant image embedding
```

---

## Python (API)

```bash
source .venv/bin/activate

# Lint
ruff check runtime/api/app/
ruff check runtime/clip-service/app/
ruff check pipeline/scraper/app/ pipeline/ingestor/app/

# Run API locally (requires Neo4j, Qdrant, clip-service running)
cd runtime/api && uvicorn app.main:app --reload --port 8000

# Run a single test
pytest runtime/api/tests/test_nodes.py::test_classify_query -v

# Run all API tests
pytest runtime/api/tests/ -v --tb=short
```

---

## Frontend

```bash
cd runtime/frontend
npm run dev        # dev server at http://localhost:3000
npx tsc --noEmit   # type check
```

Vite proxies all `/api/*` requests to the FastAPI server. Inside Docker the proxy target is `http://api:8000` (service name, set via `VITE_API_URL`). Locally it points to `localhost:8000`.

---

## GHCR (pre-built base image for teammates)

Teammates can pull the pre-built base image instead of building it locally:

```bash
docker pull ghcr.io/mhamdashfaque/re-lore-base:latest
```

To publish an updated base image:

```bash
# Authenticate first
echo $GITHUB_TOKEN | docker login ghcr.io -u mhamdashfaque --password-stdin

bash scripts/build-base.sh
bash scripts/push-base.sh
```

---

## Adding a LangGraph Node

1. Create `runtime/api/app/graph/nodes/your_node.py` with an `async def your_node(state: GraphState) -> GraphState` function
2. Add any new state keys to `graph/state.py` (`GraphState` TypedDict)
3. Register the node and edges in `graph/workflow.py` → `build_graph()`
4. Restart the API — `compiled_graph` is a module-level singleton rebuilt on import

---

## Known Gotchas

- **CLIP service is slow to start** — model load takes 2–3 min. Wait for `healthy` in `docker ps` before running the ingestor.
- **Qdrant Docker image has no wget/curl** — healthcheck uses `bash -c 'exec 3<>/dev/tcp/127.0.0.1/6333'`.
- **api pip resolver times out with loose version bounds** — all langchain/langgraph deps are pinned to exact versions in `runtime/api/requirements.txt`.
- **clip-service Debian package rename** — `libgl1-mesa-glx` → `libgl1` and `libglib2.0-0` → `libglib2.0-0t64` in Debian Trixie (python:3.11-slim base).
- **torch<2.6.0 not available for Python 3.13** — clip-service uses `torch>=2.6.0`.
- **llama3-70b-8192 decommissioned by Groq** — use `llama-3.3-70b-versatile`.
- **VITE_API_URL must use Docker service name** — inside Docker, `localhost` in the frontend container refers to itself. `docker-compose.yml` sets `VITE_API_URL=http://api:8000`.
- **Ingestor checkpoint out of sync** — if a Qdrant or Neo4j volume is wiped after a run, delete the relevant checkpoint file and re-run the ingestor.
- **Neo4j password must match across both `.env` files** — if Neo4j was previously initialised with a different password, wipe the volume: `docker volume rm re-lore-rag-system-_neo4j_data`.
- **Qdrant client/server version mismatch** — `qdrant-client==1.11.x` requires Qdrant server ≥1.10.0 for the `query_points` endpoint. Keep the server image version in `docker-compose.yml` in sync with the client pinned in `requirements.txt`.
