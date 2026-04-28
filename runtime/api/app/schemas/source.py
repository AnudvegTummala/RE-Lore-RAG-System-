from pydantic import BaseModel


class Source(BaseModel):
    entity_id: str
    title: str
    section: str = ""
    snippet: str = ""
    source_url: str = ""
