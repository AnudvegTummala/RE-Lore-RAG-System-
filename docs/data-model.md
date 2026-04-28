# Data Model

## Knowledge Graph (Neo4j)

### Node Labels

| Label | Key Properties |
|---|---|
| `Character` | `id`, `name`, `source_url` |
| `Game` | `id`, `name`, `release_year`, `source_url` |
| `Enemy` | `id`, `name`, `source_url` |
| `Virus` | `id`, `name`, `source_url` |
| `Organization` | `id`, `name`, `source_url` |
| `Location` | `id`, `name`, `source_url` |
| `ConceptArt` | `id`, `image_path`, `caption` |
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
| `HAS_CONCEPT_ART` | Character / Enemy | ConceptArt | Has associated concept art |
| `DESCRIBED_IN` | Character / Enemy / Location | LoreChunk | Entity described in chunk |
| `PRECEDES` | TimelineEvent | TimelineEvent | Chronological ordering |
| `SUCCEEDS` | TimelineEvent | TimelineEvent | Chronological ordering |

## Vector Collections (Qdrant)

### `lore_text`

Sentence-transformer embeddings (`all-MiniLM-L6-v2`, dim=384).

Payload: `chunk_id`, `entity_id`, `entity_type`, `title`, `section`, `source_file`, `source_url`, `tags`, `text`

### `concept_art`

OpenCLIP embeddings (`ViT-B-32`, dim=512).

Payload: `entity_id`, `entity_type`, `image_path`, `caption`, `tags`

## Markdown Corpus Format

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
---

# Leon S. Kennedy

## Summary
...
```

### Chunk Metadata

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
  "text": "..."
}
```
