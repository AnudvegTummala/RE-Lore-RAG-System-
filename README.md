# RE Lore Oracle

A locally hosted, Dockerized lore exploration system for the Resident Evil franchise. Scrapes wiki data offline, stores structured entity relationships in Neo4j and vector embeddings in Qdrant, and answers questions through a LangGraph-orchestrated RAG pipeline exposed via FastAPI. The frontend is React + TypeScript + Tailwind with a Cytoscape knowledge graph panel, streaming chat, and concept art gallery.

## Stack

| Layer            | Technology                                                       |
| ---------------- | ---------------------------------------------------------------- |
| Frontend         | React 18 + TypeScript + Vite + Tailwind CSS + Cytoscape.js       |
| Backend API      | FastAPI                                                          |
| RAG Orchestrator | LangGraph                                                        |
| LLM              | Groq API (`llama-3.3-70b-versatile`) via langchain-groq          |
| Graph DB         | Neo4j 5 + APOC                                                   |
| Vector DB        | Qdrant (hybrid dense + BM25 sparse)                              |
| Text Embeddings  | `all-MiniLM-L6-v2` via sentence-transformers                     |
| Reranker         | `cross-encoder/ms-marco-MiniLM-L-6-v2` via sentence-transformers |
| Image Embeddings | OpenCLIP `ViT-B-32` (isolated CLIP service)                      |
| Scraper          | Python + httpx + BeautifulSoup                                   |
| Containerization | Docker Compose                                                   |

## Prerequisites

- Docker and Docker Compose v2
- A [Groq API key](https://console.groq.com/)

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Set GROQ_API_KEY and NEO4J_PASSWORD

cp pipeline/.env.example pipeline/.env
# Set NEO4J_PASSWORD (same value), leave URLs pointing at localhost
```

> **TORCH_DEVICE** in `.env` controls which PyTorch variant is used: `auto` detects a GPU via `nvidia-smi` and falls back to CPU. Override to `cpu` or `cuda` if auto-detection does not work for your setup. On Mac with Docker Desktop, `auto` always resolves to `cpu` because MPS is not available inside Linux containers.

### 2. Build the shared base image

The `api` and `clip-service` containers inherit from a shared base image that bundles PyTorch, sentence-transformers, OpenCLIP, and fastembed. This must be built once before the runtime stack:

```bash
bash scripts/build-base.sh
```

### 3. Start the runtime services

```bash
docker compose up -d
```

Wait until `docker ps` shows `clip-service` as `healthy` (model load takes 3–6 minutes).

### 4. Run the data pipeline (first time only)

Scrapes the RE wiki and ingests the corpus into Neo4j and Qdrant. Runtime services must be running first.

```bash
bash scripts/pipeline-run.sh
```

### 5. Open the app

[http://localhost:3000](http://localhost:3000)

---

## Repository Structure

```
re-lore-oracle/
├── docker-compose.yml          # Runtime: neo4j, qdrant, clip-service, api, frontend
├── pipeline/
│   ├── docker-compose.yml      # Offline pipeline: scraper, ingestor
│   ├── .env.example
│   ├── scraper/                # Async wiki scraper → markdown corpus + images
│   └── ingestor/               # Markdown → Neo4j graph + Qdrant vector collections
├── runtime/
│   ├── base/                   # Shared base Docker image (torch + heavy deps)
│   ├── api/                    # FastAPI + LangGraph RAG pipeline
│   ├── clip-service/           # Isolated OpenCLIP embedding microservice
│   └── frontend/               # React + Vite + Tailwind chat UI
├── data/
│   ├── raw/                    # Scraped markdown + images + manifests (gitignored)
│   ├── state/                  # Ingestor checkpoints (gitignored)
│   └── logs/                   # Runtime log files (gitignored)
├── docs/                       # Architecture, data model, API contract, development guide
└── scripts/                    # Shell helpers
```

---

## LangGraph Pipeline

Every query runs through a typed `StateGraph`. Graph retrieval and vector retrieval run in parallel; the reranker merges their candidates:

```
START → classify_query ──┬──► graph_retrieval ──┐
                         └──► vector_retrieval ──┴──► rerank
                                                          │
                                   needs_image_search=True├──► image_retrieval ──► assemble_evidence
                                   needs_image_search=False└──► (skip)  ─────────► assemble_evidence
                                                                                          │
                                                                                   generate_answer → END
```

- **`classify_query`** — regex entity extraction (title-case, ALL-CAPS, dotted, hyphenated patterns + known aliases); sets `needs_image_search`
- **`graph_retrieval`** — APOC 2-hop Cypher traversal on Neo4j using entity hints
- **`vector_retrieval`** — hybrid BM25 + dense search on Qdrant `lore_text`, top-15 candidates
- **`rerank`** — cross-encoder scores all candidates, applies 0.3 threshold, keeps top-3
- **`image_retrieval`** — CLIP text embed → filtered `concept_art` search, restricted to entity_ids from text results
- **`assemble_evidence`** — merges results, deduplicates by (entity_id, section), filters sparse sections
- **`generate_answer`** — streams tokens via ChatGroq SSE

---

## Scripts

| Script                                    | Purpose                                           |
| ----------------------------------------- | ------------------------------------------------- |
| `scripts/build-base.sh [cpu\|cuda\|auto]` | Build the shared `re-lore-base` Docker image      |
| `scripts/push-base.sh`                    | Push `re-lore-base` to GHCR for teammates to pull |
| `scripts/runtime-up.sh`                   | Build and start all runtime services              |
| `scripts/pipeline-run.sh`                 | Run scraper then ingestor                         |
| `scripts/reset-db.sh`                     | Wipe Neo4j and Qdrant volumes                     |
| `scripts/dev-up.sh`                       | Pipeline + runtime in one command                 |
| `scripts/export-snapshots.sh`             | Export Neo4j dump and Qdrant snapshot             |

---

## Demo Queries

**Triggers image search (concept art shown):**

- _"What does Jill Valentine look like across different games?"_
- _"Show me concept art of Nemesis"_
- _"Show me images of Ada Wong"_

**Text-only lore:**

- _"Who is connected to Umbrella through direct employment and outbreak events?"_
- _"Which games connect Leon S. Kennedy and Ada Wong?"_
- _"What enemies are related to Tyrant lineage?"_

---

## Development

See [docs/architecture.md](docs/architecture.md) for system design and technology rationale, [docs/development.md](docs/development.md) for commands and contributor workflow, and [docs/api-contract.md](docs/api-contract.md) for the API specification.

Branch strategy: feature branches → `develop` → `main` via PR.

---

## Docker Storage Note

Docker Desktop stores all image layers in a virtual disk file that grows on every build but never shrinks automatically. After repeated rebuilds this can fill your disk. See [docs/docker-storage-and-builds.md](docs/docker-storage-and-builds.md) for the fix and routine habits to prevent unbounded growth.
