from fastapi import APIRouter, Query, HTTPException

from app.services.qdrant_service import qdrant_service

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(q: str = Query(..., min_length=1)):
    try:
        results = await qdrant_service.search_text(
            query=q,
            collection="lore_text",
            limit=10,
        )
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str):
    try:
        result = await qdrant_service.get_entity(entity_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    return result
