import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api import ClientAPI

from src.core.config import settings

class DBClient:
    _instance = None
    _client: ClientAPI = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBClient, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance

    def _initialize_client(self):
        """Initializes the persistent ChromaDB client."""
        self._client = chromadb.PersistentClient(
            path=str(settings.DB_PATH),
            settings=ChromaSettings(anonymized_telemetry=False)
        )

    def get_collection(self, name: str = "memex_files"):
        """Gets or creates the vector collection."""
        return self._client.get_or_create_collection(name=name)

    def get_client(self) -> ClientAPI:
        return self._client

# Global instance
db_client = DBClient()
