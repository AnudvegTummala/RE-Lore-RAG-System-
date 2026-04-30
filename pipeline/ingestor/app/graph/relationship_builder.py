"""Relationship builder — pass 2 of the graph loader.

Wires all edges between entity nodes. The builder is *lenient*: if the
target node doesn't exist yet (e.g. a game referenced by a character that
hasn't been scraped), it creates a minimal stub node so the edge can be
stored. Stub nodes are filled in when their category is eventually ingested.

Relationship types built here:
  APPEARS_IN      — any entity → Game  (from frontmatter.related_games)
  LOCATED_IN      — Character/Enemy/Event → Location  (infobox "location")
  MEMBER_OF       — Character → Organization  (infobox "organization")
  CREATED_BY      — Virus/Weapon/Enemy → Organization  (infobox "creator" / "created by")
  INFECTED_BY     — Character/Enemy → Virus  (infobox "virus" / "parasite")
  USES_WEAPON     — Character → Weapon  (infobox "weapons")
  PART_OF         — Location → Location  (infobox "region" / "part of")
  ALLIED_WITH     — Character ↔ Character  (infobox "allies")
  ENEMY_OF        — Character ↔ Character  (infobox "enemies")
  RELATED_TO      — any entity → any entity  (fallback for infobox links)
"""

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import AsyncDriver

from app.utils.checkpoint import IngestCheckpoint

logger = logging.getLogger(__name__)

# Maps infobox label keywords → (relationship_type, target_entity_type, target_label)
# Checked in order; first match wins.
_INFOBOX_RULES: list[tuple[tuple[str, ...], str, str, str]] = [
    # keywords                            rel_type      entity_type   Neo4j label
    (("location", "located", "area"),    "LOCATED_IN",  "location",   "Location"),
    (("organization", "affiliation",
      "affiliated", "faction"),          "MEMBER_OF",   "organization","Organization"),
    (("creator", "created by",
      "manufacturer", "developer"),      "CREATED_BY",  "organization","Organization"),
    (("virus", "parasite", "progenitor",
      "infection", "infected"),          "INFECTED_BY", "virus",       "Virus"),
    (("weapon", "weapons", "armed",
      "equipment", "arms"),              "USES_WEAPON", "weapon",      "Weapon"),
    (("region", "part of", "within",
      "district", "sector"),             "PART_OF",     "location",    "Location"),
    (("allies", "ally", "partner"),      "ALLIED_WITH", "character",   "Character"),
    (("enemies", "enemy", "rival",
      "antagonist"),                     "ENEMY_OF",    "character",   "Character"),
]

_MERGE_STUB = (
    "MERGE (n:{label} {{id: $id}}) "
    "ON CREATE SET n.title = $title, n.entity_type = $entity_type, n.stub = true"
)

_MERGE_REL = (
    "MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
    "MERGE (a)-[:{rel_type}]->(b)"
)

_MERGE_APPEARS_IN = (
    "MATCH (a {{id: $from_id}}) "
    "MERGE (g:Game {{id: $to_id}}) "
    "  ON CREATE SET g.title = $game_title, g.entity_type = 'game', g.stub = true "
    "MERGE (a)-[:APPEARS_IN]->(g)"
)


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


class RelationshipBuilder:
    def __init__(self, driver: "AsyncDriver", checkpoint: IngestCheckpoint) -> None:
        self._driver = driver
        self._checkpoint = checkpoint

    async def run(self, docs: list[dict]) -> int:
        """Process all docs and return total relationships created."""
        total = 0
        async with self._driver.session() as session:
            for doc in docs:
                fm = doc.get("frontmatter", {})
                entity_id = fm.get("id")
                if not entity_id:
                    continue
                if self._checkpoint.is_done(entity_id, phase="relationships"):
                    continue
                try:
                    count = await self._wire(session, fm)
                    total += count
                    self._checkpoint.mark_done(entity_id, phase="relationships")
                except Exception:
                    logger.exception("Relationship build failed for %s", entity_id)

        logger.info("Relationship builder: %d relationships created across %d docs", total, len(docs))
        return total

    async def _wire(self, session, fm: dict) -> int:
        entity_id = fm["id"]
        count = 0

        # APPEARS_IN — from related_games list in frontmatter
        for game_slug in fm.get("related_games", []):
            game_id = f"game-{game_slug}" if not game_slug.startswith("game-") else game_slug
            game_title = game_slug.replace("-", " ").title()
            try:
                await session.run(
                    _MERGE_APPEARS_IN,
                    from_id=entity_id,
                    to_id=game_id,
                    game_title=game_title,
                )
                count += 1
            except Exception:
                logger.debug("APPEARS_IN failed: %s -> %s", entity_id, game_id)

        # Infobox-derived relationships
        infobox: dict = fm.get("infobox", {})
        for label, value in infobox.items():
            label_lower = label.lower()
            rel_type, target_entity_type, target_label = self._match_rule(label_lower)
            if not rel_type:
                continue

            for target_name in _split_values(value):
                target_id = f"{target_entity_type}-{_slug(target_name)}"
                try:
                    # Ensure stub exists
                    await session.run(
                        _MERGE_STUB.format(label=target_label),
                        id=target_id,
                        title=target_name,
                        entity_type=target_entity_type,
                    )
                    await session.run(
                        _MERGE_REL.format(rel_type=rel_type),
                        from_id=entity_id,
                        to_id=target_id,
                    )
                    count += 1
                except Exception:
                    logger.debug("%s failed: %s -> %s", rel_type, entity_id, target_id)

        return count

    def _match_rule(self, label_lower: str) -> tuple[str, str, str]:
        """Return (rel_type, entity_type, neo4j_label) for the first matching rule, or ('','','')."""
        for keywords, rel_type, entity_type, neo4j_label in _INFOBOX_RULES:
            if any(kw in label_lower for kw in keywords):
                return rel_type, entity_type, neo4j_label
        return "", "", ""


def _split_values(value: str) -> list[str]:
    """Split a comma- or newline-separated infobox value into individual names."""
    parts = re.split(r"[,\n]+", value)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]
