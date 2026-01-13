import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader
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
        """Starts the consumer loop with batch processing."""
        self._running = True
        logger.info("AsyncIndexer started with batch processing.")
        
        buffer: List[Path] = []
        
        while self._running:
            try:
                # Wait for items with a timeout to flush buffer if it doesn't fill up
                try:
                    # If buffer is empty, wait indefinitely for the first item
                    # If buffer has items, wait specifically for debounce/timeout
                    timeout = None if not buffer else settings.DEBOUNCE_SECONDS
                    
                    file_path = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    buffer.append(file_path)
                    self.queue.task_done()
                except asyncio.TimeoutError:
                    # Timeout reached, flush buffer if we have items
                    pass
                
                # Check conditions to process batch
                if len(buffer) >= settings.BATCH_SIZE or (not self.queue.empty() and len(buffer) > 0) or (buffer and not self.queue.qsize()):
                     # Simple logic: If we have items and (hit batch size OR timed out), process.
                     # The wait_for handles the timeout case.
                     if buffer:
                         await self._process_batch(list(buffer)) # Pass a copy
                         buffer.clear()
                         
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in indexer loop: {e}")
        
        # Process remaining items on stop
        if buffer:
            await self._process_batch(buffer)

    async def stop(self):
        """Stops the consumer loop."""
        self._running = False

    async def enqueue_file(self, file_path: Path):
        """Adds a file path to the processing queue."""
        await self.queue.put(file_path)

    def _extract_text(self, file_path: Path) -> str:
        """Extracts text from file based on extension."""
        try:
            if file_path.suffix.lower() == ".pdf":
                reader = PdfReader(str(file_path))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            else:
                # Default text handling
                return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Could not extract text from {file_path}: {e}")
            return ""

    async def _process_batch(self, file_paths: List[Path]):
        """Reads files, embeds content, and updates DB in batch."""
        if not file_paths:
            return

        loop = asyncio.get_running_loop()
        if self.model is None:
            await loop.run_in_executor(None, self._load_model)

        ids = []
        documents = []
        metadatas = []
        valid_indices = [] # To keep track of which files we actually processed successfully

        # 1. Extraction Phase
        for i, file_path in enumerate(file_paths):
            if not file_path.exists():
                logger.info(f"File deleted: {file_path}, removing from DB.") 
                self._remove_from_db(file_path)
                continue

            content = self._extract_text(file_path)
            
            if not content.strip():
                continue

            ids.append(str(file_path.absolute()))
            documents.append(content)
            metadatas.append({
                "filename": file_path.name,
                "path": str(file_path.absolute()),
                "extension": file_path.suffix,
                "size": file_path.stat().st_size
            })
            valid_indices.append(i)

        if not ids:
            return

        # 2. Embedding Phase (Batch)
        try:
            logger.info(f"Embedding batch of {len(ids)} files...")
            embeddings = await loop.run_in_executor(None, self.model.encode, documents)
            
            # 3. Upsert Phase
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Batch upsert complete. ({len(ids)} items)")
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")

    def _remove_from_db(self, file_path: Path):
        try:
            file_id = str(file_path.absolute())
            self.collection.delete(ids=[file_id])
            logger.info(f"Removed from index: {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove {file_path}: {e}")
