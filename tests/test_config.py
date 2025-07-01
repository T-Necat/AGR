import pytest
from src.config import Settings, get_settings

# Clear the cache for get_settings before each test
@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()

def test_settings_load_from_env(monkeypatch):
    """
    Test that the Settings class correctly loads values from environment variables.
    """
    # Mock environment variables
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "test_langchain_key")
    monkeypatch.setenv("API_KEY", "test_api_key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test_embedding_model")
    monkeypatch.setenv("LLM_MODEL", "test_llm_model")
    monkeypatch.setenv("CHROMA_PERSIST_DIRECTORY", "/test/db")
    monkeypatch.setenv("TOP_K_RESULTS", "10")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.8")
    monkeypatch.setenv("TEMPERATURE", "0.5")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://test:6379/1")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://test:6379/2")

    # Instantiate settings to trigger loading from env
    settings = get_settings()

    assert settings.OPENAI_API_KEY == "test_openai_key"
    assert settings.LANGCHAIN_API_KEY == "test_langchain_key"
    assert settings.API_KEY == "test_api_key"
    assert settings.EMBEDDING_MODEL == "test_embedding_model"
    assert settings.LLM_MODEL == "test_llm_model"
    assert settings.CHROMA_PERSIST_DIRECTORY == "/test/db"
    assert settings.TOP_K_RESULTS == 10
    assert settings.SIMILARITY_THRESHOLD == 0.8
    assert settings.TEMPERATURE == 0.5
    assert settings.CELERY_BROKER_URL == "redis://test:6379/1"
    assert settings.CELERY_RESULT_BACKEND == "redis://test:6379/2"

def test_settings_default_values(monkeypatch):
    """
    Test that the Settings class uses default values when environment variables are not set.
    We only mock the required ones and ensure others that might be in a .env file are cleared.
    """
    # Clear potentially conflicting env vars that might be in a .env file
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("CHROMA_PERSIST_DIRECTORY", raising=False)
    monkeypatch.delenv("TOP_K_RESULTS", raising=False)
    monkeypatch.delenv("SIMILARITY_THRESHOLD", raising=False)
    monkeypatch.delenv("TEMPERATURE", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)

    # Mock only required environment variables
    monkeypatch.setenv("OPENAI_API_KEY", "required_openai_key")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "required_langchain_key")
    monkeypatch.setenv("API_KEY", "required_api_key")

    # Instantiate settings
    settings = get_settings()

    # Assert required values are set
    assert settings.OPENAI_API_KEY == "required_openai_key"
    assert settings.LANGCHAIN_API_KEY == "required_langchain_key"
    assert settings.API_KEY == "required_api_key"

    # Assert default values are used for optional settings
    assert settings.EMBEDDING_MODEL == "text-embedding-3-small"
    assert settings.LLM_MODEL == "gpt-4.1-mini-2025-04-14"
    assert settings.CHROMA_PERSIST_DIRECTORY == "./chroma_db"
    assert settings.TOP_K_RESULTS == 3
    assert settings.SIMILARITY_THRESHOLD == 0.7
    assert settings.TEMPERATURE == 0.0
    assert settings.CELERY_BROKER_URL == "redis://localhost:6379/0"
    assert settings.CELERY_RESULT_BACKEND == "redis://localhost:6379/0"

def test_settings_missing_required_variable(monkeypatch):
    """
    Test that instantiating Settings raises an error if a required environment variable is missing.
    """
    # Mock only some of the required variables
    monkeypatch.setenv("OPENAI_API_KEY", "only_one_key")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "only_one_key")
    
    # Expect a validation error (Pydantic's ValidationError)
    with pytest.raises(Exception):
        get_settings() 