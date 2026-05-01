# RE Lore Oracle

A locally hosted, Dockerized lore exploration system for the Resident Evil franchise. Scrapes wiki data offline, stores structured entity relationships in Neo4j and vector embeddings in Qdrant, and serves queries through a LangGraph-orchestrated RAG pipeline exposed via FastAPI. The frontend is React + TypeScript + Tailwind with a Cytoscape knowledge graph panel, streaming chat, and concept art gallery.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Cytoscape.js |
| Backend API | FastAPI |
| RAG Orchestrator | LangGraph |
| LLM | Groq API (`llama-3.3-70b-versatile`) via langchain-groq |
| Graph DB | Neo4j 5 + APOC |
| Vector DB | Qdrant |
| Image Embeddings | OpenCLIP `ViT-B-32` (isolated CLIP service) |
| Text Embeddings | `all-MiniLM-L6-v2` via sentence-transformers |
| Scraper | Python + httpx + BeautifulSoup |
| Containerization | Docker Compose |

## Quick Start

### Prerequisites

- Docker and Docker Compose v2
- A [Groq API key](https://console.groq.com/)

### 1. Configure environment

```bash
cp .env.example .env
# Set GROQ_API_KEY and NEO4J_PASSWORD
```

### 2. Start the runtime services

```bash
bash scripts/runtime-up.sh
```

### 3. Run the data pipeline (first time only)

Scrapes and ingests the RE wiki corpus into Neo4j and Qdrant. Runtime services must be running first.

```bash
cp pipeline/.env.example pipeline/.env
# Set NEO4J_PASSWORD (same as .env), leave URLs pointing at localhost
bash scripts/pipeline-run.sh
```

### 4. Open the app

[http://localhost:3000](http://localhost:3000)

---

## Repository Structure

```
re-lore-oracle/
├── docker-compose.yml          # Runtime: neo4j, qdrant, clip-service, api, frontend
├── pipeline/
│   ├── docker-compose.yml      # Offline pipeline: scraper, ingestor
│   ├── scraper/                # Async wiki scraper → markdown corpus + images
│   └── ingestor/               # Markdown → Neo4j graph + Qdrant vector collections
├── runtime/
│   ├── api/                    # FastAPI + LangGraph RAG pipeline
│   ├── clip-service/           # Isolated OpenCLIP embedding microservice
│   └── frontend/               # React + Vite + Tailwind chat UI
├── data/
│   ├── raw/                    # Scraped markdown + images (gitignored)
│   └── processed/              # Chunked data (gitignored)
├── docs/                       # Architecture and API contract
└── scripts/                    # Shell helpers
```

---

## LangGraph Pipeline

Every query runs through a typed `StateGraph`:

```
START → classify_query → graph_retrieval → vector_retrieval
          ↓ (needs_image_search=True)  → image_retrieval → assemble_evidence → generate_answer → END
          ↓ (needs_image_search=False) ────────────────→ assemble_evidence → generate_answer → END
```

- **`classify_query`** — extracts entity hints (capitalised words) and sets `needs_image_search` via keyword match
- **`graph_retrieval`** — APOC 2-hop Cypher traversal on Neo4j using entity hints
- **`vector_retrieval`** — embeds query with sentence-transformers, searches `lore_text` collection (top-5)
- **`image_retrieval`** — CLIP text embed → filtered `concept_art` search, restricted to entities already found by vector retrieval (prevents wrong-character images)
- **`assemble_evidence`** — merges results, deduplicates by (entity_id, section), filters sparse sections, includes image captions
- **`generate_answer`** — streams tokens via ChatGroq SSE

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/runtime-up.sh` | Build and start all runtime services |
| `scripts/pipeline-run.sh` | Run scraper then ingestor |
| `scripts/reset-db.sh` | Wipe Neo4j and Qdrant volumes |
| `scripts/dev-up.sh` | Pipeline + runtime in one command |
| `scripts/export-snapshots.sh` | Export Neo4j dump and Qdrant snapshot |

---

## Demo Queries

**Triggers image search (concept art shown):**
- *"What does Jill Valentine look like across different games?"*
- *"Show me concept art of Nemesis"*
- *"Show me images of Ada Wong"*

**Text-only lore:**
- *"Who is connected to Umbrella through direct employment and outbreak events?"*
- *"Which games connect Leon S. Kennedy and Ada Wong?"*
- *"What enemies are related to Tyrant lineage?"*

---

## Development

See [docs/architecture.md](docs/architecture.md) and [docs/api-contract.md](docs/api-contract.md).

Branch strategy: feature branches → `develop` → `main` via PR.

### Environment notes

- **GROQ_MODEL** — `llama-3.3-70b-versatile` (llama3-70b-8192 was decommissioned by Groq)
- **Two `.env` files** — `.env` for runtime, `pipeline/.env` for pipeline (both need the same `NEO4J_PASSWORD`)
- **Pipeline uses `network_mode: host`** — so it can reach runtime services on `localhost`; does not share a Docker network with the runtime stack
- **Ingestor checkpoints** live at `data/state/`. If a database volume is wiped, delete the relevant checkpoint file and re-run the ingestor to re-populate.
