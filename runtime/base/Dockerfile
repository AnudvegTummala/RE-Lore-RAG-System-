# syntax=docker/dockerfile:1
FROM python:3.11-slim

# TORCH_DEVICE controls which torch wheel is installed:
#   auto  — detects NVIDIA GPU via nvidia-smi; falls back to CPU (default)
#   cpu   — force CPU-only wheel (~250 MB, no CUDA deps)
#   cuda  — force CUDA wheel (~1.5 GB, full nvidia stack)
#
# Mac (Apple Silicon) with Docker Desktop runs a Linux VM — MPS is not
# available inside containers, so "auto" correctly resolves to "cpu".
ARG TORCH_DEVICE=auto

WORKDIR /app

# System deps needed by both api and clip-service
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    libgl1 \
    libglib2.0-0t64 \
    && rm -rf /var/lib/apt/lists/*

# Install torch with device-appropriate wheel, then remaining heavy deps.
# The pip cache mount avoids re-downloading wheels on subsequent builds.
COPY requirements-base.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    VARIANT="${TORCH_DEVICE}"; \
    if [ "$VARIANT" = "auto" ]; then \
        if nvidia-smi > /dev/null 2>&1; then \
            VARIANT="cuda"; \
        else \
            VARIANT="cpu"; \
        fi; \
    fi; \
    echo "Installing torch variant: $VARIANT"; \
    if [ "$VARIANT" = "cpu" ]; then \
        pip install torch==2.6.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu; \
    else \
        pip install "torch>=2.6.0"; \
    fi && \
    pip install -r requirements-base.txt

# Pre-warm models so container startup is fast (layers cached independently)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" && \
    python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')" && \
    python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')"
