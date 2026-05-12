"""Application settings loaded from environment / .env.

Centralized so every other module reads configuration from one typed
object. See ``docs/00-design/03-architecture.md`` (Cross-cutting concerns).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM (Phase 2+) ---
    groq_api_key: str = Field(default="", description="Groq API key.")
    llm_model: str = Field(default="llama-3.1-8b-instant")

    # --- Embeddings (Phase 1+) ---
    embed_model: str = Field(default="all-MiniLM-L6-v2")

    # --- Persistence (Phase 1+) ---
    chroma_persist_dir: Path = Field(default=Path("./data/chroma"))
    graph_cache_dir: Path = Field(default=Path("./data/graphs"))
    raw_upload_dir: Path = Field(default=Path("./data/raw"))

    # --- Chunking (Phase 1+) ---
    # Character counts used as a rough token proxy (~4 chars ≈ 1 token for
    # English prose). 1024 chars ≈ 256 tokens. See ADR 0004 for why
    # dreamforge uses smaller chunks than a typical RAG project.
    chunk_size: int = Field(default=1024, ge=100)
    chunk_overlap: int = Field(default=120, ge=0)

    # --- Dreamspace capacity (Phase 1+) ---
    # Keeps the 3D scene responsive and bounds LLM cost for theme labels.
    max_chunks_in_dreamspace: int = Field(default=800, ge=1)

    # --- Semantic graph parameters (Phase 2+) ---
    knn_k: int = Field(default=8, ge=1)
    sim_floor: float = Field(default=0.55, ge=-1.0, le=1.0)
    hdbscan_min_cluster_size: int = Field(default=4, ge=2)
    umap_seed: int = Field(default=42)

    # --- HTTP (Phase 1+) ---
    cors_origins: str = Field(default="http://localhost:5173")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
