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

    # --- Proveedor de LLM ---
    # 'openai' o 'gemini'. Se cambia sin tocar código: `app/ai/llm.py` despacha
    # a la implementación correspondiente y ambas exponen la misma interfaz.
    #
    # Se usa OpenAI por defecto porque el free tier de Gemini limita a 20
    # peticiones AL DÍA por modelo, y el agente consume 4 por manual: la demo
    # moriría con un 429 en la segunda prueba del evaluador.
    LLM_PROVIDER: Literal["openai", "gemini"] = "openai"

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_TEXT_MODEL: str = "gpt-5.6-luna"
    OPENAI_VISION_MODEL: str = "gpt-5.6-luna"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    #: 'none' desactiva el razonamiento extendido. Estas tareas son de generación
    #: estructurada guiada por prompts detallados, no de resolución de problemas:
    #: el razonamiento añadiría latencia y coste sin mejorar la adherencia al schema.
    #: ⚠️ 'minimal' NO está soportado por gpt-5.6-luna; los válidos son 'none', 'low', etc.
    OPENAI_REASONING_EFFORT: Literal["none", "low", "medium", "high"] = "none"

    # --- Gemini (fallback documentado) ---
    GEMINI_API_KEY: str = ""
    GEMINI_TEXT_MODEL: str = "gemini-3.5-flash"
    GEMINI_VISION_MODEL: str = "gemini-3.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"

    # --- Común a ambos ---
    # 1536: por debajo del límite de 2000 que pgvector indexa con el tipo
    # `vector`, y dimensión NATIVA de text-embedding-3-small (sin truncar).
    EMBEDDING_DIM: int = 1536
    LLM_TIMEOUT_SECONDS: int = 180

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
    def text_model(self) -> str:
        return self.OPENAI_TEXT_MODEL if self.LLM_PROVIDER == "openai" else self.GEMINI_TEXT_MODEL

    @property
    def vision_model(self) -> str:
        return (
            self.OPENAI_VISION_MODEL if self.LLM_PROVIDER == "openai" else self.GEMINI_VISION_MODEL
        )

    @property
    def embedding_model(self) -> str:
        return (
            self.OPENAI_EMBEDDING_MODEL
            if self.LLM_PROVIDER == "openai"
            else self.GEMINI_EMBEDDING_MODEL
        )

    @property
    def llm_api_key(self) -> str:
        return self.OPENAI_API_KEY if self.LLM_PROVIDER == "openai" else self.GEMINI_API_KEY

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """Cacheado: las settings se leen una sola vez por proceso."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
