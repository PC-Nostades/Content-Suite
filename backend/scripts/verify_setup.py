"""Verificación de configuración: comprueba que todas las credenciales funcionan.

    python scripts/verify_setup.py

Comprueba, sin detenerse ante el primer fallo:
  1. Que el DATABASE_URL apunte al Session Pooler (no a la conexión directa IPv6).
  2. Que la BD responda y tenga pgvector.
  3. Que los model ids del proveedor activo existan de verdad.
  4. Que el modelo de embeddings devuelva la dimensión configurada.
  5. Que Langfuse autentique.
"""

import asyncio

import _bootstrap  # noqa: F401

from app.core.config import settings

OK = "  OK  "
FAIL = "FALLA "
WARN = "AVISO "


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
            dim = (
                await conn.execute(
                    text(
                        "select atttypmod from pg_attribute "
                        "where attrelid = 'public.manual_chunks'::regclass and attname='embedding'"
                    )
                )
            ).scalar_one_or_none()

        print(f"  {OK} {str(version).split(' on ')[0]}")
        print(f"  {OK if has_vector else FAIL} extensión pgvector")

        if dim is not None and dim != settings.EMBEDDING_DIM:
            print(
                f"  {FAIL} la columna `embedding` es vector({dim}) pero EMBEDDING_DIM="
                f"{settings.EMBEDDING_DIM}. Los inserts fallarían."
            )
            return False
        if dim is not None:
            print(f"  {OK} columna embedding = vector({dim}), coincide con EMBEDDING_DIM")
        return bool(has_vector)
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} {type(exc).__name__}: {exc}")
        return False


async def _check_models() -> bool:
    print(f"\n[3/5] Modelos del proveedor «{settings.LLM_PROVIDER}»")
    if not settings.llm_api_key:
        clave = "OPENAI_API_KEY" if settings.LLM_PROVIDER == "openai" else "GEMINI_API_KEY"
        print(f"  {FAIL} {clave} vacía")
        return False

    try:
        if settings.LLM_PROVIDER == "openai":
            from app.ai.providers.openai_provider import get_client

            client = get_client()
            disponibles = {m.id async for m in client.models.list()}
        else:
            from app.ai.providers.gemini_provider import get_client

            disponibles = {
                m.name.removeprefix("models/") for m in get_client().models.list()
            }
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} no se pudo listar modelos: {type(exc).__name__}: {exc}")
        return False

    todo_ok = True
    for etiqueta, model_id in [
        ("texto", settings.text_model),
        ("visión", settings.vision_model),
        ("embeddings", settings.embedding_model),
    ]:
        if model_id in disponibles:
            print(f"  {OK} {etiqueta}: {model_id}")
        else:
            print(f"  {FAIL} {etiqueta}: '{model_id}' no existe en la API")
            sugerencias = sorted(
                m for m in disponibles
                if ("embedding" in m) == ("embedding" in model_id)
            )[:6]
            if sugerencias:
                print(f"         disponibles: {', '.join(sugerencias)}")
            todo_ok = False
    return todo_ok


async def _check_embedding_dim() -> bool:
    print("\n[4/5] Dimensión de embeddings")
    if settings.EMBEDDING_DIM > 2000:
        print(
            f"  {FAIL} {settings.EMBEDDING_DIM} dims: pgvector no puede indexar más de "
            "2000 con el tipo `vector`. El índice HNSW no se crearía."
        )
        return False

    try:
        from app.ai.embeddings import embed_query

        vec = await embed_query("prueba de dimensionalidad")
        norma = sum(v * v for v in vec) ** 0.5
        print(f"  {OK} {len(vec)} dims · norma L2 = {norma:.4f}")
        if abs(norma - 1.0) > 0.01:
            print(
                f"  {WARN} el vector NO viene normalizado (norma {norma:.4f}); "
                "la distancia coseno se degradaría."
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

        from app.ai.observability import init_observability

        init_observability()
        if get_client().auth_check():
            print(f"  {OK} autenticado contra {settings.LANGFUSE_BASE_URL}")
            return True
        print(f"  {FAIL} auth_check() falló — revisa las claves y LANGFUSE_BASE_URL")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} {type(exc).__name__}: {exc}")
        return False


async def main() -> int:
    print("=" * 70)
    print("  Content Suite — Verificación de configuración")
    print("=" * 70)

    resultados = [
        _check_database_url(),
        await _check_database(),
        await _check_models(),
        await _check_embedding_dim(),
        _check_langfuse(),
    ]

    print("\n" + "=" * 70)
    if all(resultados):
        print("  Todo listo.")
        return 0
    print(f"  {sum(not r for r in resultados)} de {len(resultados)} comprobaciones fallaron.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
