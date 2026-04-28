from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    labels: list[str]
    name: str = ""
    entity_type: str = ""


class GraphEdge(BaseModel):
    source: str
    type: str
    target: str


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
