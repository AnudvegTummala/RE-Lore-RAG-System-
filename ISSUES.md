# Known Issues & Pending Tasks

## Bugs

### [HIGH] Game lore and movie lore are mixed in the corpus

**Symptom:** When querying for characters like Alice, Leon, or Claire, the RAG system returns lore from both the video game canon and the Paul W.S. Anderson film series (and/or the 2021 Netflix CG series). This produces contradictory or confusing answers — e.g., Alice does not exist in the game canon at all, and characters like Leon behave differently across media.

**Root cause:** The wiki scraper fetches pages from the Resident Evil Fandom wiki, which contains articles for both the game/main-canon universe and the film/alternate-universe characters without strict separation. Both sets of articles are ingested into the same `lore_text` Qdrant collection, so a query can surface game and movie content together with no distinction.

**Proposed fixes (pick one or combine):**
1. **Filter at scrape time** — During scraping, skip any wiki page that belongs to a film-universe category (e.g. `Film_universe_characters`, `Anderson_film_series`). Add these category slugs to a `EXCLUDED_CATEGORIES` blocklist in `pipeline/scraper/app/base_scraper.py` before the next scrape run.
2. **Filter at ingest time** — Check the `tags` frontmatter field in each markdown file. If it contains film-related tags, skip the file in `pipeline/ingestor/app/loaders/markdown_loader.py`.
3. **Add a `canon` metadata field** — Tag each chunk's Qdrant payload with `canon: "game"` or `canon: "film"`, then pass a query-time filter to restrict retrieval to `game` canon only. Requires a re-scrape and re-ingest.

**Note:** The current scrape predates the `prop=categories` fix (tags were empty on the first run), so existing markdown files may not have the category tags needed for option 2. A targeted re-scrape of film-universe categories would be needed first.

---

### [MEDIUM] Knowledge graph panel may not render on first query after page load

**Symptom:** After a hard refresh, the knowledge graph `<aside>` panel is conditionally mounted only when `activeGraph` is non-null (Shell.tsx). On the first query the graph panel mounts for the first time; Cytoscape may not resize correctly into the new container before `cy.fit()` is called.

**Status:** Partially addressed — `cy.resize()` is called before layout, and `animate: false` was added so layout is synchronous. Not fully verified after the Shell.tsx conditional rendering change was merged.

**Proposed fix:** Wrap the Cytoscape init in a `ResizeObserver` callback (or a `useLayoutEffect` with a short `requestAnimationFrame`) so it fires after the container has been painted with its real dimensions.

---

### [LOW] Scraped files have empty `tags: []` frontmatter

**Symptom:** All markdown files scraped before the `prop=categories` fix have empty `tags: []`. Category-based filtering (e.g. to separate film lore) will not work on these files without a re-scrape.

**Fix:** Re-run the scraper. It supports checkpointing — delete `data/raw/manifests/scrape_manifest.json` (or the relevant per-category checkpoint) and run:
```bash
docker compose -f pipeline/docker-compose.yml run --rm scraper
```

---

## Pending Tasks

### [FEATURE] Separate or exclude film/movie universe lore from the pipeline

Depends on the fix chosen for the lore-mixing bug above. Recommended approach:

1. Add `EXCLUDED_CATEGORIES` list to the scraper config.
2. Re-scrape to regenerate markdown with correct tags.
3. Re-run ingestor against fresh Neo4j + Qdrant volumes (`bash scripts/reset-db.sh`).

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
