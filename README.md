# RE Lore Oracle

A locally hosted, Dockerized lore exploration system for the Resident Evil franchise. Scrapes wiki data offline, stores structured entity relationships in Neo4j and vector embeddings in Qdrant, and serves queries through a LangGraph-orchestrated RAG pipeline exposed via FastAPI. The frontend is React + TypeScript + Tailwind with a Cytoscape graph panel and streaming chat interface.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Graph Visualization | Cytoscape.js |
| Backend API | FastAPI |
| RAG Orchestrator | LangGraph |
| LLM | Groq API (llama3-70b-8192) via langchain-groq |
| Graph DB | Neo4j 5 |
| Vector DB | Qdrant |
| Image Embeddings | OpenCLIP (isolated CLIP service) |
| Scraper | Python + httpx + BeautifulSoup |
| Containerization | Docker Compose |

## Quick Start

### Prerequisites

- Docker and Docker Compose v2
- A [Groq API key](https://console.groq.com/)

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set GROQ_API_KEY and NEO4J_PASSWORD
```

### 2. Run the data pipeline (first time only)

The pipeline scrapes and ingests the knowledge corpus into Neo4j and Qdrant.

```bash
cp pipeline/.env.example pipeline/.env
# Edit pipeline/.env — same NEO4J_PASSWORD, point URLs at localhost
bash scripts/pipeline-run.sh
```

### 3. Start the runtime

```bash
bash scripts/runtime-up.sh
```

Open [http://localhost:3000](http://localhost:3000).

### Dev shortcut (pipeline + runtime together)

```bash
bash scripts/dev-up.sh
```

## Repository Structure

```
re-lore-oracle/
├── docker-compose.yml          # Runtime services: neo4j, qdrant, clip-service, api, frontend
├── pipeline/
│   ├── docker-compose.yml      # Offline pipeline: scraper, ingestor
│   ├── scraper/                # Async wiki scraper → markdown corpus
│   └── ingestor/               # Markdown → Neo4j graph + Qdrant vectors
├── runtime/
│   ├── api/                    # FastAPI + LangGraph orchestration
│   ├── clip-service/           # Isolated OpenCLIP embedding service
│   └── frontend/               # React + Vite + Tailwind UI
├── data/
│   ├── raw/                    # Scraped markdown corpus and images (gitignored)
│   └── processed/              # Chunked text and embedding files (gitignored)
├── docs/                       # Architecture diagrams and API contract
└── scripts/                    # Helper shell scripts
```

## LangGraph Pipeline

Every query runs through a typed `StateGraph`:

```
START → classify_query → graph_retrieval → vector_retrieval
          ↓ (needs_image_search=True)  → image_retrieval → assemble_evidence → generate_answer → END
          ↓ (needs_image_search=False) ────────────────→ assemble_evidence → generate_answer → END
```

See [docs/architecture.md](docs/architecture.md) for the full diagram.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/dev-up.sh` | Build and start everything (pipeline + runtime) |
| `scripts/runtime-up.sh` | Start runtime services only |
| `scripts/pipeline-run.sh` | Run scraper then ingestor |
| `scripts/reset-db.sh` | Wipe Neo4j and Qdrant volumes |
| `scripts/export-snapshots.sh` | Export Neo4j dump and Qdrant snapshot |

## Demo Queries

**Triggers image search path:**
- *"What does Jill Valentine look like across different games?"*
- *"Which concept art items relate to Nemesis?"*

**Skips image search:**
- *"Who is connected to Umbrella through direct employment and outbreak events?"*
- *"Which games connect Leon S. Kennedy and Ada Wong?"*
- *"What enemies are related to Tyrant lineage?"*

## Development

See [docs/architecture.md](docs/architecture.md) and [docs/api-contract.md](docs/api-contract.md).

Branches: feature branches → `develop` → `main` via PR.
