import logging
import os

from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

_LABEL_MAP = {
    "character": "Character",
    "game": "Game",
    "enemy": "Enemy",
    "location": "Location",
    "organization": "Organization",
    "virus": "Virus",
    "timeline": "TimelineEvent",
}

_MERGE_NODE = "MERGE (n:{label} {{id: $id}}) SET n += $props"
_MERGE_APPEARS_IN = (
    "MATCH (c {{id: $char_id}}), (g:Game {{id: $game_id}}) "
    "MERGE (c)-[:APPEARS_IN]->(g)"
)


async def build_relationships(entity: dict) -> None:
    label = _LABEL_MAP.get(entity["entity_type"], "Entity")
    props = {
        "id": entity["id"],
        "name": entity["title"],
        "source_url": entity["source_url"],
    }

    async with AsyncGraphDatabase.driver(
        _NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD)
    ) as driver:
        async with driver.session() as session:
            await session.run(_MERGE_NODE.format(label=label), id=entity["id"], props=props)

            for game_id in entity.get("related_games", []):
                try:
                    await session.run(
                        _MERGE_APPEARS_IN,
                        char_id=entity["id"],
                        game_id=f"game-{game_id}",
                    )
                except Exception:
                    logger.debug("Could not link %s -> %s", entity["id"], game_id)
