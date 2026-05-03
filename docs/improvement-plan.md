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

- [x] **3a. Add sentence-level overlap to chunker**
  `utils/chunker.py` — when finishing a child chunk, carry the last sentence of that chunk forward as the start of the next child. ~50-char overlap. Prevents context loss at chunk boundaries.

- [x] **3b. Add sparse vector field to Qdrant lore_text collection**
  `qdrant/collections.py` — configure `lore_text` with a named sparse vector alongside the existing dense vector. This is the foundation for hybrid BM25+dense search (Phase 5).

- [x] **3c. Compute and store BM25 sparse vectors at embed time**
  `embeddings/text_embedder.py` — use `qdrant_client`'s built-in `SparseVector` or a `BM25Encoder` (from `qdrant-sparse-encoders` / `fastembed`) to produce a sparse vector per chunk and upsert it alongside the dense vector.

### Phase 3 — Completed Summary

**Files changed:** `utils/chunker.py`, `qdrant/collections.py`, `embeddings/text_embedder.py`, `requirements.txt`

**3a — Chunk overlap (`utils/chunker.py`):**
- New `_last_sentence()` helper extracts the last sentence from a text string by splitting on `_SENTENCE_END`.
- `_split_children()` now captures `overlap = _last_sentence(current)` before flushing each child. The next child starts with that overlap sentence, so every chunk boundary has ~one sentence of bridging context.
- Both flush paths updated: the normal budget-overflow path and the hard-split path for oversized sentences.

**3b — Named vector collection (`qdrant/collections.py`):**
- `lore_text` is now created with `vectors_config={"dense": VectorParams(...)}` and `sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))}`.
- Imports extended with `SparseIndexParams`, `SparseVectorParams`.
- `concept_art` collection is unchanged (dense-only CLIP; no sparse search needed there).

**3c — BM25 sparse vectors (`embeddings/text_embedder.py`, `requirements.txt`):**
- New dep: `fastembed==0.4.2` in `requirements.txt`.
- `Bm25("Qdrant/bm25")` loaded at startup alongside the dense encoder — no corpus-level fitting required; uses a pre-fitted English model.
- `flush_batch()` now calls `bm25.query_embed(texts)` to get sparse results alongside `encoder.encode()` for dense. Each `PointStruct` uses `vector={"dense": ..., "sparse": SparseVector(indices=..., values=...)}` matching the named-vector schema.

**To take effect:** the `lore_text` Qdrant collection **must be deleted and recreated** (Qdrant does not support in-place vector config changes). Delete the collection via Qdrant dashboard or `qdrant-client`, delete `data/state/text_embedder.json`, and re-run the ingestor. No re-scrape needed.

---

## Phase 4 — Ingestor: Harvest Infobox + Body Entity Links into Neo4j

Enriches the graph with data already extracted by the scraper but currently discarded.

- [x] **4a. Ingest all infobox properties as node properties**
  `graph/loader.py` — when creating entity nodes, write the full `infobox` dict from frontmatter as individual node properties (e.g., `height`, `blood_type`, `nationality`, `status`) rather than only using a subset for relationship building.

- [x] **4b. Extract MENTIONS relationships from body text**
  New file `graph/mention_extractor.py` — after relationship building, scan each entity's markdown body for references to other known entity titles. For each hit, `MERGE (source)-[:MENTIONS]->(target)`. Use the existing entity title index for lookup. Checkpoint-gated.

- [x] **4c. Wire mention extractor into main pipeline**
  `main.py` — add as Step 7 after relationship building.

### Phase 4 — Completed Summary

**Files changed:** `graph/loader.py`, `graph/mention_extractor.py` (new), `main.py`

**4a — Infobox properties (`graph/loader.py`):**
- New `_sanitise_infobox()` helper converts raw infobox keys to safe Neo4j property names: lowercased, non-alphanumeric runs replaced with `_`, leading/trailing underscores stripped.
- Values are coerced to `str` unless already `bool`, `int`, `float`, or `list`, preventing mixed-type Neo4j errors.
- New `_SET_INFOBOX` Cypher template uses `SET n += $props` which merges properties without overwriting unrelated ones.
- In `load_graph()` pass 1, after the core `MERGE`/`SET`, the infobox dict is sanitised and written with a second query. Skipped if `infobox` is empty.

**4b — Mention extractor (`graph/mention_extractor.py`):**
- On startup, fetches all `(id, title)` pairs from Neo4j via a single `MATCH (n) WHERE n.id IS NOT NULL` query.
- Titles shorter than 4 characters are excluded to reduce false positives.
- Lookup list is sorted longest-title-first so multi-word names (e.g. `"Albert Wesker"`) match before their substrings (`"Wesker"`).
- Each title is compiled into a `re.compile(r"\b" + re.escape(title) + r"\b", re.IGNORECASE)` pattern for whole-word matching.
- For each source entity body, every pattern is tested; matching titles that aren't the entity itself get a `MERGE (source)-[:MENTIONS]->(target)`.
- `IngestCheckpoint("mention_extractor")` gates per `entity_id` with phase `"mentions"`.

**4c — Pipeline wiring (`main.py`):**
- All step labels updated from `/6` to `/7`.
- Step 7/7 calls `extract_mentions()` and logs its summary.
- Final log line extended with `Mentions: %s`.

**To take effect:** delete `data/state/graph_loader.json` and `data/state/mention_extractor.json` (if they exist) and re-run the ingestor. No re-scrape needed.

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
