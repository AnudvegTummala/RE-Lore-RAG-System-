# Demo Script

## Setup

1. `cp .env.example .env` — fill in `GROQ_API_KEY` and `NEO4J_PASSWORD`
2. `bash scripts/pipeline-run.sh` — scrape and ingest corpus
3. `bash scripts/runtime-up.sh` — start services
4. Open [http://localhost:3000](http://localhost:3000)

## Verification Checklist

Before demo:
- [ ] All containers healthy: `docker compose ps`
- [ ] Health endpoint returns `"status": "ok"`: `curl http://localhost:8000/health`
- [ ] Neo4j browser accessible: http://localhost:7474
- [ ] Qdrant dashboard accessible: http://localhost:6333/dashboard

## Demo Queries

### Text-only path (must NOT show concept art, `needs_image_search=False`)

1. **"Who is connected to Umbrella through both direct employment and outbreak events?"**
   - Expected: Answer citing Wesker, Birkin, etc. Sources panel populated. Graph shows Umbrella org cluster.

2. **"Which games connect Leon S. Kennedy and Ada Wong?"**
   - Expected: RE2, RE4 cited. Graph shows APPEARS_IN edges.

3. **"What enemies are related to Tyrant lineage?"**
   - Expected: Mr. X, Nemesis, G cited. No image gallery shown.

### Image search path (MUST show concept art, `needs_image_search=True`)

4. **"What does Jill Valentine look like across different games?"**
   - Expected: Answer describes visual evolution. Image gallery renders concept art.

5. **"Which concept art items relate to Nemesis, and what descriptive lore is attached?"**
   - Expected: Concept art images shown. Lore citations in sources panel.

6. **"What locations are most associated with the Raccoon City outbreak?"**
   - Expected: RPD, Spencer Mansion, sewers cited with images if scraped.

## Talking Points

- **LangGraph**: Stateful graph — each node reads/writes `GraphState`. Conditional edge skips CLIP for text queries.
- **Dual retrieval**: Graph traversal (structured relationships) + vector search (semantic lore chunks) combined before LLM call.
- **Streaming**: Tokens stream token-by-token via SSE; no wait for full response.
- **Grounding**: LLM is given only retrieved evidence — reduces hallucination risk.
