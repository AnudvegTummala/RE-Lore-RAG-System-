# Pipeline Improvement Plan

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Done

---

## Phase 1 — Scraper: Richer Image Metadata

All changes in `pipeline/scraper/`. Must be done before re-running the scraper; ingestor changes in Phase 2 consume the enriched manifest.

- [x] **1a. Track section context per image**
  `parsers/common.py` — maintain a `current_section` variable as the body walker crosses `h2`/`h3` headings. Attach `"section": current_section` to each image entry returned by `_make_image_entry()`.

- [x] **1b. Extract real captions**
  `parsers/common.py` — before falling back to `alt_text`, check the image's parent chain for `<figcaption>` or `.thumbcaption` text. Store as a separate `"caption"` field in the image entry (kept distinct from `alt_text`).

- [x] **1c. Forward section + caption through the manifest**
  `utils/manifests.py` — add `section`, `caption`, and `tags` parameters to `ImageManifest.add_reference()`. Write all three fields into the manifest entry.

- [x] **1d. Pass all new fields from scraper to manifest**
  `scrapers/fandom.py` — pass `section`, `caption`, and entity `tags` into `add_reference()` at the call site.

### Phase 1 — Completed Summary

**Commit:** `eaf3894` — `feat(scraper): enrich image manifest with section, caption, and tags`

**Files changed:** `parsers/common.py`, `utils/manifests.py`, `scrapers/fandom.py`

Each image entry in `image_manifest.json` now carries three new fields:
- `section` — the article heading the image appeared under (e.g. `"Appearance"`, `"History"`); infobox images are tagged `"Infobox"`.
- `caption` — real figure caption text extracted from `<figcaption>` / `.thumbcaption` in the HTML. Falls back to empty string if no caption element is found. Kept separate from `alt_text` which remains the raw HTML attribute value.
- `tags` — entity-level page categories forwarded from the parsed frontmatter (e.g. `["characters", "resident-evil-3", "s-t-a-r-s"]`).

**To take effect:** re-run the scraper. The existing `image_manifest.json` predates these changes and will not have these fields until pages are re-scraped.

---

## Phase 2 — Ingestor: Enrich Qdrant Payload + Neo4j Image Nodes

Depends on Phase 1 manifest fields being populated.

- [x] **2a. Forward dimensions + section + caption to Qdrant**
  `embeddings/image_embedder.py` — add `width`, `height`, `section`, `caption` to the `PointStruct` payload. Use `meta.get("caption") or meta.get("alt_text", "")` as the caption value.

- [x] **2b. Add index on ConceptArt.entity_id**
  `graph/schema.py` — add `CREATE INDEX concept_art_entity IF NOT EXISTS FOR (n:ConceptArt) ON (n.entity_id)` alongside the existing uniqueness constraint.

- [x] **2c. Create image loader (ConceptArt nodes + HAS_IMAGE edges)**
  New file `graph/image_loader.py` — reads `image_manifest.json`, for each downloaded non-skipped image:
  - `MERGE` a `ConceptArt` node: `{id, entity_id, entity_type, image_path, caption, section, width, height}`
  - `MERGE (entity)-[:HAS_IMAGE]->(concept_art)` where entity is matched by `id`
  - Checkpoint-gated per `image_id` so re-runs are idempotent

- [x] **2d. Wire image loader into main pipeline**
  `main.py` — add Step 6 calling `load_images_into_graph()` after existing steps.

### Phase 2 — Completed Summary

**Commit:** `3a4d710` — `feat(ingestor): enrich Qdrant payload and add ConceptArt Neo4j nodes`

**Files changed:** `embeddings/image_embedder.py`, `graph/schema.py`, `graph/image_loader.py` (new), `main.py`

- **Qdrant `concept_art` payload** now includes `width`, `height`, `section`, `caption` (prefers real caption over alt_text), and `tags`. The hardcoded `"tags": []` is gone.
- **Neo4j schema** gains a `concept_art_entity` index on `ConceptArt.entity_id` for fast per-entity image lookups.
- **`image_loader.py`** (new): reads `image_manifest.json`, `MERGE`s a `ConceptArt` node per downloaded image with all properties, then `MERGE`s a `HAS_IMAGE` edge from the owning entity node. Checkpoint-gated and idempotent — safe to re-run.
- **`main.py`** pipeline is now 6 steps; image graph loading is Step 6.

**To take effect:** delete `data/state/image_embedder.json` and `data/state/image_loader.json` (if they exist) and re-run the ingestor. No re-scrape needed if the manifest already has the Phase 1 fields; otherwise run the scraper first.

---

## Phase 3 — Ingestor: Chunk Overlap + Hybrid Search Foundation

Self-contained chunker improvement. No dependency on Phase 1/2.

- [ ] **3a. Add sentence-level overlap to chunker**
  `utils/chunker.py` — when finishing a child chunk, carry the last sentence of that chunk forward as the start of the next child. ~50-char overlap. Prevents context loss at chunk boundaries.

- [ ] **3b. Add sparse vector field to Qdrant lore_text collection**
  `qdrant/collections.py` — configure `lore_text` with a named sparse vector alongside the existing dense vector. This is the foundation for hybrid BM25+dense search (Phase 5).

- [ ] **3c. Compute and store BM25 sparse vectors at embed time**
  `embeddings/text_embedder.py` — use `qdrant_client`'s built-in `SparseVector` or a `BM25Encoder` (from `qdrant-sparse-encoders` / `fastembed`) to produce a sparse vector per chunk and upsert it alongside the dense vector.

---

## Phase 4 — Ingestor: Harvest Infobox + Body Entity Links into Neo4j

Enriches the graph with data already extracted by the scraper but currently discarded.

- [ ] **4a. Ingest all infobox properties as node properties**
  `graph/loader.py` — when creating entity nodes, write the full `infobox` dict from frontmatter as individual node properties (e.g., `height`, `blood_type`, `nationality`, `status`) rather than only using a subset for relationship building.

- [ ] **4b. Extract MENTIONS relationships from body text**
  New file `graph/mention_extractor.py` — after relationship building, scan each entity's markdown body for references to other known entity titles. For each hit, `MERGE (source)-[:MENTIONS]->(target)`. Use the existing entity title index for lookup. Checkpoint-gated.

- [ ] **4c. Wire mention extractor into main pipeline**
  `main.py` — add as Step 7 after relationship building.

---

## Phase 5 — Runtime API: Retrieval Quality Improvements

All changes in `runtime/api/`. Each item is independently deployable.

- [ ] **5a. Parallelize graph_retrieval and vector_retrieval**
  `graph/workflow.py` — remove the sequential edge `classify_query → graph_retrieval → vector_retrieval`. Replace with a fan-out from `classify_query` to both nodes simultaneously, then a join node before `rerank`. LangGraph supports this natively via multiple `add_edge` calls from the same source.

- [ ] **5b. Bump vector retrieval limit to 15**
  `graph/nodes/vector_retrieval.py` — change hardcoded `limit=5` to `limit=15`. More candidates into the reranker = better final selection with no extra latency.

- [ ] **5c. Add score threshold to reranker**
  `graph/nodes/rerank.py` — after sorting by score, filter to results above a minimum threshold (e.g. `0.3`) before applying TOP_K. If nothing passes the threshold, keep top-1 as a fallback rather than producing empty results. This prevents weak evidence from being passed to the LLM as if it were valid.

- [ ] **5d. Set LLM temperature**
  `graph/nodes/generate.py` or `services/llm.py` — set `temperature=0.15` on the ChatGroq instance. Default is ~0.7 which introduces unnecessary variance on factual lore answers.

- [ ] **5e. LRU cache on query embeddings**
  `services/qdrant_service.py` — wrap the `encode()` call with a `functools.lru_cache(maxsize=128)` keyed on the query string. Repeated queries in the same process skip re-encoding entirely.

- [ ] **5f. Enable hybrid search at query time**
  `services/qdrant_service.py` + `graph/nodes/vector_retrieval.py` — use Qdrant's `query_points` with `prefetch` (dense) + sparse vector, fused via RRF. Requires Phase 3b/3c to have populated sparse vectors. This is the single biggest recall improvement for proper nouns and abbreviations (BSAA, S.T.A.R.S., T-Abyss).

- [ ] **5g. Improve entity hint extraction in classify node**
  `graph/nodes/classify.py` — extend `_ENTITY_PATTERN` to also match: all-caps tokens (BSAA, STARS), hyphenated names (T-Abyss, G-Virus), single-letter names, and known abbreviations. Add a deduplicated fallback that lowercases and searches if the strict regex finds nothing.

---

## Future Improvements (deferred — do not implement now)

- [ ] **F1. Retrieval confidence pass-through in state** (`graph/state.py`)
  Add `rerank_scores: list[float]`, `vector_scores: list[float]`, `retrieval_adequate: bool` fields to `GraphState`. Let reranker write scores into state. Let assemble and generate nodes inspect scores to make adaptive decisions (skip rerank if top score > 0.95, trigger fallback if all scores < 0.3, suppress generation if retrieval failed). Currently `retrieval_adequate` is set by checking `len(evidence) > 50` which is meaningless.

- [ ] **F2. NER-based entity extraction and alias resolution** (`pipeline/scraper/` + `pipeline/ingestor/`)
  Run a lightweight NER model (spaCy or a fine-tuned RE-domain model) over scraped markdown before ingestion to extract canonical entity references and aliases. Resolve "Nemesis-T", "The Pursuer", "NEMESIS" → single canonical node. Also enables proper `MENTIONS` relationship extraction (replaces the heuristic body scanner from Phase 4b). Highest ceiling improvement but also the most involved.

---

## Implementation Order Summary

```
Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5
(scraper)   (ingestor   (chunker +   (graph       (runtime:
            images)     hybrid       enrichment)  retrieval
                        foundation)              quality)
```

Phases 3, 4, and 5 are largely independent of each other and can be parallelized if multiple people are working. Phase 5f (hybrid search at query time) depends on Phase 3b/3c being deployed first.

After all phases are complete: delete image embedder checkpoint + graph loader checkpoint and re-run the ingestor against the existing scraped data to get enriched vectors and graph nodes without needing to re-scrape.
