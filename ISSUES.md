# Known Issues & Pending Tasks

## Bugs

### ~~[HIGH] Game lore and movie lore are mixed in the corpus~~ — RESOLVED

**Resolved in:** `feat(scraper): filter non-game-canon pages from Fandom BFS`

Two-layer filtering added to `pipeline/scraper/app/scrapers/fandom.py`:
1. `_EXCLUDED_SUBCATEGORIES` — BFS guard skips entire subtrees for Anderson films, DeCandido/Perry novels, WildStorm comics, Monolith Soft crossovers, and Welcome to Raccoon City. Category names verified against the live wiki API.
2. `_EXCLUDED_ARTICLE_CATEGORIES` — article-level intersection check after HTML fetch catches pages that appear in both a game and a film/novel category.

A full re-scrape is required to apply the fix to the corpus.

---

### [MEDIUM] Knowledge graph panel may not render on first query after page load

**Symptom:** After a hard refresh, the knowledge graph `<aside>` panel is conditionally mounted only when `activeGraph` is non-null (Shell.tsx). On the first query the graph panel mounts for the first time; Cytoscape may not resize correctly into the new container before `cy.fit()` is called.

**Status:** Partially addressed — `cy.resize()` is called before layout, and `animate: false` was added so layout is synchronous. Not fully verified after the Shell.tsx conditional rendering change was merged.

**Proposed fix:** Wrap the Cytoscape init in a `ResizeObserver` callback (or a `useLayoutEffect` with a short `requestAnimationFrame`) so it fires after the container has been painted with its real dimensions.

---

### ~~[LOW] Scraped files have empty `tags: []` frontmatter~~ — RESOLVED

**Resolved in:** prior scraper work (prop=categories fix, already merged to main).

Tags are now populated from `api.php?action=parse&prop=categories` on every scrape. A full re-scrape is required to backfill existing files — this is being done as part of the film lore fix re-scrape.

---

## Pending Tasks

### ~~[FEATURE] Separate or exclude film/movie universe lore from the pipeline~~ — DONE

Implemented via `_EXCLUDED_SUBCATEGORIES` and `_EXCLUDED_ARTICLE_CATEGORIES` in the Fandom scraper. Re-scrape in progress.

---

### [FEATURE] Deployment

The user asked about deploying on Dokploy. No decision has been made. Considerations:

- The CLIP service requires ~2–3 min cold-start for model load; Dokploy health-check timeouts may need extending.
- Qdrant and Neo4j require persistent volumes; confirm Dokploy supports named volume mounts.
- The free tier of most PaaS providers has memory constraints — CLIP + Neo4j + Qdrant + API may exceed them. A VPS (e.g. Hetzner CX22) running Dokploy is the more practical option.

---

### [CHORE] Verify ingestor checkpoint sync after any volume wipe

Any time `scripts/reset-db.sh` is run (wipes Neo4j and Qdrant volumes), the following checkpoint files must be deleted before re-running the ingestor, otherwise it will skip all work:

```
data/state/graph_loader.json
data/state/text_embedder.json
data/state/image_embedder.json
```
