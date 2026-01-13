import asyncio
import hashlib
import logging
from pathlib import Path
from typing import List, Optional

from sentence_transformers import SentenceTransformer
from chromadb.api.models.Collection import Collection

from src.core.config import settings
from src.db.db_client import db_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("indexer")

class AsyncIndexer:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.collection: Collection = db_client.get_collection()
        self.model: Optional[SentenceTransformer] = None
        self._running = False

    def _load_model(self):
        """Lazy load the model to avoid overhead at startup if not needed immediately."""
        if self.model is None:
            logger.info(f"Loading model: {settings.MODEL_NAME}...")
            self.model = SentenceTransformer(settings.MODEL_NAME)
            logger.info("Model loaded.")

    async def start(self):
        """Starts the consumer loop."""
        self._running = True
        logger.info("AsyncIndexer started.")
        while self._running:
            try:
                # Wait for next item
                file_path = await self.queue.get()
                await self._process_file(file_path)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in indexer loop: {e}")

    async def stop(self):
        """Stops the consumer loop."""
        self._running = False
        # Optional: wait for queue to empty? for now just stop.

    async def enqueue_file(self, file_path: Path):
        """Adds a file path to the processing queue."""
        await self.queue.put(file_path)

    async def _process_file(self, file_path: Path):
        """Reads file, embeds content, and updates DB."""
        if not file_path.exists():
             logger.info(f"File deleted: {file_path}, removing from DB.") 
             self._remove_from_db(file_path)
             return

        # Simple text extraction for now
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                return
            
            # Identify file in a stable way
            file_id = str(file_path.absolute())
            
            # Metadata
            metadata = {
                "filename": file_path.name,
                "path": str(file_path.absolute()),
                "extension": file_path.suffix,
                "size": file_path.stat().st_size
            }

            # Run embedding in a thread executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            
            if self.model is None:
                await loop.run_in_executor(None, self._load_model)

            embeddings = await loop.run_in_executor(None, self.model.encode, content)
            
            # Upsert to Chroma
            logger.info(f"Indexing: {file_path}")
            self.collection.upsert(
                ids=[file_id],
                embeddings=[embeddings.tolist()],
                documents=[content],
                metadatas=[metadata]
            )

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")

    def _remove_from_db(self, file_path: Path):
        try:
            file_id = str(file_path.absolute())
            self.collection.delete(ids=[file_id])
            logger.info(f"Removed from index: {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove {file_path}: {e}")
