import httpx

from app.core.config import settings


class ClipServiceClient:
    async def embed_text(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.clip_service_url}/embed/text",
                json={"text": text},
            )
            response.raise_for_status()
            return response.json()["vector"]

    async def embed_image(self, image_bytes: bytes) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.clip_service_url}/embed/image",
                content=image_bytes,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
            return response.json()["vector"]


clip_client = ClipServiceClient()
