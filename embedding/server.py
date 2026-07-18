import logging
import os
from typing import List, Union
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embedding-service")

app = FastAPI(title="SmartGov Embedding Service")

# Model configuration
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "dangvantuan/vietnamese-embedding")
PORT = int(os.getenv("PORT", "7997"))

# Select device
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Loading model '{MODEL_NAME}' on device: {device}...")

try:
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info("Model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    raise e

# Pydantic models for OpenAI compatibility
class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = Field(default=MODEL_NAME)

class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: List[float]

class EmbeddingUsage(BaseModel):
    prompt_tokens: int = 0
    total_tokens: int = 0

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage

@app.get("/")
def read_root():
    return {
        "message": "SmartGov Local Embedding Service",
        "model": MODEL_NAME,
        "device": device
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "device": device}

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
@app.post("/embeddings", response_model=EmbeddingResponse)
def create_embeddings(request: EmbeddingRequest):
    # Standardize input to list of strings
    if isinstance(request.input, str):
        inputs = [request.input]
    elif isinstance(request.input, list):
        inputs = request.input
    else:
        raise HTTPException(status_code=400, detail="Input must be a string or a list of strings")

    try:
        # Generate embeddings
        # dangvantuan/vietnamese-embedding outputs 768-dimensional vectors
        embeddings = model.encode(inputs, convert_to_numpy=True)
        
        data_items = []
        for idx, emb in enumerate(embeddings):
            data_items.append(
                EmbeddingData(
                    index=idx,
                    embedding=emb.tolist()
                )
            )
        
        # Simple estimate of tokens or just keep it 0 as placeholder
        total_chars = sum(len(text) for text in inputs)
        estimated_tokens = int(total_chars / 4) # Rough approximation
        
        return EmbeddingResponse(
            data=data_items,
            model=request.model,
            usage=EmbeddingUsage(
                prompt_tokens=estimated_tokens,
                total_tokens=estimated_tokens
            )
        )
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
