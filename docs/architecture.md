# Architecture

## System Overview

RE Lore Oracle is a locally hosted, Dockerized knowledge retrieval system for the Resident Evil franchise. Architecturally it is interesting because it combines three distinct retrieval modalities — graph traversal, dense + sparse vector search, and CLIP image embedding — orchestrated through a LangGraph stateful pipeline with parallel fan-out, a cross-encoder reranker, and conditional image routing, all streaming tokens to the browser via SSE. The data layer is populated entirely offline by a two-stage pipeline that scrapes the wiki, enriches a Neo4j knowledge graph, and builds named-vector Qdrant collections. The result is a system where users can ask natural-language lore questions and receive grounded answers with source citations, a live knowledge graph panel, and concept art.

---

## Component Map

| Service | Port | Role | Source |
|---|---|---|---|
| `neo4j` | 7474 (HTTP), 7687 (Bolt) | Graph database storing entity nodes, relationships, and lore chunks | Docker Hub official Neo4j 5 image |
| `qdrant` | 6333 | Vector database with hybrid dense + sparse named vectors | Docker Hub official Qdrant image |
| `clip-service` | 8001 | Isolated FastAPI service running the OpenCLIP ViT-B-32 model for image and text embedding | `runtime/clip-service/` |
| `api` | 8000 | FastAPI backend; houses the LangGraph pipeline and all query logic | `runtime/api/` |
| `frontend` | 3000 | React + Vite + Tailwind chat UI with Cytoscape graph panel | `runtime/frontend/` |
| `scraper` (pipeline) | — | Offline async wiki scraper; produces markdown corpus and image files | `pipeline/scraper/` |
| `ingestor` (pipeline) | — | Offline ingestor; reads corpus, populates Neo4j and Qdrant | `pipeline/ingestor/` |

Both `api` and `clip-service` inherit from a shared base image (`runtime/base/`) that packages the heavy ML dependencies: PyTorch, sentence-transformers, OpenCLIP, and fastembed. This base image is built once with `scripts/build-base.sh` and then referenced by `FROM re-lore-base` in each service's Dockerfile.

---

## The Data Pipeline (offline)

The pipeline runs once before the runtime stack is used. It has two stages — scraper then ingestor — each in its own Docker Compose service under `pipeline/docker-compose.yml`.

### Why an offline pipeline rather than live scraping?

The RE wiki corpus is essentially static on any given day. Scraping is slow (rate-limited, Cloudflare-protected, multi-hour for full coverage) and embedding is GPU-bound and equally slow. Separating the pipeline from the runtime avoids all of that latency at query time, lets the runtime serve from pre-built indexes, and separates concerns cleanly: the pipeline produces data, the runtime consumes it. Re-running the pipeline only when the corpus changes (new game releases, wiki corrections) is the right tradeoff.

### Scraper (`pipeline/scraper/`)

The scraper is a Python service using httpx and BeautifulSoup. Its job is to turn wiki pages into markdown files with YAML frontmatter and to download image assets.

**URL discovery.** The obvious approach — fetching `wiki/Category:Characters` — does not work because Fandom renders those pages with JavaScript and serves a Cloudflare challenge page to automated requests. Instead the scraper uses the MediaWiki `api.php?action=query&list=categorymembers` endpoint to enumerate all pages in a category, with a recursive BFS that descends into subcategories to depth 5. Category names were verified against the live API: `Creatures`, `Organisations`, `Biological_agents`, `Equipment` — not the display names shown in the browser.

**Page fetch.** Direct HTML page fetches are also Cloudflare-blocked. The scraper uses `api.php?action=parse&page=...` which returns structured JSON including the parsed HTML body. This endpoint is not behind the JS challenge. The canonical wiki URL is still recorded in the frontmatter `source_url` for citation purposes.

**Film and non-canon filtering.** A two-layer filter prevents film and non-game-canon pages from entering the corpus. `_EXCLUDED_SUBCATEGORIES` is a frozenset that blocks BFS from entering category subtrees for Anderson films, DeCandido/Perry novels, WildStorm comics, Monolith Soft crossovers, and Welcome to Raccoon City. `_EXCLUDED_ARTICLE_CATEGORIES` is a second-pass check on the article's own `prop=categories` response — it catches pages that appear in both game and film categories. This ensures the corpus contains only game-canon lore.

**7 entity types, all sharing a parser.** The scraper produces 7 entity categories: `character`, `game`, `enemy`, `location`, `organization`, `virus`, `weapon`. Each has its own parser module in `parsers/`, but all 7 delegate the actual parsing to `parsers/common.py`'s `parse_entity_page()` function. There is no meaningful per-type variation in scraping logic — the entity type is a metadata tag, not a behavioral difference.

**Categories as tags.** The `api.php?action=parse` response does not include the page header HTML where category links normally live. The scraper adds `prop=categories` to the API call and extracts non-hidden categories from the API response. These become the `tags` array in frontmatter. Files scraped before this fix have `tags: []`.

**3 manifest files.** All manifest files live under `data/raw/manifests/`. `image_manifest.json` is a flat dict mapping `image_id → meta` (including `local_path`, `source_url`, `alt_text`, `width`, `height`, `section`, `caption`, `tags` after Phase 1). `source_registry.json` tracks every source URL processed. `scrape_manifest.json` tracks completion status per entity.

**Checkpoints.** Each scraper run writes an atomic checkpoint (`.tmp` rename) and auto-flushes every 10 completions. This makes the scraper resumable if interrupted mid-run.

**Cloudflare bypass.** The scraper container runs with `network_mode: host` in its Docker Compose file. This means it shares the host's network stack rather than NAT-ing through a Docker bridge. The host's residential ISP IP is used for requests, which passes Cloudflare's bot detection. If the scraper ran inside Docker's default NAT, it would be making requests from a datacenter IP range and would be blocked.

**Wikipedia supplementary scraper.** The scraper also fetches supplementary content from Wikipedia using the `wikipedia-api` library. It targets sections like Gameplay, Plot, Synopsis, Story, Setting, Characters, and Narrative. Title resolution tries the plain title first, then the `(video game)` suffix, then a Roman numeral variant for numbered titles. This content is appended under a `## Wikipedia` heading in the markdown file. Sequential processing is used for a polite crawl rate.

### Ingestor (`pipeline/ingestor/`)

The ingestor reads the markdown corpus and populates both databases. It runs in 7 sequential steps, each checkpoint-gated for idempotency.

**Step 1: Schema.** Creates Neo4j uniqueness constraints and title indexes for all node labels: `Character`, `Game`, `Enemy`, `Virus`, `Organization`, `Location`, `Weapon`, `ConceptArt`, `LoreChunk`, `TimelineEvent`. Uses APOC, which is loaded via the `NEO4J_PLUGINS` environment variable in the runtime `docker-compose.yml`.

**Step 2: Graph node loading (pass 1).** Reads each markdown file and creates the entity node in Neo4j with its core properties. Also writes infobox fields as individual node properties — raw infobox keys are sanitised (lowercased, non-alphanumeric runs replaced with `_`) before being written via `SET n += $props` to avoid overwriting existing properties. This means node properties are enriched beyond the minimal `id`, `name`, `source_url` set — they include whatever structured data the wiki infobox contained (`height`, `blood_type`, `nationality`, `status`, etc.).

**Step 3: Relationship building (pass 2).** Scans frontmatter `related_games`, `related_entities`, and infobox fields to create typed relationships between nodes. Creates stub nodes for referenced entities that were not scraped (e.g. a character references a game from a not-yet-scraped category) so the graph is internally consistent. These stubs are filled in when the corresponding category is later ingested.

**Step 4: Mention extraction.** Scans each entity's markdown body text for references to other known entity titles. Uses whole-word regex matching (`\b{title}\b`, case-insensitive) against a lookup table of all known entity `(id, title)` pairs, sorted longest-first to prefer multi-word names over substrings. Creates `MERGE (source)-[:MENTIONS]->(target)` edges for each match. This produces a second layer of graph connectivity beyond the structured relationship builder, capturing co-references that appear in prose but not in frontmatter.

**Step 5: Text embedding.** Reads each markdown file, chunks it hierarchically (see below), embeds each child chunk with `all-MiniLM-L6-v2` (384-dim), and upserts into the Qdrant `lore_text` collection with named vectors: `"dense"` (the sentence-transformer embedding) and `"sparse"` (a BM25 sparse vector from the `fastembed` `Bm25("Qdrant/bm25")` pre-fitted model). The dense encoder runs in a thread executor to avoid blocking the event loop.

**Step 6: Image embedding.** Reads `image_manifest.json`, skips entries without a `local_path`, and sends each image to the CLIP service's `POST /embed/image` endpoint as `multipart/form-data`. Upserts into the Qdrant `concept_art` collection (512-dim, dense only). Payload includes `entity_id`, `entity_type`, `image_path`, `caption`, `section`, `width`, `height`, `tags`.

**Step 7: Neo4j image nodes.** For each downloaded image in `image_manifest.json`, creates a `ConceptArt` node and a `HAS_IMAGE` edge from the owning entity node. Uses `MERGE` on both, so re-runs are idempotent. The `HAS_IMAGE` relationship name (not `HAS_CONCEPT_ART`) is what the code uses; the data model documentation reflects this.

**Checkpoints** live at `data/state/` (not `data/checkpoints/`). Each step writes its checkpoint there. After wiping a database volume, the relevant checkpoint files must be deleted before re-running the ingestor or it will believe the step is already complete.

**Hierarchical parent-child chunking.** Each markdown section becomes a parent chunk (≤1500 chars). Each parent is then sub-split into child chunks (≤400 chars) at sentence boundaries, with ~1 sentence of overlap carried forward to prevent context loss at boundaries. The design rationale: child chunks are small enough that their embeddings are precise and retrievable — the embedding captures the meaning of a focused passage rather than a diluted mixture of multiple topics. But 400 chars is not enough context for the LLM to generate a good answer. So the parent section text (≤1500 chars) is stored in the Qdrant payload alongside the child embedding and returned to the LLM at query time. This gives precise retrieval with full-context generation.

**Contextual prefix.** Every child chunk is prefixed with `"{title} — {section}: "` before embedding. Without this prefix, a chunk like "He survived the Raccoon City incident by..." has no vector signal indicating it is about Leon S. Kennedy. With the prefix, the embedding space carries entity context. This is especially important for short chunks that don't re-state the subject.

**Why CLIP is a separate service.** The CLIP model (OpenCLIP ViT-B-32) has deep CUDA and PyTorch dependencies that are version-sensitive. The ingestor and API both use `sentence-transformers`, which has its own PyTorch dependency graph. Running CLIP and sentence-transformers in the same Python environment causes version conflicts. The microservice pattern isolates these completely: the CLIP service maintains its own environment and model, and the ingestor and API call it over HTTP as a black box. Additionally, the CLIP service can be killed, restarted, or replaced without touching the API or ingestor. Memory-wise, the CLIP model (~340 MB) is isolated to its own container and does not compete with the API's sentence-transformer model.

---

## LangGraph Query Pipeline

### Why LangGraph?

A plain Python function chain — call graph retrieval, then vector retrieval, then generate — would work for the basic case, but it has several problems. There is no typed state object shared across steps, so each function must thread its outputs through arguments to the next, creating brittle interfaces. Conditional routing (skip image search if not needed) requires manual `if/else` around function calls. Adding parallelism means managing async tasks manually. Streaming events requires custom plumbing into the generation step. LangGraph solves all of these with its `StateGraph` abstraction: all nodes read from and write to a single `GraphState` TypedDict, edges can be conditional, the fan-out to parallel nodes is declared as multiple `add_edge` calls from the same source (LangGraph handles the join automatically), and `astream_events(version="v2")` gives a first-class streaming event API. Future extensibility (adding a retry loop, a validation node, a hallucination detector) is also much cleaner in a graph than in a chain.

### GraphState

Defined in `runtime/api/app/graph/state.py`. Every node reads from and writes to this object:

```python
class GraphState(TypedDict):
    query: str              # raw user question, unchanged throughout
    entity_hints: list[str] # entity names extracted by classify_query
    needs_image_search: bool# routing flag set by classify_query
    graph_results: list[dict] # subgraph data from Neo4j
    text_results: list[dict]  # lore chunks from Qdrant (after reranking, top-3)
    image_results: list[dict] # concept art from Qdrant+CLIP
    evidence: str           # assembled context string for the LLM
    answer: str             # final generated answer
    retrieval_adequate: bool# set by generate_answer; currently a simple length check
```

`retrieval_adequate` is set by a `len(evidence) > 50` check in the generate node. A proper confidence-based implementation (using reranker scores) is tracked as a future improvement (F1) and has not yet been implemented.

### Nodes

**`classify_query`** (`nodes/classify.py`)

Reads `query`. Writes `entity_hints` and `needs_image_search`.

Extracts entity names using four compiled regex patterns: `_TITLE_CASE` (capitalised words like "Leon Kennedy"), `_ALL_CAPS` (acronyms like BSAA, STARS), `_DOTTED` (dotted abbreviations like S.T.A.R.S., B.O.W.), `_HYPHENATED` (hyphenated names like T-Virus, G-Virus, T-Abyss). A `_KNOWN_ALIASES` set covers RE-domain proper nouns that appear fully lowercase in natural queries. The aliases are only checked as a fallback if all four regex patterns return nothing.

`needs_image_search` is set to `True` if the query contains visual terms: "concept art", "look like", "appearance", "design", "show me", "image", "picture", "portrait". This uses a keyword list, not a model.

The regex approach was chosen over spaCy because spaCy's NER models are not trained on RE-domain proper nouns. S.T.A.R.S., T-Abyss, and BSAA are not in any standard NER training set, so spaCy would miss or misclassify them. The regex patterns are explicitly designed for the domain vocabulary. The tradeoff is that the heuristic is less generalizable, but for a domain-specific system that is acceptable.

**`graph_retrieval`** (`nodes/graph_retrieval.py`)

Reads `entity_hints`. Writes `graph_results`.

Runs a Cypher query on Neo4j using APOC `subgraphAll` for a **1-hop** traversal from any node whose `title` OR `name` property matches an entity hint (case-insensitive). Returns all nodes and relationships within 1 hop of the matched entities. The depth is deliberately 1 rather than 2: with 18,000+ `MENTIONS` edges in the graph, 2-hop traversal from 5 seed entities routinely returned 150–200 nodes, which caused the Cytoscape renderer to hang. 1-hop returns direct connections (typically 10–40 nodes) while still capturing the most relevant relationships.

The Cypher also matches on `e.name` in addition to `e.title` because some entities (primarily legacy nodes) store their identifier in `name` rather than `title`. Matching both prevents silent misses.

`_serialise_graph` in `routers/query.py` applies a hard cap of 60 nodes and trims dangling edges as a safety net, even after the 1-hop depth reduction.

When the query has no capitalised entity hints, graph retrieval returns nothing. The `_serialise_graph` function falls back to building graph nodes from `text_results` entity_ids so the Knowledge Graph panel always shows something.

**`vector_retrieval`** (`nodes/vector_retrieval.py`)

Reads `query`. Writes `text_results`.

Embeds the query with `all-MiniLM-L6-v2` via `qdrant_service.encode()` (runs in a thread executor). Calls `qdrant_service.search_text()` which uses Qdrant's `query_points` with a `prefetch` list of two sub-queries: one dense (named vector `"dense"`) and one sparse (named vector `"sparse"`, BM25 via fastembed), each fetching `limit*2` candidates, fused via RRF (Reciprocal Rank Fusion). Falls back to plain dense-only `client.search()` if the collection does not have named vectors (e.g. pre-Phase-3 data).

Retrieves 15 candidates. More candidates into the reranker means better final selection quality.

Hybrid search is critical for RE proper nouns. A term like "BSAA" or "S.T.A.R.S." is a token that dense vectors handle poorly — the embedding captures semantics, but the exact token matching that BM25 provides is more reliable for acronyms. RRF fusion combines both lists without needing to tune relative weights.

**`rerank`** (`nodes/rerank.py`)

Reads `query` and `text_results`. Writes `text_results` (overwritten with the reranked subset).

The cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) scores all (query, passage) pairs jointly, attending to both simultaneously. This gives much higher precision than the bi-encoder retrieval that produced the 15 candidates: bi-encoders optimise for recall over a large corpus (they must be fast), while cross-encoders optimise for precision on a small candidate set (they can be slow because they see only a handful of pairs).

Scores are sorted descending. Results above a 0.3 threshold are kept. If nothing clears the threshold, the single top-scoring result is kept regardless — this prevents the LLM from receiving empty evidence and hallucinating a complete answer. At most 3 results are passed forward. The cross-encoder runs in a thread executor (`loop.run_in_executor`) because it is CPU-bound.

**`image_retrieval`** (`nodes/image_retrieval.py`)

Reads `query`, `needs_image_search`, `graph_results`, and `text_results`. Writes `image_results`.

Only runs when `needs_image_search=True`. Calls the CLIP service's `POST /embed/text` endpoint to embed the query text into CLIP's 512-dim embedding space. Searches the Qdrant `concept_art` collection filtered to a resolved set of entity_ids.

**Entity filter construction** (order of priority):
1. Extract all entity_ids from `graph_results` nodes and filter to visual prefixes: `character-*`, `enemy-*`, `organization-*`. These are the verified Neo4j matches for the query hints.
2. Supplement with entity_ids from `text_results` that share the same visual prefixes.
3. If neither source yields any visual entity_ids, fall back to all entity_ids from `text_results`.

`game-*`, `location-*`, `weapon-*`, and `virus-*` entity_ids are excluded explicitly — their images are game cover art and location screenshots, not character concept art. Without this filter, a query for "What does Jill Valentine look like?" would retrieve cover art for every game she appears in, because those game entities dominate the text_results.

The graph_results source is preferred over text_results because it reliably identifies the correct entity regardless of how the wiki classified the character. For example, the main Jill Valentine page has `entity_id: enemy-jill-valentine` (classified as enemy because the BFS found her through the "Creatures" category). The prefix filter `enemy-*` matches her correctly, and the graph_results always contain her node when "Jill Valentine" appears in the query.

**`assemble_evidence`** (`nodes/assemble.py`)

Reads `graph_results`, `text_results`, `image_results`. Writes `evidence`.

Merges all retrieved results into a single context string for the LLM prompt. Deduplicates by `(entity_id, section)` pair — the same section from the same entity should appear at most once, regardless of how many chunks or graph paths led to it. Sections with fewer than 80 meaningful characters (after stripping whitespace and punctuation) are skipped as they contain no real content (stub sections like `## History` with no body are common on the wiki). Image captions from `image_results` are appended as descriptive text.

**`generate_answer`** (`nodes/generate.py`)

Reads `query` and `evidence`. Writes `answer` and `retrieval_adequate`.

Calls the Groq API via `ChatGroq` with `streaming=True` and `temperature=0.2`. Low temperature makes the model more deterministic and less prone to confabulation when given specific evidence. Streams tokens via LangGraph's event system; the FastAPI router captures these as SSE events. Sets `retrieval_adequate` based on `len(evidence) > 50`.

### Parallel Fan-out

`classify_query` has two outgoing edges: one to `graph_retrieval` and one to `vector_retrieval`. Both nodes execute concurrently. LangGraph's fan-in semantics mean `rerank` does not begin until both upstream nodes have written their results into the shared state. No explicit synchronisation code is needed.

The rationale: graph traversal and vector search are completely independent operations — graph retrieval uses `entity_hints` and vector retrieval uses `query`. Running them sequentially would waste time waiting for whichever finishes first. The reranker benefits from having both sets of candidates, which is why it sits after both retrieval branches rather than after just one.

**Critical implementation constraint:** Parallel nodes must return only the keys they write — not a full state spread. `graph_retrieval` must return `{"graph_results": records}`, not `{**state, "graph_results": records}`. When two nodes run concurrently and both return the full state (including `query`, `entity_hints`, etc.), LangGraph raises `InvalidUpdateError: At key 'query': Can receive only one value per step` because both writes land in the same channel in the same step. Returning only the changed key avoids the conflict.

### Conditional Image Search

The `_route_after_rerank` function checks `state["needs_image_search"]`. If True, routes to `image_retrieval` then `assemble_evidence`. If False, routes directly to `assemble_evidence`. This prevents a CLIP service call and image vector search on every text-only lore query. CLIP embedding and image search add latency and are irrelevant for questions like "What is Leon Kennedy's backstory?" — only visual queries like "Show me concept art of Jill Valentine" should trigger them.

---

## Retrieval Strategy

### Hybrid Search: Dense + BM25

The `lore_text` Qdrant collection stores named vectors: `"dense"` (384-dim all-MiniLM-L6-v2 embedding) and `"sparse"` (BM25 sparse vector from fastembed `Bm25("Qdrant/bm25")`). At query time, Qdrant's `query_points` fetches candidates from both named vectors and fuses the ranked lists using RRF.

Dense vectors capture semantic similarity — "umbrella corporation" and "Umbrella" will match even without exact token overlap. BM25 captures exact token matches — "BSAA", "S.T.A.R.S.", "T-Abyss", "G-Virus" are RE-domain proper nouns that appear infrequently in the corpus and need exact match. RRF fusion combines both ranked lists by reciprocal rank sums, which is robust and requires no weight tuning.

The `fastembed` `Bm25("Qdrant/bm25")` pre-fitted model requires no corpus-level fitting. It uses a general English BM25 vocabulary, which is sufficient for domain proper nouns because they are distinct tokens even without domain-specific IDF weights.

### Graph Retrieval

Neo4j stores entity relationships as typed edges: `APPEARS_IN`, `MEMBER_OF`, `ENCOUNTERS`, `INFECTED_WITH`, `CREATED_BY`, `LOCATED_IN`, `FEATURED_IN`, `HAS_IMAGE`, `DESCRIBED_IN`, `PRECEDES`, `SUCCEEDS`, and `MENTIONS`. The APOC `subgraphAll` function returns the subgraph within 1 hop of each matched entity (up to 30 relationship traversals per seed entity).

1-hop traversal captures the most directly relevant relationships. "Who created the T-Virus?" — the path is `T-Virus ← CREATED_BY ← Umbrella`, a 1-hop traversal found directly. The depth was reduced from 2 to 1 because the 18,000+ `MENTIONS` edges make 2-hop traversal produce 150–200 nodes per query, crashing the graph renderer. 1-hop still covers the majority of meaningful relationship queries.

The `MENTIONS` relationship (added in Phase 4) provides a second layer of connectivity extracted from prose. When a character's biography mentions another character or location by name, a `MENTIONS` edge is created. This captures co-references that are real but not modelled in the structured infobox data.

Alternatives considered: Postgres with recursive CTEs or `pg_graphql` would require implementing BFS manually in SQL and would not give the property graph semantics (typed relationships, relationship properties) that Neo4j provides natively.

### Image Retrieval

CLIP embeds both images and text into a shared 512-dim embedding space. A CLIP text embedding of "Jill Valentine in her STARS uniform" will be geometrically close to the embedding of an image of Jill in that uniform. This cross-modal retrieval is why CLIP is used rather than a text-only similarity over image captions.

The entity_id filter from text results is critical. Without it, a query for "Nemesis" might retrieve a visually similar image of another tall enemy — same pose, similar palette. Filtering by entity_ids from text results means the image search is restricted to images whose entity_id was already retrieved as relevant by the vector search. This prevents false positive image matches.

### Evidence Assembly

The assembler deduplicates by `(entity_id, section)` — if both graph retrieval and vector retrieval returned information about the "Biography" section of Leon Kennedy, only one instance appears in the evidence. The 80-character minimum filters stub sections that would add no information to the LLM prompt but would waste context window space.

---

## Why These Technology Choices

### Neo4j

Neo4j provides native property graph semantics: typed directed relationships with properties, Cypher query language, APOC plugin for advanced traversal functions like `subgraphAll`. The alternative — a relational database with Postgres — would require either manual BFS queries with recursive CTEs or a separate graph extension. The BFS implementation for 2-hop traversal would need careful index design and would still be harder to read and maintain than a 3-line Cypher query.

### Qdrant

Qdrant was chosen for its native hybrid search support via named vectors: a single collection can store multiple named vector fields (dense and sparse), and Qdrant's `query_points` API fuses them with RRF natively. The alternatives considered were Weaviate and Pinecone. Weaviate supports hybrid search but its on-premise sparse vector support was less mature at the time of design. Pinecone is cloud-only and adds operational overhead. Milvus was considered but adds complexity without a clear advantage for this use case. Qdrant is also lightweight to operate self-hosted, with a single binary container.

### LangGraph over bare LangChain

LangChain provides individual chain components (LLMChain, RetrievalQA) but does not handle the stateful graph, conditional routing, or streaming event bus that this pipeline requires. LangGraph extends LangChain with a `StateGraph` abstraction that handles all of these. The alternatives were a plain Python async function chain (loses streaming events and type-safe state), or Haystack (a different pipeline framework with fewer streaming primitives and a steeper configuration overhead). LangGraph's `astream_events(version="v2")` gives a clean event-based API for filtering specific node outputs.

### Groq API

Groq provides fast inference via their LPU hardware. The `llama-3.3-70b-versatile` model gives strong lore reasoning quality. The original model specified in the plan (`llama3-70b-8192`) was decommissioned by Groq; the replacement was a drop-in model change via the `GROQ_MODEL` environment variable. The alternative — local Ollama — would require a GPU capable of running a 70B parameter model at reasonable speed (at minimum 48 GB VRAM for 4-bit quantisation), which is not a common development environment. For a demo system, the Groq free tier is sufficient.

### Separate CLIP Service

The CLIP service runs as an isolated microservice for two reasons. First, model isolation: OpenCLIP with full CUDA dependencies has conflicting version requirements with `sentence-transformers` when installed in the same Python environment. Running them in separate containers avoids dependency resolution failures. Second, operational independence: the CLIP service can be restarted, scaled, or replaced (e.g. swap ViT-B-32 for ViT-L-14) without touching the API container. The model load time (2–3 minutes) is isolated to the CLIP service startup and does not block the API from serving non-image queries.

### BM25 via fastembed

The `fastembed` library provides a pre-fitted `Bm25("Qdrant/bm25")` model that requires no corpus-level IDF fitting. This is important because corpus-level fitting would need to happen during the ingest phase and then be serialised and shared with the query phase — a non-trivial operational dependency. The pre-fitted model works out of the box for English text, and because the sparse vectors are exact-match based, the domain vocabulary (proper nouns, acronyms) gets the right behaviour without any additional tuning.

---

## Streaming Architecture

The FastAPI `POST /query` endpoint (`routers/query.py`) calls `compiled_graph.astream_events(initial_state, version="v2")` and iterates over the event stream. Two event types are filtered:

- `on_chat_model_stream` — emitted by ChatGroq for each generated token. Each token is immediately written to the HTTP response as an SSE event: `data: {"token": "..."}\n\n`.
- `on_chain_end` where `event["name"] == "LangGraph"` — emitted when the entire graph finishes. The final state is extracted and a `done` SSE event is emitted: `{"done": true, "answer": "...", "sources": [...], "images": [...], "graph": {...}}`.

The frontend `useStreaming` hook (`src/hooks/useStreaming.ts`) reads the SSE stream. For `token` events it calls `updateLastMessage` which replaces the last message object in the Zustand messages array with a new object containing the accumulated content. The `assistantMsg.content` local variable is kept in sync with the store to make the token accumulation pattern work correctly across async boundaries.

The result is that the user sees the answer token-by-token as it is generated, and then the sources, graph, and images appear atomically when generation completes.

---

## Image Serving

`main.py` mounts a `StaticFiles` handler at the `/images` path pointing to the `/data/raw/images` directory on the container filesystem. This means any image file in the bind-mounted `./data/raw/images/` directory is accessible via a direct HTTP GET.

The frontend accesses images via `/api/images/...` (with the `/api` prefix). The Vite dev server proxies all `/api/*` requests to `http://localhost:8000`, stripping the `/api` prefix, so `/api/images/characters/leon.jpg` becomes `GET http://localhost:8000/images/characters/leon.jpg`. Inside Docker, the proxy target is the service name `http://api:8000` rather than `localhost:8000`, because `localhost` in the frontend container refers to itself.

`_serialise_images()` in `routers/query.py` converts the container-internal path `/data/raw/images/characters/leon.jpg` to the frontend-accessible path `/api/images/characters/leon.jpg`.

---

## Frontend State Management

The Zustand store in `src/store/appStore.ts` is the single source of truth for all UI state: `messages[]` (chat history), `isStreaming` (whether a request is in flight), `activeGraph` (the graph data for the current response), and `selectedNode` (for the node detail drawer in the graph panel).

Two custom hooks expose slices of this state to components: `useChat` provides the messages array and streaming state for the chat panel, and `useGraph` provides the active graph and selected node for the Cytoscape graph panel. Components never read from the store directly — all reads go through these hooks.

The Vite proxy is configured in `vite.config.ts` to forward all `/api/*` requests to the API server. Inside Docker Compose, the `VITE_API_URL` environment variable is set to `http://api:8000` (the Docker service name) rather than `localhost:8000`, because the frontend container cannot reach the API container via `localhost`.

---

## Docker Build Architecture

### Shared Base Image

The `runtime/base/` directory contains a single Dockerfile that installs all heavy ML dependencies shared between `api` and `clip-service`: PyTorch (with device-appropriate wheel), sentence-transformers, OpenCLIP, and fastembed. Both `runtime/api/Dockerfile` and `runtime/clip-service/Dockerfile` start with `FROM re-lore-base`, inheriting all of these layers.

Before the base image existed, each service's Dockerfile installed torch independently. This meant a 1.5 GB torch download on every rebuild of either service, even for a one-line code change. With the shared base, torch is installed once and cached as a Docker layer. Subsequent rebuilds of `api` or `clip-service` start from the pre-built base and only re-install their own application-level dependencies.

The base image also pre-warms the three models at build time:
- `all-MiniLM-L6-v2` (sentence-transformers) — for text embedding
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (CrossEncoder) — for reranking
- `ViT-B-32` (OpenCLIP) — for image embedding

This means model files are baked into the base image layer. Container startup does not require downloading model weights — the files are already present in the layer cache.

### TORCH_DEVICE Auto-Detection

The base Dockerfile accepts a `TORCH_DEVICE` build argument (`auto`, `cpu`, or `cuda`). When set to `auto` (the default), the build script checks for `nvidia-smi` at build time. If an NVIDIA GPU is available, the full CUDA torch wheel (~1.5 GB) is installed. If not, the CPU-only wheel (~250 MB) is installed. This means the same `build-base.sh` script works correctly on a developer laptop (CPU fallback) and on a GPU server (CUDA wheel) without any manual configuration.

On Mac with Apple Silicon and Docker Desktop, the MPS backend is not available inside containers — Docker Desktop runs a Linux VM using QEMU/KVM, and MPS is not a Linux construct. The `auto` detection correctly falls back to CPU in this environment.

### BuildKit Pip Cache

The base Dockerfile uses `--mount=type=cache,target=/root/.cache/pip` in the `RUN pip install` step. This tells BuildKit to mount a persistent cache directory for pip downloads. Pip wheels are cached across builds. Even when a code change busts the `COPY` layer and forces a pip reinstall, the wheels themselves are served from cache rather than re-downloaded from PyPI or the torch CDN. This makes incremental rebuilds much faster after the first run.

### GHCR Pre-built Image

`scripts/push-base.sh` pushes the tagged base image to GitHub Container Registry (`ghcr.io/mhamdashfaque/re-lore-base:latest`). Teammates who want to avoid the 10–20 minute base build can pull this pre-built image instead:

```bash
docker pull ghcr.io/mhamdashfaque/re-lore-base:latest
```

After pulling, `docker compose build api` and `docker compose build clip-service` will start from the pulled base layer and only install application-level dependencies, which takes seconds rather than minutes.
