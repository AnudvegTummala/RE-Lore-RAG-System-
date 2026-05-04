# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Python (activate venv first)

```bash
source .venv/bin/activate
```

**Lint:**

```bash
ruff check runtime/api/app/
ruff check runtime/clip-service/app/
ruff check pipeline/scraper/app/ pipeline/ingestor/app/
```

**Run API locally (requires Neo4j, Qdrant, clip-service running):**

```bash
cd runtime/api && uvicorn app.main:app --reload --port 8000
```

**Run a single test:**

```bash
pytest runtime/api/tests/test_nodes.py::test_classify_query -v
```

**Run all API tests:**

```bash
pytest runtime/api/tests/ -v --tb=short
```

### Frontend

```bash
cd runtime/frontend
npm run dev        # dev server at http://localhost:3000
npx tsc --noEmit   # type check
```

### Docker (full stack)

```bash
bash scripts/build-base.sh cpu  # build shared base image (once, or after ML dep changes)
docker compose up -d                                        # start all runtime services (Neo4j, Qdrant, clip-service, api)
docker compose -f pipeline/docker-compose.yml run --rm ingestor  # run ingestor (requires runtime services up)
docker compose logs -f api                                  # tail a specific service
docker compose build api                                    # rebuild one service (fast — inherits re-lore-base)
bash scripts/reset-db.sh       # wipe Neo4j and Qdrant volumes
```

**Two separate env files are required:**

- `.env` — runtime (copy from `.env.example`, set `GROQ_API_KEY` and `NEO4J_PASSWORD`)
- `pipeline/.env` — pipeline (copy from `pipeline/.env.example`, same password, point URLs at localhost)

---

## Architecture

### LangGraph Query Pipeline

Every user query runs through a LangGraph `StateGraph` compiled at import time in `runtime/api/app/graph/workflow.py`. All nodes share a single typed state object (`GraphState` in `graph/state.py`).

```
                         ┌→ graph_retrieval ─┐
START → classify_query ──┤                   ├→ rerank → [image_retrieval →] assemble_evidence → generate_answer → END
                         └→ vector_retrieval ┘
```

`graph_retrieval` and `vector_retrieval` run **in parallel** (fan-out from `classify_query`). LangGraph's fan-in semantics hold `rerank` until both complete.

**Key detail:** `compiled_graph` is a module-level singleton created at import. Adding or renaming nodes requires editing `build_graph()` in `workflow.py` and restarting the server.

**Node responsibilities:**
| Node | File | What it does |
|---|---|---|
| `classify_query` | `nodes/classify.py` | Regex entity extraction + sets `needs_image_search` flag |
| `graph_retrieval` | `nodes/graph_retrieval.py` | Cypher 1-hop traversal on Neo4j; matches `e.title` OR `e.name` (case-insensitive) |
| `vector_retrieval` | `nodes/vector_retrieval.py` | Hybrid dense+BM25 search → Qdrant `lore_text` top-15 candidates |
| `rerank` | `nodes/rerank.py` | Cross-encoder scores all candidates; keeps results ≥0.3 threshold (top-3 max) |
| `image_retrieval` | `nodes/image_retrieval.py` | CLIP embed → Qdrant `concept_art` filtered to visual entity_ids from graph+text results |
| `assemble_evidence` | `nodes/assemble.py` | Merge results → `evidence` string; deduplicates by (entity_id, section); skips sections with <80 meaningful chars |
| `generate_answer` | `nodes/generate.py` | ChatGroq with `streaming=True` → `answer` |

`classify_query` uses a **regex heuristic** (four patterns: title-case, ALL_CAPS, dotted abbreviations, hyphenated names; plus known RE aliases) — not spaCy. The `needs_image_search` flag is the only conditional edge in the graph.

**Lowercase queries:** When the query has no capitalised entity hints, `graph_retrieval` returns nothing. `_serialise_graph` in `routers/query.py` falls back to building graph nodes from `text_results` entity_ids so the Knowledge Graph panel always shows something.

**Image retrieval filtering:** `image_retrieval` builds its entity filter from two sources: (1) entity_ids extracted from `graph_results` nodes filtered to visual prefixes (`character-*`, `enemy-*`, `organization-*`), and (2) text_results entity_ids with the same prefix filter. Graph ids take priority because they are the verified Neo4j matches. Game/location/weapon entity_ids are explicitly excluded — their images are cover art and screenshots, not character concept art.

**Graph serialisation cap:** `_serialise_graph` limits output to 60 nodes and trims dangling edges. Without this cap, a 1-hop APOC subgraph across 18k+ MENTIONS edges returns hundreds of nodes and crashes the Cytoscape renderer.

### SSE Streaming

`POST /query` (in `routers/query.py`) calls `compiled_graph.astream_events(initial_state, version="v2")` and filters two event types:

- `on_chat_model_stream` → streams `{"token": "..."}` events immediately
- `on_chain_end` where `name == "LangGraph"` → emits the final `{"done": true, "answer": ..., "sources": ..., "images": ..., "graph": ...}` event

The frontend's `useStreaming` hook (`src/hooks/useStreaming.ts`) drives all chat state. It appends tokens by calling `updateLastMessage` which replaces the last entry in the Zustand messages array. The `assistantMsg.content` local variable is kept in sync with the store for the token accumulation pattern to work correctly.

### Services (runtime/api)

All services are module-level singletons:

- `neo4j_service` (`services/neo4j_service.py`) — lazy `AsyncDriver` init
- `qdrant_service` (`services/qdrant_service.py`) — lazy `AsyncQdrantClient` + `SentenceTransformer` init; `encode()` runs in a thread executor to avoid blocking the event loop
- `clip_client` (`services/clip_service_client.py`) — stateless HTTP client to the CLIP microservice
- `get_llm()` (`services/llm.py`) — `@lru_cache` returning a single `ChatGroq` instance

Config is loaded from `.env` via `pydantic-settings` into `core/config.py`'s `settings` singleton.

### Image Serving

`main.py` mounts a `StaticFiles` handler at `/images` pointing to `/data/raw/images`. The frontend accesses images via `/api/images/…` (with the `/api` prefix so the Vite proxy forwards the request to the API). `_serialise_images()` in `query.py` converts the container path `/data/raw/images/X` → `/api/images/X`.

### Frontend State

Zustand store in `src/store/appStore.ts` is the single source of truth: `messages[]`, `isStreaming`, `activeGraph`, `selectedNode`. Components read from it via `useChat` / `useGraph` hooks.

Vite proxies all `/api/*` requests to the FastAPI server (stripping the `/api` prefix), configured in `vite.config.ts`. **Inside Docker the proxy target must be `http://api:8000` (service name), not `localhost:8000`.**

### Data Pipeline (offline, run before runtime)

Two separate services, run once to build the corpus:

1. **Scraper** (`pipeline/scraper/`) — `BaseScraper` with rate limiting and checkpoint support. Fetches article HTML via `api.php?action=parse` (bypasses Cloudflare JS challenge on rendered pages). Outputs markdown files to `data/raw/markdown/{category}/` and images to `data/raw/images/`. Each markdown file has YAML frontmatter with `id`, `entity_type`, `related_games`, `image_refs`, `tags`. Categories are pulled from the API response (`prop=categories`) — the rendered HTML category links are absent in the parse API output.

   - **7 parsers, not 4**: `character`, `game`, `enemy`, `location`, `organization`, `virus`, `weapon` — all delegate to `parsers/common.py` (`parse_entity_page`).
   - **URL discovery**: `api.php?action=query&list=categorymembers` with recursive BFS (depth ≤ 5) — avoids Cloudflare-blocked category HTML pages.
   - **3 manifest files**: `image_manifest.json` (flat dict, `image_id → meta`), `source_registry.json`, `scrape_manifest.json` — all under `data/raw/manifests/`.

2. **Ingestor** (`pipeline/ingestor/`) — reads markdown, chunks hierarchically by heading (`utils/chunker.py`; parent ≤1500 chars, child ≤400 chars with contextual prefix), creates Neo4j nodes + relationship types, embeds text chunks into Qdrant `lore_text` (dim=384, `all-MiniLM-L6-v2`), embeds images into Qdrant `concept_art` (dim=512, CLIP `ViT-B-32`). Image manifest is read from `/data/raw/manifests/image_manifest.json` (flat dict, no wrapper key). Images are sent to the CLIP service as `multipart/form-data` (`UploadFile`). Checkpoints stored at `/data/state/` (not `/data/checkpoints/`).

The pipeline has its **own `docker-compose.yml`** in `pipeline/` and runs offline — it does not share a Docker network with the runtime stack. Both pipeline services use `network_mode: host` so they can reach the runtime services on localhost. Point `pipeline/.env` at the runtime services' host ports before running.

### Neo4j Schema

Constraints enforced at startup (`pipeline/ingestor/app/graph/schema.py`): `id` is unique per label (`Character`, `Game`, `Enemy`, `Virus`, `Organization`, `Location`, `Weapon`, `ConceptArt`, `LoreChunk`, `TimelineEvent`). Title indexes exist per label for fast lookup. Graph retrieval uses APOC `subgraphAll` for 2-hop traversal — the Neo4j container loads APOC via the `NEO4J_PLUGINS` env var in `docker-compose.yml`.

### Qdrant Collections

| Collection    | Model            | Dimensions | Populated by                                         |
| ------------- | ---------------- | ---------- | ---------------------------------------------------- |
| `lore_text`   | all-MiniLM-L6-v2 | 384        | `pipeline/ingestor/app/embeddings/text_embedder.py`  |
| `concept_art` | CLIP ViT-B-32    | 512        | `pipeline/ingestor/app/embeddings/image_embedder.py` |

Both collections have a keyword payload index on `entity_id` for efficient filtered search. Collections are created idempotently by the ingestor before upserting. The CLIP service (`runtime/clip-service/`) is the only component that runs the OpenCLIP model — both the ingestor and the API's `image_retrieval` node call it over HTTP.

---

## Known Gotchas

- **Build the base image first** — `api` and `clip-service` both start with `FROM re-lore-base`. Run `bash scripts/build-base.sh cpu` before `docker compose build` or the build fails with "image not found".
- **Parallel nodes must return partial state** — `graph_retrieval` and `vector_retrieval` run concurrently. Each must return only the keys it writes (`{"graph_results": ...}` and `{"text_results": ...}`). Returning `{**state, ...}` (full state spread) causes `InvalidUpdateError: At key 'query': Can receive only one value per step` because both nodes write to the same channel simultaneously.
- **Reranker deadlock on CPU Docker** — `OMP_NUM_THREADS=1` and `TOKENIZERS_PARALLELISM=false` must be set in the api container environment (already in `docker-compose.yml`). Without these, PyTorch/OpenMP spawns threads inside the asyncio worker and deadlocks. `torch.set_num_threads(1)` alone does not suppress the OpenMP thread pool.
- **Qdrant named vector schema** — `lore_text` uses named vectors (`"dense"` and `"sparse"`). The old `client.search(query_vector=vector)` API returns 400 Bad Request against this schema. The service uses `client.query_points()` with `FusionQuery`. After wiping and re-ingesting, if the api container was not rebuilt it will use the old code and fail silently — rebuild with `docker compose build api`.
- **Scraper checkpoint at `/data/checkpoints/`** — the scraper checkpoint lives at `/data/checkpoints/scraper_state.json`. The ingestor checkpoints live at `/data/state/`. These are different directories. Wiping only `data/state/` leaves scraper progress intact; wiping only `data/checkpoints/` forces a full re-scrape.
- **CLIP service is slow to start** — model load takes 2–3 min. Wait for `health: healthy` in `docker ps` before running the ingestor, otherwise image embedding will fail with connection refused. With the base image, the weights are pre-baked and startup is near-instant.
- **Qdrant Docker image has no wget or curl** — the healthcheck uses `bash -c 'exec 3<>/dev/tcp/127.0.0.1/6333'` instead of a HTTP check.
- **api pip resolver times out with loose version bounds** — `langgraph>=0.2` style specs cause `ResolutionTooDeep` after 20 min in pip 24.x. All langchain/langgraph deps are pinned to exact versions in `runtime/api/requirements.txt`.
- **clip-service Debian package rename** — `libgl1-mesa-glx` was renamed to `libgl1` and `libglib2.0-0` to `libglib2.0-0t64` in Debian Trixie (the base used by `python:3.11-slim`).
- **torch<2.6.0 not available for Python 3.13** — the clip-service requirements use `torch>=2.6.0`.
- **llama3-70b-8192 decommissioned by Groq** — use `llama-3.3-70b-versatile` (set in `.env` as `GROQ_MODEL`).
- **VITE_API_URL must use Docker service name** — inside Docker, `localhost` in the frontend container refers to itself, not the API. `docker-compose.yml` sets `VITE_API_URL=http://api:8000` so the Vite proxy reaches the API container.
- **Ingestor checkpoint out of sync** — checkpoints live at `data/state/`. If a Qdrant or Neo4j volume is wiped after a run, the checkpoint will say "done" but the database is empty. Delete the relevant checkpoint file (`graph_loader.json`, `text_embedder.json`, or `image_embedder.json`) and re-run the ingestor.
- **Scraper tags were empty on first run** — the `api.php?action=parse` response doesn't include the page header HTML where category links live. Fixed by adding `prop=categories` to the API call. Existing scraped files from before this fix have empty `tags: []` in their frontmatter.
- **Empty body sections are not a parser bug** — many wiki articles have stub sections (e.g. `## History` with no content). The parser correctly produces empty sections for these.
- **Category count mismatch is expected** — weapons (39), viruses (94), games (105) are just small categories on the wiki. The `MAX_PAGES` cap only hits the large categories.
- **Neo4j password must match across both `.env` and `pipeline/.env`** — if Neo4j was previously initialized with a different password, wipe the volume: `docker volume rm re-lore-rag-system-_neo4j_data` or reset via cypher-shell.
- **Some characters land in `enemies/` not `characters/`** — the Fandom BFS can discover a character through the "Creatures" category first (e.g. Jill Valentine as RE5 boss). The entity_id will be `enemy-jill-valentine` with `entity_type: enemy`. The image retrieval entity_id prefix filter (`character-*`, `enemy-*`) handles both, so images are still found correctly.
