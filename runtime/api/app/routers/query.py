import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.graph.state import GraphState
from app.graph.workflow import compiled_graph

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    query: str


async def _stream_response(query: str):
    initial_state: GraphState = {
        "query": query,
        "entity_hints": [],
        "needs_image_search": False,
        "graph_results": [],
        "text_results": [],
        "image_results": [],
        "evidence": "",
        "answer": "",
        "retrieval_adequate": False,
    }

    final_state: GraphState | None = None

    async for event in compiled_graph.astream_events(initial_state, version="v2"):
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            if chunk and chunk.content:
                yield f"data: {json.dumps({'token': chunk.content})}\n\n"
        elif kind == "on_chain_end" and event.get("name") == "LangGraph":
            final_state = event["data"].get("output")

    if final_state:
        payload = {
            "done": True,
            "answer": final_state.get("answer", ""),
            "sources": final_state.get("text_results", []),
            "images": final_state.get("image_results", []),
            "graph": {
                "nodes": [],
                "edges": [],
            },
        }
        yield f"data: {json.dumps(payload)}\n\n"


@router.post("/query")
async def query_endpoint(body: QueryRequest):
    return StreamingResponse(
        _stream_response(body.query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
