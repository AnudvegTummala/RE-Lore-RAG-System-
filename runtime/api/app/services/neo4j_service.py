from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import settings


class Neo4jService:
    _driver: AsyncDriver | None = None

    def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._driver

    async def run(self, cypher: str, **params) -> list[dict]:
        driver = self._get_driver()
        async with driver.session() as session:
            result = await session.run(cypher, **params)
            return [dict(record) async for record in result]

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None


neo4j_service = Neo4jService()
