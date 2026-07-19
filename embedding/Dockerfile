# macOS Apple Silicon / Docker Desktop: CPU image đa kiến trúc (linux/arm64).
# PyTorch CPU được cài từ PyTorch CPU index ở bên dưới.
FROM python:3.11-slim

# Intel x86_64 + NVIDIA GPU: bỏ comment dòng dưới và comment FROM CPU ở trên.
# FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# macOS Apple Silicon: dùng PyTorch CPU (không yêu cầu CUDA/NVIDIA runtime).
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir fastapi uvicorn "sentence-transformers<3.0.0" "transformers<4.41.0"

# Intel x86_64 + NVIDIA GPU: bỏ comment dòng dưới khi đã dùng CUDA base image.
# RUN pip install --no-cache-dir fastapi uvicorn "sentence-transformers<3.0.0" "transformers<4.41.0"

# Pre-download model weights to the cache directory during image build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('dangvantuan/vietnamese-embedding')"

# Copy server code
COPY server.py .

ENV PORT=7997
ENV EMBEDDING_MODEL_NAME=dangvantuan/vietnamese-embedding

EXPOSE 7997

CMD ["python", "server.py"]
