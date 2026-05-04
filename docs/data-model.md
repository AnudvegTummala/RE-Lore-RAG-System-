# Data Model

## Knowledge Graph (Neo4j)

### Node Labels

All entity nodes carry a core set of properties. In addition, any infobox fields scraped from the wiki (e.g. `height`, `blood_type`, `nationality`, `status`, `affiliation`) are written as individual node properties during ingest — keys are sanitised to lowercase with underscores. These properties vary by entity and by how complete the wiki page is.

| Label | Core Properties |
|---|---|
| `Character` | `id`, `title`, `source_url` |
| `Game` | `id`, `title`, `release_year`, `source_url` |
| `Enemy` | `id`, `title`, `source_url` |
| `Virus` | `id`, `title`, `source_url` |
| `Organization` | `id`, `title`, `source_url` |
| `Location` | `id`, `title`, `source_url` |
| `Weapon` | `id`, `title`, `source_url` |
| `ConceptArt` | `id`, `entity_id`, `entity_type`, `image_path`, `caption`, `section`, `width`, `height` |
| `LoreChunk` | `id`, `text`, `section` |
| `TimelineEvent` | `id`, `name`, `year`, `description` |

### Relationships

| Relationship | From | To | Description |
|---|---|---|---|
| `APPEARS_IN` | Character / Enemy | Game | Entity appears in this game |
| `MEMBER_OF` | Character | Organization | Character is a member |
| `ENCOUNTERS` | Character | Enemy | Character encounters this enemy |
| `INFECTED_WITH` | Character / Enemy | Virus | Entity infected with virus |
| `CREATED_BY` | Virus / Enemy | Organization | Created/engineered by org |
| `LOCATED_IN` | Event / Game | Location | Takes place at location |
| `FEATURED_IN` | Location | Game | Location features in game |
| `HAS_IMAGE` | Any entity | ConceptArt | Entity has associated concept art image |
| `DESCRIBED_IN` | Character / Enemy / Location | LoreChunk | Entity described in chunk |
| `MENTIONS` | Any entity | Any entity | Body text co-reference — source entity's markdown body mentions target entity by name |
| `PRECEDES` | TimelineEvent | TimelineEvent | Chronological ordering |
| `SUCCEEDS` | TimelineEvent | TimelineEvent | Chronological ordering |

`MENTIONS` edges are created by `graph/mention_extractor.py` during ingest. It scans each entity's markdown body for references to other known entity titles using whole-word regex matching, sorted longest-title-first to prefer multi-word names over substrings.

Note: the relationship is named `HAS_IMAGE` in the code (not `HAS_CONCEPT_ART` as in earlier planning documents).

---

## Vector Collections (Qdrant)

### `lore_text`

Hybrid named-vector collection. Each point stores two vectors:

| Named vector | Model | Dimensions | Type |
|---|---|---|---|
| `"dense"` | `all-MiniLM-L6-v2` (sentence-transformers) | 384 | Dense float |
| `"sparse"` | `Qdrant/bm25` (fastembed pre-fitted) | variable | Sparse (indices + values) |

At query time, Qdrant's `query_points` fetches candidates from both vectors independently and fuses the ranked lists using RRF (Reciprocal Rank Fusion). This hybrid approach gives semantic similarity from the dense vector and exact token matching from BM25 — important for RE-domain proper nouns like BSAA, S.T.A.R.S., T-Abyss that dense embeddings handle poorly.

**Payload fields:** `chunk_id`, `entity_id`, `entity_type`, `title`, `section`, `source_file`, `source_url`, `tags`, `chunk_text` (child chunk, what was embedded), `parent_text` (full section up to 1500 chars, what is returned to the LLM)

**Chunking strategy:** hierarchical parent-child with sentence-level overlap. Each markdown section becomes a parent (≤1500 chars). Each parent is sub-split into children (≤400 chars) at sentence boundaries, with the last sentence of each child carried forward as overlap into the next. The child is embedded; the parent is stored in the payload and returned at query time for full-context generation.

**Keyword index on `entity_id`** — for efficient filtered search during graph-anchored retrieval.

### `concept_art`

Dense CLIP vector collection.

| Model | Dimensions |
|---|---|
| OpenCLIP `ViT-B-32` | 512 |

**Payload fields:** `image_id`, `entity_id`, `entity_type`, `image_path`, `caption`, `section`, `width`, `height`, `tags`

`caption` prefers real figure caption text (from `<figcaption>` / `.thumbcaption`) over the raw `alt_text` attribute. `section` is the article heading the image appeared under (e.g. `"Appearance"`, `"History"`); infobox images are tagged `"Infobox"`.

**Keyword index on `entity_id`** — image retrieval filters by entity_ids from text results to prevent wrong-character image matches.

---

## Markdown Corpus Format

Each scraped entity page becomes one markdown file under `data/raw/markdown/{category}/`.

```yaml
---
id: character-leon-s-kennedy
entity_type: character
title: Leon S. Kennedy
source_name: Resident Evil Wiki
source_url: https://residentevil.fandom.com/wiki/Leon_S._Kennedy
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
infobox:
  status: Active
  nationality: American
  occupation: Government Agent
---

# Leon S. Kennedy

## Summary
...

## Biography
...
```

### Chunk Payload (Qdrant `lore_text` point)

```json
{
  "chunk_id": "character-leon-s-kennedy_biography_001",
  "entity_id": "character-leon-s-kennedy",
  "entity_type": "character",
  "title": "Leon S. Kennedy",
  "section": "Biography",
  "source_file": "data/raw/markdown/characters/leon-s-kennedy.md",
  "source_url": "https://residentevil.fandom.com/wiki/Leon_S._Kennedy",
  "tags": ["protagonist", "rpd"],
  "chunk_text": "Leon S. Kennedy — Biography: Leon was recruited by...",
  "parent_text": "Leon S. Kennedy — Biography: Leon was recruited by the RPD after graduating... [full section up to 1500 chars]"
}
```

The `chunk_text` field (child, ≤400 chars with contextual prefix) is what gets embedded and indexed. The `parent_text` field (full section, ≤1500 chars) is returned to the LLM at query time — this is the "parent-child retrieval" pattern: precise retrieval, full-context generation.
