import asyncio
import logging
from pathlib import Path
from typing import List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from src.core.config import settings
from src.services.indexer import AsyncIndexer

logger = logging.getLogger("watcher")

class MemexEventHandler(FileSystemEventHandler):
    def __init__(self, indexer: AsyncIndexer, loop: asyncio.AbstractEventLoop):
        self.indexer = indexer
        self.loop = loop

    def _should_process(self, path_str: str) -> bool:
        path = Path(path_str)
        
        # Check ignored directories
        for part in path.parts:
            if part in settings.IGNORE_DIRS:
                return False
        
        # Check extension
        if path.suffix not in settings.SUPPORTED_EXTENSIONS:
            return False
            
        return True

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            self.loop.call_soon_threadsafe(
                asyncio.create_task,
                self.indexer.enqueue_file(Path(event.src_path))
            )

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and self._should_process(event.src_path):
            self.loop.call_soon_threadsafe(
                asyncio.create_task,
                self.indexer.enqueue_file(Path(event.src_path))
            )

class DirectoryWatcher:
    def __init__(self, indexer: AsyncIndexer):
        self.observer = Observer()
        self.indexer = indexer

    def start(self):
        loop = asyncio.get_running_loop()
        handler = MemexEventHandler(self.indexer, loop)
        
        for directory in settings.WATCH_DIRECTORIES:
            path = Path(directory)
            if not path.exists():
                logger.warning(f"Watch directory not found: {path}")
                continue
                
            logger.info(f"Watching directory: {path}")
            self.observer.schedule(handler, str(path), recursive=True)
            
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
