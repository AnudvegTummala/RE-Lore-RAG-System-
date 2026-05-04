import logging
import os

from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Uniqueness constraints (also create an implicit index on the property).
_CONSTRAINTS = [
    "CREATE CONSTRAINT character_id IF NOT EXISTS FOR (n:Character) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT game_id IF NOT EXISTS FOR (n:Game) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT enemy_id IF NOT EXISTS FOR (n:Enemy) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (n:Location) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT organization_id IF NOT EXISTS FOR (n:Organization) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT virus_id IF NOT EXISTS FOR (n:Virus) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT weapon_id IF NOT EXISTS FOR (n:Weapon) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT lore_chunk_id IF NOT EXISTS FOR (n:LoreChunk) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT concept_art_id IF NOT EXISTS FOR (n:ConceptArt) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT timeline_event_id IF NOT EXISTS FOR (n:TimelineEvent) REQUIRE n.id IS UNIQUE",
]

# Extra indexes on frequently queried properties (title lookup, tag search).
_INDEXES = [
    "CREATE INDEX character_title IF NOT EXISTS FOR (n:Character) ON (n.title)",
    "CREATE INDEX game_title IF NOT EXISTS FOR (n:Game) ON (n.title)",
    "CREATE INDEX enemy_title IF NOT EXISTS FOR (n:Enemy) ON (n.title)",
    "CREATE INDEX location_title IF NOT EXISTS FOR (n:Location) ON (n.title)",
    "CREATE INDEX organization_title IF NOT EXISTS FOR (n:Organization) ON (n.title)",
    "CREATE INDEX virus_title IF NOT EXISTS FOR (n:Virus) ON (n.title)",
    "CREATE INDEX weapon_title IF NOT EXISTS FOR (n:Weapon) ON (n.title)",
    "CREATE INDEX lore_chunk_entity IF NOT EXISTS FOR (n:LoreChunk) ON (n.entity_id)",
    "CREATE INDEX lore_chunk_section IF NOT EXISTS FOR (n:LoreChunk) ON (n.section)",
    "CREATE INDEX concept_art_entity IF NOT EXISTS FOR (n:ConceptArt) ON (n.entity_id)",
]


async def ensure_schema() -> None:
    async with AsyncGraphDatabase.driver(
        _NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD)
    ) as driver:
        async with driver.session() as session:
            for stmt in _CONSTRAINTS:
                await session.run(stmt)
                logger.debug("Applied constraint: %s", stmt[:60])
            for stmt in _INDEXES:
                await session.run(stmt)
                logger.debug("Applied index: %s", stmt[:60])
    logger.info("Neo4j schema ready — %d constraints, %d indexes", len(_CONSTRAINTS), len(_INDEXES))
