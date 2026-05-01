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
            "sources": _serialise_sources(final_state.get("text_results", [])),
            "images": _serialise_images(final_state.get("image_results", [])),
            "graph": _serialise_graph(
                final_state.get("graph_results", []),
                final_state.get("text_results", []),
            ),
        }
        yield f"data: {json.dumps(payload)}\n\n"


def _serialise_images(image_results: list) -> list[dict]:
    out = []
    for r in image_results:
        raw_path = r.get("image_path", "")
        # Convert container path /data/raw/images/X → /api/images/X so the
        # browser's request hits the Vite proxy (/api/* → API) and the API's
        # StaticFiles mount serves the file.
        if raw_path.startswith("/data/raw/images/"):
            browser_path = raw_path.replace("/data/raw/images/", "/api/images/", 1)
        else:
            browser_path = raw_path
        out.append({
            "image_id": r.get("image_id", ""),
            "path": browser_path,
            "caption": r.get("caption") or r.get("image_id", ""),
        })
    return out


def _serialise_sources(text_results: list) -> list[dict]:
    out = []
    seen: set[str] = set()
    for r in text_results:
        eid = r.get("entity_id", "")
        if eid in seen:
            continue
        seen.add(eid)
        out.append({
            "entity_id": eid,
            "title": r.get("title", eid),
            "section": r.get("section", ""),
            "snippet": (r.get("parent_text") or r.get("chunk_text") or r.get("text", ""))[:200],
            "source_url": r.get("source_url", ""),
        })
    return out


def _serialise_graph(graph_results: list, text_results: list | None = None) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple] = set()

    for rec in graph_results:
        for node in rec.get("nodes", []):
            try:
                props = dict(node)
                nid = props.get("id") or str(node.element_id)
                if nid not in seen_nodes:
                    seen_nodes.add(nid)
                    nodes.append({
                        "id": nid,
                        "labels": list(node.labels),
                        "name": props.get("title") or props.get("name") or nid,
                        "entity_type": props.get("entity_type", ""),
                    })
            except Exception:
                pass
        for rel in rec.get("relationships", []):
            try:
                key = (str(rel.start_node.element_id), rel.type, str(rel.end_node.element_id))
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({
                        "source": dict(rel.start_node).get("id") or str(rel.start_node.element_id),
                        "type": rel.type,
                        "target": dict(rel.end_node).get("id") or str(rel.end_node.element_id),
                    })
            except Exception:
                pass

    # Fallback: build stub nodes from text_results when Neo4j graph retrieval
    # returned nothing (e.g. query had no capitalised entity hints).
    if not nodes and text_results:
        _LABEL_MAP = {
            "character": "Character", "game": "Game", "enemy": "Enemy",
            "location": "Location", "organization": "Organization",
            "virus": "Virus", "weapon": "Weapon",
        }
        for r in text_results:
            eid = r.get("entity_id", "")
            if not eid or eid in seen_nodes:
                continue
            seen_nodes.add(eid)
            et = r.get("entity_type", "")
            nodes.append({
                "id": eid,
                "labels": [_LABEL_MAP.get(et, "Entity")],
                "name": r.get("title", eid),
                "entity_type": et,
            })

    return {"nodes": nodes, "edges": edges}


@router.post("/query")
async def query_endpoint(body: QueryRequest):
    return StreamingResponse(
        _stream_response(body.query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
