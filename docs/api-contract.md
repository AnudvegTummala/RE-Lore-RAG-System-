# API Contract

Base URL: `http://localhost:8000`

## Endpoints

### `GET /health`

Returns status of all dependent services.

```json
{
  "status": "ok",
  "services": {
    "neo4j": "ok",
    "qdrant": "ok",
    "clip_service": "ok"
  }
}
```

---

### `POST /query`

Invoke the LangGraph pipeline. Streams tokens via Server-Sent Events.

**Request:**
```json
{ "query": "Who is connected to Umbrella?" }
```

**SSE stream:**
```
data: {"token": "Umbrella"}
data: {"token": " Corporation"}
...
data: {
  "done": true,
  "answer": "...",
  "sources": [...],
  "images": [...],
  "graph": {"nodes": [...], "edges": [...]}
}
```

**Source object:**
```json
{
  "entity_id": "character-leon-s-kennedy",
  "title": "Leon S. Kennedy",
  "section": "Biography",
  "snippet": "...",
  "source_url": "https://..."
}
```

**Image object:**
```json
{
  "image_id": "leon-concept-02",
  "path": "/assets/leon-concept-02.jpg",
  "caption": "Early concept art"
}
```

---

### `GET /graph/{entity_id}`

Returns a 2-hop subgraph centred on `entity_id`.

```json
{
  "nodes": [
    {"id": "...", "labels": ["Character"], "name": "Leon S. Kennedy"}
  ],
  "edges": [
    {"source": "...", "type": "APPEARS_IN", "target": "..."}
  ]
}
```

---

### `GET /search?q={query}`

Keyword search for entity lookup (top-10).

```json
{
  "results": [
    {"entity_id": "...", "title": "...", "section": "...", "text": "..."}
  ]
}
```

---

### `GET /entity/{entity_id}`

Full entity detail from Qdrant payload.

```json
{
  "entity_id": "character-leon-s-kennedy",
  "entity_type": "character",
  "title": "Leon S. Kennedy",
  "source_url": "..."
}
```
