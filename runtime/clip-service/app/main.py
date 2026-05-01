import io
import os

import open_clip
import torch
from fastapi import FastAPI, File, UploadFile
from PIL import Image
from pydantic import BaseModel

app = FastAPI(title="CLIP Embedding Service", version="0.1.0")

_MODEL_NAME = os.getenv("CLIP_MODEL", "ViT-B-32")
_PRETRAINED = os.getenv("CLIP_PRETRAINED", "openai")

_model, _, _preprocess = open_clip.create_model_and_transforms(_MODEL_NAME, pretrained=_PRETRAINED)
_tokenizer = open_clip.get_tokenizer(_MODEL_NAME)
_model.eval()


class TextRequest(BaseModel):
    text: str


@app.get("/health")
async def health():
    return {"status": "ok", "model": _MODEL_NAME}


@app.post("/embed/text")
async def embed_text(body: TextRequest):
    tokens = _tokenizer([body.text])
    with torch.no_grad():
        vector = _model.encode_text(tokens)
        vector = vector / vector.norm(dim=-1, keepdim=True)
    return {"vector": vector[0].tolist()}


@app.post("/embed/image")
async def embed_image(image_bytes: UploadFile = File(...)):
    data = await image_bytes.read()
    image = Image.open(io.BytesIO(data)).convert("RGB")
    tensor = _preprocess(image).unsqueeze(0)
    with torch.no_grad():
        vector = _model.encode_image(tensor)
        vector = vector / vector.norm(dim=-1, keepdim=True)
    return {"vector": vector[0].tolist()}
