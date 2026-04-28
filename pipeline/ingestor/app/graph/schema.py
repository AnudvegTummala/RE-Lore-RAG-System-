import os
from neo4j import AsyncGraphDatabase

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

_CONSTRAINTS = [
    "CREATE CONSTRAINT character_id IF NOT EXISTS FOR (n:Character) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT game_id IF NOT EXISTS FOR (n:Game) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT enemy_id IF NOT EXISTS FOR (n:Enemy) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (n:Location) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT organization_id IF NOT EXISTS FOR (n:Organization) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT virus_id IF NOT EXISTS FOR (n:Virus) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT lore_chunk_id IF NOT EXISTS FOR (n:LoreChunk) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT concept_art_id IF NOT EXISTS FOR (n:ConceptArt) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT timeline_event_id IF NOT EXISTS FOR (n:TimelineEvent) REQUIRE n.id IS UNIQUE",
]


async def ensure_schema() -> None:
    async with AsyncGraphDatabase.driver(
        _NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD)
    ) as driver:
        async with driver.session() as session:
            for stmt in _CONSTRAINTS:
                await session.run(stmt)
