# Resident Evil Lore Oracle — Claude Code Implementation Plan

## Project Summary

Resident Evil Lore Oracle is a locally hosted, Dockerized lore exploration system for the Resident Evil franchise. It scrapes wiki data offline, stores structured entity relationships in Neo4j and vector embeddings in Qdrant, and serves queries through a LangGraph-orchestrated RAG pipeline exposed via FastAPI. The frontend is React + TypeScript + Tailwind with a Cytoscape graph panel and streaming chat interface.

**The retrieval pipeline is graph-orchestrated using LangGraph.** Every query runs through a stateful StateGraph where each retrieval step is an isolated node, routing is conditional, and all nodes share a typed state object.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite + Tailwind CSS |
| Graph Visualization | Cytoscape.js |
| Backend API | FastAPI |
| RAG Orchestrator | LangGraph |
| LLM Integration | LangChain-Groq (langchain-groq) |
| LLM Provider | Groq API (llama3-70b-8192) |
| Graph Database | Neo4j |
| Vector Database | Qdrant |
| Image Embeddings | OpenCLIP (CLIP service) |
| Scraper | Python + httpx + BeautifulSoup |
| Containerization | Docker Compose |

---

## Repository Structure

```
re-lore-oracle/
├── .github/
│   ├── pull_request_template.md
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── .env.example
├── README.md
├── docker-compose.yml
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── api-contract.md
│   └── demo-script.md
├── runtime/
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── core/
│   │       │   ├── config.py
│   │       │   ├── logging.py
│   │       │   └── middleware.py
│   │       ├── graph/
│   │       │   ├── __init__.py
│   │       │   ├── state.py
│   │       │   ├── workflow.py
│   │       │   └── nodes/
│   │       │       ├── classify.py
│   │       │       ├── graph_retrieval.py
│   │       │       ├── vector_retrieval.py
│   │       │       ├── image_retrieval.py
│   │       │       ├── assemble.py
│   │       │       └── generate.py
│   │       ├── routers/
│   │       │   ├── health.py
│   │       │   ├── query.py
│   │       │   ├── graph.py
│   │       │   └── search.py
│   │       ├── services/
│   │       │   ├── llm.py
│   │       │   ├── neo4j_service.py
│   │       │   ├── qdrant_service.py
│   │       │   ├── clip_service_client.py
│   │       │   └── prompt_builder.py
│   │       ├── schemas/
│   │       │   ├── query.py
│   │       │   ├── graph.py
│   │       │   └── source.py
│   │       └── utils/
│   │           ├── citations.py
│   │           └── chunking.py
│   ├── clip-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py
│   └── frontend/
│       ├── Dockerfile
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.ts
│       ├── tsconfig.json
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           ├── api/
│           │   └── client.ts
│           ├── components/
│           │   ├── layout/
│           │   │   ├── Header.tsx
│           │   │   ├── Sidebar.tsx
│           │   │   └── Shell.tsx
│           │   ├── chat/
│           │   │   ├── ChatInput.tsx
│           │   │   ├── ChatMessage.tsx
│           │   │   ├── ChatWindow.tsx
│           │   │   └── SourcePanel.tsx
│           │   ├── graph/
│           │   │   ├── GraphViewer.tsx
│           │   │   ├── NodeDetails.tsx
│           │   │   └── GraphLegend.tsx
│           │   └── media/
│           │       ├── ImageGallery.tsx
│           │       └── ImageCard.tsx
│           ├── hooks/
│           │   ├── useChat.ts
│           │   ├── useGraph.ts
│           │   └── useStreaming.ts
│           ├── store/
│           │   └── appStore.ts
│           └── types/
│               └── index.ts
├── pipeline/
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── scraper/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── scrapers/
│   │       │   ├── base.py
│   │       │   ├── fandom.py
│   │       │   ├── wikipedia.py
│   │       │   └── images.py
│   │       ├── parsers/
│   │       │   ├── character_parser.py
│   │       │   ├── game_parser.py
│   │       │   ├── enemy_parser.py
│   │       │   └── location_parser.py
│   │       └── utils/
│   │           ├── checkpoint.py
│   │           ├── cleaner.py
│   │           ├── markdown_writer.py
│   │           └── rate_limit.py
│   └── ingestor/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── main.py
│           ├── graph/
│           │   ├── schema.py
│           │   ├── loader.py
│           │   ├── entity_extractor.py
│           │   └── relationship_builder.py
│           ├── embeddings/
│           │   ├── image_embedder.py
│           │   └── text_embedder.py
│           ├── qdrant/
│           │   └── collections.py
│           └── utils/
│               ├── markdown_loader.py
│               ├── frontmatter.py
│               └── chunker.py
├── data/
│   ├── raw/
│   │   ├── markdown/
│   │   │   ├── characters/
│   │   │   ├── games/
│   │   │   ├── enemies/
│   │   │   ├── locations/
│   │   │   ├── organizations/
│   │   │   └── timeline/
│   │   ├── images/
│   │   │   ├── characters/
│   │   │   ├── enemies/
│   │   │   ├── locations/
│   │   │   └── concept-art/
│   │   └── manifests/
│   │       ├── scrape_manifest.json
│   │       ├── image_manifest.json
│   │       └── source_registry.json
│   ├── processed/
│   │   ├── chunks/
│   │   ├── entities/
│   │   ├── relationships/
│   │   └── embeddings/
│   └── checkpoints/
│       ├── scraper_state.json
│       └── ingest_state.json
└── scripts/
    ├── dev-up.sh
    ├── pipeline-run.sh
    ├── runtime-up.sh
    ├── reset-db.sh
    └── export-snapshots.sh
```

---

## LangGraph Architecture

### How It Works

Every user query runs through a LangGraph `StateGraph`. Instead of one function calling everything in sequence, the pipeline is a set of named nodes connected by edges. Edges can be conditional — the graph decides at runtime which node to run next based on what previous nodes found.

All nodes share a single typed state object. Any node can read anything any previous node wrote.

### GraphState

Defined in `runtime/api/app/graph/state.py`:

```python
from typing import TypedDict

class GraphState(TypedDict):
    query: str                    # raw user question
    entity_hints: list[str]       # entity names extracted from query
    needs_image_search: bool      # routing flag — set by classify node
    graph_results: list[dict]     # subgraph data from Neo4j
    text_results: list[dict]      # matching lore chunks from Qdrant
    image_results: list[dict]     # matching concept art from Qdrant+CLIP
    evidence: str                 # assembled context string for the LLM
    answer: str                   # final generated answer
    retrieval_adequate: bool      # optional grounding check flag
```

### Nodes

| Node | File | Reads | Writes | Description |
|---|---|---|---|---|
| `classify_query` | `nodes/classify.py` | `query` | `entity_hints`, `needs_image_search` | Extracts entity names from the query. Sets `needs_image_search=True` if the query references visual content (concept art, appearances, design, looks like). |
| `graph_retrieval` | `nodes/graph_retrieval.py` | `entity_hints` | `graph_results` | Runs a Cypher traversal on Neo4j using entity hints. Returns matching nodes and edges up to 2 hops. |
| `vector_retrieval` | `nodes/vector_retrieval.py` | `query` | `text_results` | Embeds the query with sentence-transformers. Searches the `lore_text` Qdrant collection, top-5. |
| `image_retrieval` | `nodes/image_retrieval.py` | `query` | `image_results` | Calls the CLIP service to embed the query. Searches the `concept_art` Qdrant collection, top-3. Only runs when `needs_image_search=True`. |
| `assemble_evidence` | `nodes/assemble.py` | `graph_results`, `text_results`, `image_results` | `evidence` | Merges and deduplicates all retrieved results. Formats them into a single context string for the LLM prompt. |
| `generate_answer` | `nodes/generate.py` | `query`, `evidence` | `answer`, `retrieval_adequate` | Sends evidence + query to Groq via `ChatGroq`. Streams the response. |

### Graph Wiring

Defined in `runtime/api/app/graph/workflow.py`:

```
START
  └─► classify_query
        └─► graph_retrieval
              └─► vector_retrieval
                    ├─► [needs_image_search=True]  ──► image_retrieval ──► assemble_evidence
                    └─► [needs_image_search=False] ──────────────────────► assemble_evidence
                                                                                └─► generate_answer
                                                                                      └─► END
```

### Conditional Edges

**After `vector_retrieval`:** Router checks `state["needs_image_search"]`. Routes to `image_retrieval` if True, directly to `assemble_evidence` if False. This skips CLIP embedding for text-only lore queries.

**After `generate_answer` (optional):** Router checks `state["retrieval_adequate"]`. If False, routes back to `graph_retrieval` with a broadened traversal for a retry. Implement this loop in Phase 2 polish if time allows.

### Streaming

The FastAPI `/query` router calls `compiled_graph.astream_events(initial_state, version="v2")`. It filters for `on_chat_model_stream` events from the `generate_answer` node and pipes each token to the frontend as a Server-Sent Event. The frontend `useStreaming` hook appends tokens to the displayed answer in real time.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check for all services |
| `POST` | `/query` | Main endpoint — invokes LangGraph, streams response via SSE |
| `GET` | `/graph/{entity_id}` | Returns subgraph for a specific entity |
| `GET` | `/search?q=` | Lightweight keyword search for entity lookup |
| `GET` | `/entity/{entity_id}` | Returns full entity details |

### Query Response Shape

```json
{
  "answer": "...",
  "sources": [
    {
      "entity_id": "character-leon-s-kennedy",
      "title": "Leon S. Kennedy",
      "section": "Biography",
      "snippet": "...",
      "source_url": "..."
    }
  ],
  "images": [
    {
      "image_id": "leon-concept-02",
      "path": "/assets/leon-concept-02.jpg",
      "caption": "Early concept art"
    }
  ],
  "graph": {
    "nodes": [],
    "edges": []
  }
}
```

---

## Knowledge Graph Schema

### Entity Types

- `Character`
- `Game`
- `Enemy`
- `Virus`
- `Organization`
- `Location`
- `ConceptArt`
- `LoreChunk`
- `TimelineEvent`

### Relationships

- `APPEARS_IN` — Character/Enemy → Game
- `MEMBER_OF` — Character → Organization
- `ENCOUNTERS` — Character → Enemy
- `INFECTED_WITH` — Character/Enemy → Virus
- `CREATED_BY` — Virus/Enemy → Organization
- `LOCATED_IN` — Event/Game → Location
- `FEATURED_IN` — Location → Game
- `HAS_CONCEPT_ART` — Character/Enemy → ConceptArt
- `DESCRIBED_IN` — Character/Enemy/Location → LoreChunk
- `PRECEDES` / `SUCCEEDS` — TimelineEvent → TimelineEvent

---

## Vector Collections (Qdrant)

### `lore_text`

Sentence-transformer embeddings of markdown chunks using a **parent-child hierarchical strategy with contextual prefixing**:

- **Child chunks** (≤ 400 chars) are what gets embedded and indexed in Qdrant — small enough for precise retrieval.
- **Parent chunks** (full section, ≤ 1500 chars) are stored in the Qdrant payload alongside the child — this is what gets sent to the LLM as context.
- Every chunk is prefixed with `"{title} — {section_name}: "` before embedding so vectors carry entity context even when the chunk is read in isolation (contextual retrieval).

Payload fields: `entity_id`, `entity_type`, `source_file`, `source_url`, `section`, `tags`, `chunk_text` (child, embedded), `parent_text` (full section, returned to LLM)

### `concept_art`

CLIP embeddings of images sourced from `image_manifest.json` (only entries with a `local_path`).

Payload fields: `image_id`, `entity_id`, `entity_type`, `image_path`, `caption` (alt_text from manifest), `tags`

Both `lore_text` and `concept_art` have a Qdrant payload index on `entity_id` (keyword type) for efficient filtered search during graph-anchored retrieval.

---

## Markdown Corpus Format

Each scraped entity page becomes one markdown file:

```md
---
id: character-leon-s-kennedy
entity_type: character
title: Leon S. Kennedy
source_name: Resident Evil Wiki
source_url: https://example.com/leon
franchise: Resident Evil
related_games:
  - resident-evil-2
  - resident-evil-4
scraped_at: 2026-04-27T00:00:00Z
tags:
  - protagonist
  - rpd
  - government-agent
image_refs:
  - leon-main-01
  - leon-concept-02
---

# Leon S. Kennedy

## Summary
...

## Biography
...
```

### Folder Layout

```
data/raw/markdown/
├── characters/
├── games/
├── enemies/
├── locations/
├── organizations/
└── timeline/
```

### Chunk Metadata

Parent-child chunking with contextual prefixing. Each Qdrant point represents one child chunk:

```json
{
  "chunk_id": "leon-s-kennedy_biography_001",
  "entity_id": "character-leon-s-kennedy",
  "entity_type": "character",
  "section": "Biography",
  "source_file": "data/raw/markdown/characters/leon-s-kennedy.md",
  "source_url": "https://example.com/leon",
  "tags": ["protagonist", "rpd"],
  "chunk_text": "Leon S. Kennedy — Biography: Leon was recruited by...",
  "parent_text": "Leon S. Kennedy — Biography: Leon was recruited by the RPD after graduating... [full section up to 1500 chars]"
}
```

The vector stored in Qdrant is the embedding of `chunk_text` (child, ≤ 400 chars with prefix). The `parent_text` field is retrieved at query time and passed to the LLM — giving precise retrieval with full-context generation.

---

## Docker Compose Services

### Runtime (`docker-compose.yml`)

- `neo4j` — graph database, port 7474/7687, named volume `neo4j_data`
- `qdrant` — vector database, port 6333, named volume `qdrant_data`
- `clip-service` — OpenCLIP inference service, port 8001
- `api` — FastAPI + LangGraph, port 8000
- `frontend` — React Vite app, port 3000

### Pipeline (`pipeline/docker-compose.yml`)

- `scraper` — offline scraper, bind mount to `data/`
- `ingestor` — offline ingestor, bind mount to `data/`

### Volumes

- `neo4j_data` — persists graph between restarts
- `qdrant_data` — persists vector collections between restarts
- `./data` — bind mount shared between pipeline and runtime containers

---

## Python Dependencies (runtime/api/requirements.txt)

```
fastapi
uvicorn[standard]
langgraph>=0.2
langchain-core>=0.2
langchain-groq>=0.1
langchain-community>=0.2
neo4j
qdrant-client
sentence-transformers
httpx
pydantic
python-dotenv
```

---

## Implementation Phases

### Phase 1 — Repo Bootstrap (Dev 1)

- Create GitHub repository and directory structure
- Write root `docker-compose.yml` with all runtime services
- Write `pipeline/docker-compose.yml` with scraper and ingestor
- Define named volumes for Neo4j and Qdrant
- Add `.env.example`, `.gitignore`, `README.md`, PR template
- Add `scripts/` for dev-up, runtime-up, reset-db

Deliverable: Clean repo scaffold with working container skeleton.

### Phase 2 — Scraper Pipeline (Dev 2)

- Build async scraper base class with global `Semaphore(5)`, per-domain rate limiter (1.5–3.0 s gap), exponential backoff on 429/403/503; user-agent is a full Chrome UA string to pass Cloudflare checks
- URL discovery via MediaWiki API (`api.php?list=categorymembers`) with BFS subcategory traversal (depth ≤ 5) — avoids Cloudflare-blocked category HTML pages; category names corrected to match live wiki (`Creatures`, `Organisations`, `Biological_agents`, `Equipment`)
- Implement Resident Evil wiki (Fandom) scraper with shared `ImageManifest`, `SourceRegistry`, `ScrapeManifest`
- Implement Wikipedia supplementary scraper (appends `## Wikipedia Summary` to game files)
- Implement image downloader with Pillow dimension validation (skip < 100×100)
- Normalize page titles into slugs; convert page content to markdown with YAML frontmatter
- Atomic checkpoint writes (`.tmp` rename); auto-flush every 10 completions
- Scraper container uses `network_mode: host` so Cloudflare sees residential IP over HTTP/2

Deliverable: `data/raw/markdown/` corpus and `data/raw/images/` image corpus.

### Phase 3 — Ingestor Pipeline (Dev 2)

- Implement markdown loader and frontmatter parser
- Build hierarchical chunker: split by heading into parent sections (≤ 1500 chars), sub-split into child chunks (≤ 400 chars) by sentence boundary; prefix every chunk with `"{title} — {section}: "` for contextual retrieval
- Define Neo4j schema, constraints, and indexes (one index per node label)
- Build graph node loader (pass 1) and relationship builder (pass 2); relationship builder is lenient — creates stub nodes for referenced entities not yet in the graph so future scrape runs can fill them in
- Generate text embeddings with `all-MiniLM-L6-v2` (dim=384); store child chunk as the embedded vector, parent section text in payload; run model in thread executor to avoid blocking the event loop
- Generate CLIP image embeddings via HTTP calls to clip-service (dim=512); skip images without a `local_path` in image_manifest
- All steps idempotent via checkpoint; produce summary log at completion

Deliverable: Populated Neo4j and Qdrant volumes ready for runtime.

### Phase 4 — CLIP Service (Dev 1)

- Create isolated FastAPI service that loads OpenCLIP model at startup
- Expose `POST /embed/text` endpoint — returns vector from text string
- Expose `POST /embed/image` endpoint — returns vector from image bytes
- Add `GET /health` endpoint
- Add batching support
- Add Dockerfile and environment config

Deliverable: Working embedding service container.

### Phase 5 — LangGraph Workflow (Dev 1)

- Define `GraphState` TypedDict in `graph/state.py`
- Implement `classify_query` node: spaCy or regex entity extraction, set `needs_image_search` flag
- Implement `graph_retrieval` node: Cypher query via `neo4j_service.py`, write `graph_results`
- Implement `vector_retrieval` node: sentence-transformer embed + Qdrant `lore_text` search, write `text_results`
- Implement `image_retrieval` node: CLIP service call + Qdrant `concept_art` search, write `image_results`
- Implement `assemble_evidence` node: merge, deduplicate, format context string, write `evidence`
- Implement `generate_answer` node: `ChatGroq` with `streaming=True`, write `answer`
- Wire all nodes in `workflow.py` using `StateGraph`
- Add conditional edge after `vector_retrieval` routing on `needs_image_search`
- Call `graph.compile()` and export as `compiled_graph`

Deliverable: Fully wired and compiled LangGraph workflow, unit tested per node.

### Phase 6 — FastAPI Backend (Dev 1)

- Scaffold FastAPI app with config, CORS middleware, structured logging
- Implement `/query` router: build `initial_state`, call `compiled_graph.astream_events()`, pipe `on_chat_model_stream` events as SSE, return full payload at completion
- Implement `/graph/{entity_id}` router using `neo4j_service.py`
- Implement `/search` and `/entity` routers using `qdrant_service.py`
- Implement `/health` router checking Neo4j, Qdrant, CLIP service
- Update `llm.py` to return a `ChatGroq` instance with `streaming=True`
- Finalize `requirements.txt` with all LangGraph packages

Deliverable: End-to-end backend with streaming LangGraph pipeline.

### Phase 7 — Frontend (Dev 2)

- Initialize React + Vite + TypeScript project
- Add Tailwind and base dark theme styling
- Build shell layout: header, sidebar, chat panel, right panel
- Build chat input with suggested demo prompts
- Build streaming answer renderer consuming SSE via `useStreaming` hook
- Build source cards panel
- Build Cytoscape graph panel with node detail drawer
- Build concept art image gallery (conditionally rendered when images present)
- Integrate API client
- Add loading and error states
- Tune for dark, Resident Evil-inspired visual theme

Deliverable: Functional integrated frontend.

### Phase 8 — Integration and Polish (Both)

- Run full pipeline on full chosen dataset
- Validate Neo4j graph contents and Qdrant retrieval quality
- Tune LangGraph node logic and evidence assembly for better answers
- Verify conditional edge: confirm image search skips on text-only queries
- Test local runtime cold start from scratch
- Add demo-safe fallback responses for empty retrieval
- Capture screenshots and architecture diagrams for `docs/`
- Clean branch history and merge all features
- Tag `v1.0-final-submission`

Deliverable: Demo-ready system, clean repository, final documentation.

---

## Development Order

1. Repo bootstrap and Docker runtime skeleton
2. Scraper on small sample set
3. Ingestor on small sample set
4. CLIP service
5. `graph/state.py` and stub node files — agree on interface before writing logic
6. `graph_retrieval` node with working Cypher query
7. `vector_retrieval` node with working Qdrant search
8. `classify_query` node and conditional edge to `image_retrieval`
9. `image_retrieval` node
10. `assemble_evidence` and `generate_answer` nodes
11. FastAPI `/query` router with SSE streaming
12. Frontend shell
13. Chat and graph integration
14. Full scrape and full ingest
15. Final polish and documentation

Step 5 should happen early. Both developers need to agree on the `GraphState` shape before any node logic is written — this prevents integration bugs when nodes are merged.

---

## Branching Strategy

- `main` — stable, demo-ready
- `develop` — integration branch
- Feature branches merged into `develop` via PR

### Feature Branches

- `feature/repo-bootstrap`
- `feature/docker-runtime`
- `feature/pipeline-scraper`
- `feature/pipeline-ingestor`
- `feature/clip-service`
- `feature/api-core`
- `feature/langgraph-state`
- `feature/langgraph-nodes`
- `feature/langgraph-streaming`
- `feature/frontend-shell`
- `feature/frontend-chat`
- `feature/frontend-graph`
- `feature/integration-polish`

### Milestone Tags

- `v0.1-repo-init`
- `v0.2-pipeline-ready`
- `v0.3-runtime-ready`
- `v0.4-langgraph-wired`
- `v0.5-end-to-end-demo`
- `v1.0-final-submission`

---

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| LangGraph streaming integration harder than expected | Medium | Prototype `astream_events()` with a 2-node graph before wiring the full workflow |
| `needs_image_search` too aggressive — skips when it shouldn't | Medium | Default to running image search during testing; tune the classifier conservatively |
| Scraper HTML structure breaks | Medium | Keep parsers modular, test on small samples first |
| Noisy scraped text | High | Markdown cleanup and frontmatter metadata filtering |
| LLM hallucination | High | Ground prompts with retrieved evidence; optionally add grounding validation node |
| Slow end-to-end runtime | Medium | Limit top-k, skip image search conditionally, stream responses |
| Data volume too large for timeline | Medium | Prioritize major entities and mainline games first |
| Frontend graph too cluttered | Medium | Return focused subgraphs, not global graph |

---

## Acceptance Criteria

- [ ] Repository is structured and documented with LangGraph architecture diagram in `docs/`
- [ ] Scraper produces markdown corpus, image corpus, and manifests
- [ ] Ingestor loads Neo4j graph and Qdrant vector collections successfully
- [ ] LangGraph workflow compiles without errors
- [ ] Each node has passing unit tests
- [ ] Runtime stack starts with one command via Docker Compose
- [ ] User can ask a lore question and receive a grounded streamed answer
- [ ] Response includes sources, graph entities, and images when applicable
- [ ] Image search is verifiably skipped for text-only queries
- [ ] Frontend is stable and presentable for live demo
- [ ] GitHub history shows branch-based collaboration

---

## Demo Questions

Use these to validate the full pipeline:

**Should trigger image search path:**
- Which concept art items relate to Nemesis, and what descriptive lore is attached to them?
- What does Jill Valentine look like across different games?
- What locations are most associated with the Raccoon City outbreak?

**Should skip image search:**
- Who is connected to Umbrella through both direct employment and outbreak events?
- Which games connect Leon S. Kennedy and Ada Wong?
- What enemies are related to Tyrant lineage?

Verify during integration that the first group sets `needs_image_search=True` and the second sets it `False`.
