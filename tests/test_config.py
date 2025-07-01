import pytest
from pydantic import ValidationError
from src.config import Settings, get_settings


def test_get_settings_is_cached():
    """
    Test that get_settings function returns a cached instance of Settings.
    """
    # Clear cache for a clean test
    get_settings.cache_clear()
    
    # Mock environment variables
    import os
    os.environ["OPENAI_API_KEY"] = "test_key_1"
    os.environ["API_KEY"] = "test_api_key_1"
    
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    # Change env var and check if settings are still cached
    os.environ["OPENAI_API_KEY"] = "test_key_2"
    s3 = get_settings()
    assert s3 is s1  # Should still be the same cached object

    # Clean up environment variables
    del os.environ["OPENAI_API_KEY"]
    del os.environ["API_KEY"]


def test_settings_from_env(monkeypatch):
    """
    Test that Settings are correctly loaded from environment variables.
    """
    # Clear cache before test
    get_settings.cache_clear()

    monkeypatch.setenv("OPENAI_API_KEY", "env_openai_key")
    monkeypatch.setenv("API_KEY", "env_api_key")
    monkeypatch.setenv("EMBEDDING_MODEL", "env_embedding_model")

    settings = get_settings()
    assert settings.OPENAI_API_KEY == "env_openai_key"
    assert settings.API_KEY == "env_api_key"
    assert settings.EMBEDDING_MODEL == "env_embedding_model"


def test_settings_default_values(monkeypatch):
    """
    Test that the Settings class uses default values when environment variables are not set.
    We only mock the required ones and ensure others that might be in a .env file are cleared.
    """
    # Clear cache before test
    get_settings.cache_clear()

    # Clear potentially conflicting env vars that might be in a .env file
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("CHROMA_PERSIST_DIRECTORY", raising=False)
    monkeypatch.delenv("KNOWLEDGE_BASE_FILE", raising=False)
    monkeypatch.delenv("TOP_K_RESULTS", raising=False)
    monkeypatch.delenv("SIMILARITY_THRESHOLD", raising=False)
    monkeypatch.delenv("TEMPERATURE", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False) # LANGCHAIN_API_KEY opsiyonel, bu yüzden test için kaldıralım.

    # Mock only required environment variables
    monkeypatch.setenv("OPENAI_API_KEY", "required_openai_key")
    monkeypatch.setenv("API_KEY", "required_api_key")

    settings = get_settings()

    # Assert required values are set
    assert settings.OPENAI_API_KEY == "required_openai_key"
    assert settings.API_KEY == "required_api_key"

    # Assert default values are used for optional settings
    assert settings.EMBEDDING_MODEL == "text-embedding-3-small"
    assert settings.LLM_MODEL == "gpt-4o-mini-2024-07-18"
    assert settings.CHROMA_PERSIST_DIRECTORY == "./chroma_db"
    assert settings.TOP_K_RESULTS == 3
    assert settings.SIMILARITY_THRESHOLD == 0.7
    assert settings.TEMPERATURE == 0.0
    assert settings.CELERY_BROKER_URL == "redis://localhost:6379/0"
    assert settings.CELERY_RESULT_BACKEND == "redis://localhost:6379/0"
    assert settings.LANGCHAIN_API_KEY is None


def test_settings_missing_required_variable(monkeypatch):
    """
    Test that instantiating Settings raises a ValidationError if a required environment variable is missing.
    """
    # Clear cache for a clean test
    get_settings.cache_clear()

    # Prevent Pydantic from reading any .env file during this test
    monkeypatch.setitem(Settings.model_config, 'env_file', None)

    # Ensure all required keys are missing by clearing them
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    # Expect a Pydantic ValidationError
    with pytest.raises(ValidationError):
        get_settings() 