# Architecture

## Overview

RE Lore Oracle is a locally hosted, Dockerized knowledge system. Every user query flows through a LangGraph `StateGraph` that orchestrates retrieval from Neo4j (graph), Qdrant (vector), and an OpenCLIP service (image), then generates a grounded answer via the Groq API.

## LangGraph Pipeline

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

### Nodes

| Node | File | Reads | Writes |
|---|---|---|---|
| `classify_query` | `graph/nodes/classify.py` | `query` | `entity_hints`, `needs_image_search` |
| `graph_retrieval` | `graph/nodes/graph_retrieval.py` | `entity_hints` | `graph_results` |
| `vector_retrieval` | `graph/nodes/vector_retrieval.py` | `query` | `text_results` |
| `image_retrieval` | `graph/nodes/image_retrieval.py` | `query` | `image_results` |
| `assemble_evidence` | `graph/nodes/assemble.py` | `graph_results`, `text_results`, `image_results` | `evidence` |
| `generate_answer` | `graph/nodes/generate.py` | `query`, `evidence` | `answer`, `retrieval_adequate` |

### GraphState

```python
class GraphState(TypedDict):
    query: str
    entity_hints: list[str]
    needs_image_search: bool
    graph_results: list[dict]
    text_results: list[dict]
    image_results: list[dict]
    evidence: str
    answer: str
    retrieval_adequate: bool
```

## Services

| Service | Port | Description |
|---|---|---|
| `neo4j` | 7474 / 7687 | Graph database |
| `qdrant` | 6333 | Vector database |
| `clip-service` | 8001 | OpenCLIP embedding service |
| `api` | 8000 | FastAPI + LangGraph |
| `frontend` | 3000 | React + Vite |

## Data Flow

1. User submits query → FastAPI `/query`
2. LangGraph `compiled_graph.astream_events()` called with initial state
3. `classify_query` extracts entity names and sets `needs_image_search`
4. `graph_retrieval` runs Cypher traversal on Neo4j (up to 2 hops)
5. `vector_retrieval` embeds query with sentence-transformers, searches Qdrant `lore_text`
6. If `needs_image_search`: `image_retrieval` calls CLIP service, searches `concept_art`
7. `assemble_evidence` merges and deduplicates all results into a context string
8. `generate_answer` sends evidence + query to Groq; tokens stream as SSE
9. Final state (sources, images, graph) emitted as last SSE event
10. Frontend `useStreaming` appends tokens, then renders sources and graph panel
