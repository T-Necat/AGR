from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Uygulama genelindeki ayarları yönetir.
    Ayarlar .env dosyasından, ortam değişkenlerinden veya varsayılan değerlerden okunur.
    """
    # .env dosyasının yolunu, kodlamasını ve ekstra alanları yoksaymayı belirtir.
    model_config = SettingsConfigDict(
        env_file="src/.env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Gerekli Ayarlar (varsayılan değeri yok)
    OPENAI_API_KEY: str
    API_KEY: str
    
    # Opsiyonel Ayarlar (varsayılan değerli)
    LANGCHAIN_API_KEY: Optional[str] = None
    DATABASE_URL: str = "sqlite:///./evaluation_metrics.db"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini-2024-07-18"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"
    KNOWLEDGE_BASE_FILE: str = "agent_knowledge_base.csv"

    # RAG Ayarları
    TOP_K_RESULTS: int = 3
    SIMILARITY_THRESHOLD: float = 0.7
    TEMPERATURE: float = 0.0

    # Celery & Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"


@lru_cache()
def get_settings() -> Settings:
    """
    Ayarları önbelleğe alarak döndüren fonksiyon.
    Bu, test sırasında ayarların üzerine yazılabilmesini sağlar.
    """
    return Settings.model_validate({}) 