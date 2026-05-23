from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    APP_NAME: str = "Local Graph RAG & Knowledge Graph Mapper"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./data/graphrag.db"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "graphrag_password"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "llama3.1"

    # FAISS
    FAISS_INDEX_PATH: str = "./data/faiss_index"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:80"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
