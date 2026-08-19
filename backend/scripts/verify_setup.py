"""Verificación de Fase 0: comprueba que todas las credenciales funcionan.

Correr ANTES de escribir código que dependa de ellas:

    python scripts/verify_setup.py

Comprueba, en orden y sin detenerse ante el primer fallo:
  1. Que el DATABASE_URL apunte al Session Pooler (no a la conexión directa IPv6).
  2. Que la BD responda y tenga la extensión pgvector.
  3. Que los model ids de Gemini existan de verdad en la API.
  4. Que el modelo de embeddings devuelva la dimensión configurada.
  5. Que Langfuse autentique (si está configurado).
"""

import asyncio

import _bootstrap  # noqa: F401  (efecto secundario: arregla el sys.path)

from app.core.config import settings

OK = "\033[92m  OK \033[0m"
FAIL = "\033[91mFALLA\033[0m"
WARN = "\033[93m AVISO\033[0m"


def _check_database_url() -> bool:
    url = settings.DATABASE_URL
    print("\n[1/5] Formato del DATABASE_URL")

    problemas = []
    if not url.startswith("postgresql+asyncpg://"):
        problemas.append("debe empezar con 'postgresql+asyncpg://' (SQLAlchemy async)")
    if ".pooler.supabase.com" not in url:
        problemas.append(
            "no apunta al Session Pooler. La conexión directa (db.<ref>.supabase.co) "
            "es IPv6-only y Render no la alcanza"
        )
    if "<PASSWORD>" in url or "<PROJECT_REF>" in url:
        problemas.append("todavía tiene placeholders sin reemplazar")

    if problemas:
        for p in problemas:
            print(f"  {FAIL} {p}")
        return False
    print(f"  {OK} Session Pooler + driver asyncpg")
    return True


async def _check_database() -> bool:
    print("\n[2/5] Conexión a Supabase y pgvector")
    try:
        from sqlalchemy import text

        from app.db.session import engine

        async with engine.connect() as conn:
            version = (await conn.execute(text("select version()"))).scalar_one()
            has_vector = (
                await conn.execute(
                    text("select exists(select 1 from pg_extension where extname='vector')")
                )
            ).scalar_one()

        print(f"  {OK} {str(version).split(' on ')[0]}")
        if has_vector:
            print(f"  {OK} extensión pgvector instalada")
        else:
            print(f"  {FAIL} falta pgvector → ejecuta: create extension if not exists vector;")
        return bool(has_vector)
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} {type(exc).__name__}: {exc}")
        return False


def _check_gemini() -> bool:
    print("\n[3/5] Modelos de Gemini")
    if not settings.GEMINI_API_KEY:
        print(f"  {FAIL} GEMINI_API_KEY vacía")
        return False

    try:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        disponibles = {m.name.removeprefix("models/") for m in client.models.list()}
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} no se pudo listar modelos: {type(exc).__name__}: {exc}")
        return False

    todo_ok = True
    for etiqueta, model_id in [
        ("texto", settings.GEMINI_TEXT_MODEL),
        ("visión", settings.GEMINI_VISION_MODEL),
        ("embeddings", settings.GEMINI_EMBEDDING_MODEL),
    ]:
        if model_id.startswith("models/"):
            print(f"  {FAIL} {etiqueta}: '{model_id}' lleva el prefijo 'models/' — quítalo")
            todo_ok = False
        elif model_id in disponibles:
            print(f"  {OK} {etiqueta}: {model_id}")
        else:
            print(f"  {FAIL} {etiqueta}: '{model_id}' no existe en la API")
            todo_ok = False
    return todo_ok


def _check_embedding_dim() -> bool:
    print("\n[4/5] Dimensión de embeddings")
    if settings.GEMINI_EMBEDDING_DIM > 2000:
        print(
            f"  {FAIL} {settings.GEMINI_EMBEDDING_DIM} dims: pgvector no puede indexar "
            "más de 2000 con el tipo `vector`. El índice HNSW fallaría."
        )
        return False

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        resp = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents="prueba de dimensionalidad",
            config=types.EmbedContentConfig(
                output_dimensionality=settings.GEMINI_EMBEDDING_DIM
            ),
        )
        vec = resp.embeddings[0].values
        norma = sum(v * v for v in vec) ** 0.5

        if len(vec) != settings.GEMINI_EMBEDDING_DIM:
            print(f"  {FAIL} se pidieron {settings.GEMINI_EMBEDDING_DIM} dims y llegaron {len(vec)}")
            return False

        print(f"  {OK} {len(vec)} dims · norma L2 = {norma:.4f}")
        if abs(norma - 1.0) > 0.01:
            print(
                f"  {WARN} el vector NO viene normalizado (norma {norma:.4f}). "
                "Hay que normalizar en app/ai/embeddings.py o la distancia coseno se degrada."
            )
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} {type(exc).__name__}: {exc}")
        return False


def _check_langfuse() -> bool:
    print("\n[5/5] Langfuse")
    if not settings.langfuse_enabled:
        print(f"  {WARN} sin claves configuradas — la app corre igual, sin trazas")
        return True
    try:
        from langfuse import get_client

        client = get_client()
        if client.auth_check():
            print(f"  {OK} autenticado contra {settings.LANGFUSE_BASE_URL}")
            return True
        print(f"  {FAIL} auth_check() falló — revisa las claves y LANGFUSE_BASE_URL")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} {type(exc).__name__}: {exc}")
        return False


async def main() -> int:
    print("=" * 70)
    print("  Content Suite — Verificación de configuración (Fase 0)")
    print("=" * 70)

    resultados = [
        _check_database_url(),
        await _check_database(),
        _check_gemini(),
        _check_embedding_dim(),
        _check_langfuse(),
    ]

    print("\n" + "=" * 70)
    if all(resultados):
        print("  Todo listo. Puedes correr las migraciones y arrancar la API.")
        return 0
    print(f"  {sum(not r for r in resultados)} de {len(resultados)} comprobaciones fallaron.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
