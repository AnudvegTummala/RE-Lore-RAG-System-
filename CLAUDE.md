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
bash scripts/runtime-up.sh     # build and start all runtime services
bash scripts/pipeline-run.sh   # run scraper then ingestor (first-time data load)
bash scripts/reset-db.sh       # wipe Neo4j and Qdrant volumes
docker compose logs -f api     # tail a specific service
docker compose build api       # rebuild one service
```

**Two separate env files are required:**
- `.env` — runtime (copy from `.env.example`, set `GROQ_API_KEY` and `NEO4J_PASSWORD`)
- `pipeline/.env` — pipeline (copy from `pipeline/.env.example`, same password, point URLs at localhost)

---

## Architecture

### LangGraph Query Pipeline

Every user query runs through a LangGraph `StateGraph` compiled at import time in `runtime/api/app/graph/workflow.py`. All nodes share a single typed state object (`GraphState` in `graph/state.py`).

```
START → classify_query → graph_retrieval → vector_retrieval
                                               ↓ needs_image_search=True  → image_retrieval → assemble_evidence
                                               ↓ needs_image_search=False ──────────────────→ assemble_evidence
                                                                                                    → generate_answer → END
```

**Key detail:** `compiled_graph` is a module-level singleton created at import. Adding or renaming nodes requires editing `build_graph()` in `workflow.py` and restarting the server.

**Node responsibilities:**
| Node | File | What it does |
|---|---|---|
| `classify_query` | `nodes/classify.py` | Regex entity extraction + sets `needs_image_search` flag |
| `graph_retrieval` | `nodes/graph_retrieval.py` | Cypher 2-hop traversal on Neo4j using entity hints |
| `vector_retrieval` | `nodes/vector_retrieval.py` | sentence-transformers embed → Qdrant `lore_text` top-5 |
| `image_retrieval` | `nodes/image_retrieval.py` | CLIP embed via clip-service → Qdrant `concept_art` top-3 |
| `assemble_evidence` | `nodes/assemble.py` | Merge + deduplicate all results → `evidence` string |
| `generate_answer` | `nodes/generate.py` | ChatGroq with `streaming=True` → `answer` |

`classify_query` uses a **regex heuristic** (capitalized words for entities, keyword list for visual terms) — not spaCy. The `needs_image_search` flag is the only conditional edge in the graph.

### SSE Streaming

`POST /query` (in `routers/query.py`) calls `compiled_graph.astream_events(initial_state, version="v2")` and filters two event types:
- `on_chat_model_stream` → streams `{"token": "..."}` events immediately
- `on_chain_end` where `name == "LangGraph"` → emits the final `{"done": true, "answer": ..., "sources": ..., "images": ..., "graph": ...}` event

The frontend's `useStreaming` hook (`src/hooks/useStreaming.ts`) drives all chat state. It appends tokens by calling `updateLastMessage` which replaces the last entry in the Zustand messages array. The `assistantMsg.content` local variable is kept in sync with the store for the token accumulation pattern to work correctly.

### Services (runtime/api)

All services are module-level singletons:
- `neo4j_service` (`services/neo4j_service.py`) — lazy `AsyncDriver` init
- `qdrant_service` (`services/qdrant_service.py`) — lazy `AsyncQdrantClient` + `SentenceTransformer` init
- `clip_client` (`services/clip_service_client.py`) — stateless HTTP client to the CLIP microservice
- `get_llm()` (`services/llm.py`) — `@lru_cache` returning a single `ChatGroq` instance

Config is loaded from `.env` via `pydantic-settings` into `core/config.py`'s `settings` singleton.

### Frontend State

Zustand store in `src/store/appStore.ts` is the single source of truth: `messages[]`, `isStreaming`, `activeGraph`, `selectedNode`. Components read from it via `useChat` / `useGraph` hooks.

Vite proxies all `/api/*` requests to the FastAPI server (stripping the `/api` prefix), configured in `vite.config.ts`.

### Data Pipeline (offline, run before runtime)

Two separate services, run once to build the corpus:

1. **Scraper** (`pipeline/scraper/`) — `BaseScraper` with rate limiting and checkpoint support. Outputs markdown files to `data/raw/markdown/{category}/` and images to `data/raw/images/`. Each markdown file has YAML frontmatter with `id`, `entity_type`, `related_games`, `image_refs`, `tags`.

2. **Ingestor** (`pipeline/ingestor/`) — reads markdown, chunks by heading (max 800 chars, `utils/chunker.py`), creates Neo4j nodes + `APPEARS_IN` relationships, embeds text chunks into Qdrant `lore_text` (dim=384, `all-MiniLM-L6-v2`), embeds images into Qdrant `concept_art` (dim=512, CLIP `ViT-B-32`).

The pipeline has its **own `docker-compose.yml`** in `pipeline/` and runs offline — it does not share a Docker network with the runtime stack. Point `pipeline/.env` at the runtime services' host ports before running.

### Neo4j Schema

Constraints enforced at startup (`pipeline/ingestor/app/graph/schema.py`): `id` is unique per label (`Character`, `Game`, `Enemy`, `Virus`, `Organization`, `Location`, `ConceptArt`, `LoreChunk`, `TimelineEvent`). Graph retrieval uses APOC `subgraphAll` for 2-hop traversal — the Neo4j container loads APOC via the `NEO4J_PLUGINS` env var in `docker-compose.yml`.

### Qdrant Collections

| Collection | Model | Dimensions | Populated by |
|---|---|---|---|
| `lore_text` | all-MiniLM-L6-v2 | 384 | `pipeline/ingestor/app/embeddings/text_embedder.py` |
| `concept_art` | CLIP ViT-B-32 | 512 | `pipeline/ingestor/app/embeddings/image_embedder.py` |

Collections are created idempotently by the ingestor before upserting. The CLIP service (`runtime/clip-service/`) is the only component that runs the OpenCLIP model — both the ingestor and the API's `image_retrieval` node call it over HTTP.
