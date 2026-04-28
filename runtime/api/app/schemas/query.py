from pydantic import BaseModel

from app.schemas.source import Source
from app.schemas.graph import GraphPayload


class QueryRequest(BaseModel):
    query: str


class ImageResult(BaseModel):
    image_id: str
    path: str
    caption: str = ""


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    images: list[ImageResult]
    graph: GraphPayload
