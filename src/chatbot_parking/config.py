"""Configuration helpers for the parking chatbot."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    vector_backend: str
    embeddings_provider: str
    embeddings_model: str
    llm_provider: str
    llm_model: str
    weaviate_url: str
    weaviate_index: str
    openai_api_key: str | None
    google_api_key: str | None
    azure_openai_endpoint: str | None
    azure_openai_api_key: str | None
    azure_openai_deployment: str | None
    azure_openai_api_version: str
    eval_output_dir: str
    admin_api_token: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        vector_backend=os.getenv("VECTOR_BACKEND", "faiss").lower(),
        embeddings_provider=os.getenv("EMBEDDINGS_PROVIDER", "fake").lower(),
        embeddings_model=os.getenv(
            "EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "echo").lower(),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        weaviate_url=os.getenv("WEAVIATE_URL", "http://weaviate:8080"),
        weaviate_index=os.getenv("WEAVIATE_INDEX", "ParkingDocs"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        eval_output_dir=os.getenv("EVAL_OUTPUT_DIR", "eval/results"),
        admin_api_token=os.getenv("ADMIN_API_TOKEN"),
    )
