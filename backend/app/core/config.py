"""Configuración central de la aplicación.

Todos los valores se leen de variables de entorno (o de `backend/.env` en local).
Nada de model ids, URLs ni secretos hardcodeados en el código: eso permite cambiar
de modelo o de entorno sin redeploy de código.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    APP_ENV: Literal["local", "staging", "production"] = "local"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    SQL_ECHO: bool = False

    # --- Auth ---
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 720

    # --- Base de datos ---
    DATABASE_URL: str

    # --- Gemini ---
    GEMINI_API_KEY: str = ""
    GEMINI_TEXT_MODEL: str = "gemini-3.7-flash"
    GEMINI_VISION_MODEL: str = "gemini-3.7-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"
    GEMINI_EMBEDDING_DIM: int = 1536
    GEMINI_TIMEOUT_SECONDS: int = 180

    # --- Langfuse ---
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    LANGFUSE_TRACING_ENVIRONMENT: str = "local"

    # --- CORS ---
    # Se declara como str y se parsea a lista: pydantic-settings intenta decodificar
    # JSON en los campos de tipo complejo, así que un "a,b" en el env reventaría.
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Demo ---
    SEED_ON_STARTUP: bool = True
    DEMO_PASSWORD: str = "Alicorp2026!"

    @property
    def cors_origins(self) -> list[str]:
        """Lista de orígenes permitidos, sin barra final (un `/` sobrante rompe el match)."""
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.LANGFUSE_PUBLIC_KEY and self.LANGFUSE_SECRET_KEY)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """Cacheado: las settings se leen una sola vez por proceso."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
