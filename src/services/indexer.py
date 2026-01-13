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
        """Starts the consumer loop with optimized batch processing."""
        self._running = True
        logger.info("AsyncIndexer started with batch processing.")
        
        buffer: List[Path] = []
        
        while self._running:
            try:
                # 버퍼가 있으면 Debounce 시간만큼 대기, 없으면 무한 대기
                timeout = settings.DEBOUNCE_SECONDS if buffer else None
                
                try:
                    # 1. 큐에서 아이템 가져오기
                    file_path = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    buffer.append(file_path)
                    self.queue.task_done()
                except asyncio.TimeoutError:
                    # 2. 타임아웃(Debounce) 발생 시: 버퍼에 내용이 있으면 처리
                    if buffer:
                        # 중복 제거 (set) 후 처리
                        await self._process_batch(list(set(buffer)))
                        buffer.clear()
                    continue

                # 3. 버퍼가 꽉 찼으면 즉시 처리
                if len(buffer) >= settings.BATCH_SIZE:
                    await self._process_batch(list(set(buffer)))
                    buffer.clear()
                         
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in indexer loop: {e}")
        
        # 종료 시 남은 잔여물 처리
        if buffer:
            await self._process_batch(list(set(buffer)))

    async def stop(self):
        """Stops the consumer loop."""
        self._running = False
        # Queue 해제를 위해 더미 데이터를 넣거나 task cancel 필요할 수 있음

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
                    # extract_text()가 None을 반환하는 경우 방지
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text
            else:
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

        # 1. Extraction Phase
        for file_path in file_paths:
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

        if not ids:
            return

        # 2. Embedding Phase (Batch)
        try:
            logger.info(f"Embedding batch of {len(ids)} unique files...")
            # run_in_executor로 CPU Blocking 방지
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