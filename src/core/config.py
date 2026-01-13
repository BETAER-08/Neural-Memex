import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
  """
  Application Settings.
  """
  APP_NAME: str = "Neural-Memex"
  VERSION: str = "0.1.0"

  # Paths
  BASE_DIR: Path = Path.home() / ".neural_memex"
  DB_PATH: Path = BASE_DIR / "chroma_db"
  
  # File Watching
  WATCH_DIRECTORIES: List[str] = [str(Path.home() / "Documents")] # Default, can be overridden env var
  SUPPORTED_EXTENSIONS: List[str] = [".md", ".txt", ".py", ".pdf"]
  IGNORE_DIRS: List[str] = [".git", "__pycache__", "node_modules", "venv", ".env"]

  # AI Model
  MODEL_NAME: str = "all-MiniLM-L6-v2"
  
  # Indexing Performance
  BATCH_SIZE: int = 10
  DEBOUNCE_SECONDS: float = 1.0

  class Config:
    env_prefix = "MEMEX_"
    env_file = ".env"


# Ensure base directory exists
settings = Settings()
os.makedirs(settings.BASE_DIR, exist_ok=True)
