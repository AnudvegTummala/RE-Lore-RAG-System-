import httpx
from fastapi import APIRouter
from neo4j import AsyncGraphDatabase

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    status: dict[str, str] = {}

    # Neo4j
    try:
        async with AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        ) as driver:
            await driver.verify_connectivity()
        status["neo4j"] = "ok"
    except Exception as e:
        status["neo4j"] = f"error: {e}"

    # Qdrant
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.qdrant_url}/readyz")
            status["qdrant"] = "ok" if r.is_success else f"error: {r.status_code}"
    except Exception as e:
        status["qdrant"] = f"error: {e}"

    # CLIP service
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.clip_service_url}/health")
            status["clip_service"] = "ok" if r.is_success else f"error: {r.status_code}"
    except Exception as e:
        status["clip_service"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in status.values()) else "degraded"
    return {"status": overall, "services": status}
