import asyncio
import contextlib
import logging
from typing import List, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from src.core.config import settings
from src.db.db_client import db_client
from src.services.indexer import AsyncIndexer
from src.services.watcher import DirectoryWatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# Global dependencies
model: SentenceTransformer = None
indexer: AsyncIndexer = None
watcher: DirectoryWatcher = None
indexer_task: asyncio.Task = None

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global model, indexer, watcher, indexer_task
    
    # Startup
    logger.info("Initializing Neural-Memex Daemon...")
    
    # 1. Load Model (Singleton)
    logger.info(f"Loading Model: {settings.MODEL_NAME}")
    model = SentenceTransformer(settings.MODEL_NAME)
    
    # 2. Init Indexer
    indexer = AsyncIndexer(model=model)
    indexer_task = asyncio.create_task(indexer.start())
    
    # 3. Init Watcher
    watcher = DirectoryWatcher(indexer)
    watcher.start()
    
    logger.info("Daemon Ready.")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    watcher.stop()
    await indexer.stop()
    if indexer_task:
        indexer_task.cancel()
        try:
            await indexer_task
        except asyncio.CancelledError:
            pass
    logger.info("Shutdown complete.")


app = FastAPI(title="Neural-Memex Daemon", lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str
    n_results: int = 10

class SearchResult(BaseModel):
    filename: str
    path: str
    score: float
    extension: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/search", response_model=List[SearchResult])
def search(request: SearchRequest):
    if not model:
        raise HTTPException(status_code=503, detail="Model not loaded")
        
    try:
        # Generate embedding
        embedding = model.encode(request.query).tolist()
        
        # Query DB
        collection = db_client.get_collection()
        results = collection.query(
            query_embeddings=[embedding],
            n_results=request.n_results,
            include=["metadatas", "distances"]
        )
        
        # Format results
        output = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                meta = results["metadatas"][0][i]
                dist = results["distances"][0][i]
                # Convert distance to similarity score
                score = 1.0 - dist
                
                output.append(SearchResult(
                    filename=meta.get("filename", "unknown"),
                    path=meta.get("path", "unknown"),
                    score=score,
                    extension=meta.get("extension", "")
                ))
        
        return output

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=False)
