# Content Suite

> Plataforma de consistencia de marca para lanzamientos masivos de producto.
> **Módulo I — Brand DNA Architect** en construcción. Módulos II–IV: roadmap documentado.

Cuando una compañía de consumo masivo lanza cientos de productos al año, el cuello de botella
no es generar contenido: es que todo ese contenido **suene y se vea** como la misma marca.
Content Suite convierte las reglas de marca en un artefacto que las máquinas pueden leer,
aplicar y auditar.

---

## Estado actual

| Módulo | Estado |
|---|---|
| **I — Brand DNA Architect** | 🚧 En construcción — cimientos, auth y RBAC operativos |
| II — Creative Engine | ⏳ Terreno preparado (`manual_chunks`, `retrieval.py`, tabla `content_pieces`) |
| III — Governance & Multimodal Audit | ⏳ Terreno preparado (roles, tablas `approvals` / `visual_audits`) |
| IV — Observabilidad (Langfuse) | ⏳ Instrumentación prevista desde el día 1 |

---

## Arquitectura

```
┌──────────────────────────┐        ┌───────────────────────────┐
│  Render Static Site      │        │  Render Web Service       │
│  React 19 + Vite + TS    │        │  FastAPI (Python 3.13)    │
│  Tailwind v4 + shadcn/ui │        │                           │
│                          │        │  ┌─────────────────────┐  │
│  rewrite /api/*  ────────┼───────►│  │ modules/            │  │
│  (mismo origen)          │        │  │  auth · brand_dna   │  │
│  rewrite /*  → index.html│        │  │  creative(II)       │  │
│  NO duerme               │        │  │  governance(III)    │  │
└──────────────────────────┘        │  ├─────────────────────┤  │
                                    │  │ ai/  (compartido)   │  │
                                    │  │  gemini · chunking  │  │
                                    │  │  embeddings         │  │
                                    │  │  retrieval          │  │
                                    │  │  observability      │  │
                                    │  └─────────────────────┘  │
                                    └────────┬─────────┬────────┘
                                             │         │
                              ┌──────────────▼──┐   ┌──▼─────────────┐
                              │ Supabase        │   │ Google Gemini  │
                              │ Postgres +      │   │ 3.7-flash      │
                              │ pgvector (1536) │   │ embedding-2    │
                              │ Session Pooler  │   └────────────────┘
                              └─────────────────┘            │
                                                    ┌────────▼───────┐
                                                    │ Langfuse Cloud │
                                                    └────────────────┘
```

**Todo en Render, un solo Blueprint.** El static site proxea `/api/*` hacia la API, así que
frontend y backend comparten origen: **CORS desaparece por completo**. Y como los static sites
de Render no duermen, el shell de la app carga instantáneo aunque la API esté despertando.

---

## Correr en local

**Requisitos:** Python 3.13, Node 22, un proyecto de Supabase, una API key de Google AI Studio.

```bash
# --- Backend ---
cd backend
python -m venv ../.venv && ../.venv/Scripts/activate   # Linux/macOS: source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # y rellenar DATABASE_URL + GEMINI_API_KEY

python scripts/verify_setup.py   # comprueba credenciales, modelos y dimensiones
python scripts/migrate.py        # aplica db/migrations/*.sql en orden
python scripts/seed_users.py     # crea los 3 usuarios de demo

uvicorn app.main:app --reload --port 8010
# → http://127.0.0.1:8010/docs
```

```bash
# --- Frontend ---
cd frontend
npm install
cp .env.example .env
npm run dev
# → http://localhost:5173
```

El `vite.config.ts` proxea `/api` y `/health` a `127.0.0.1:8010`, reproduciendo en local la
misma condición de mismo-origen que hay en producción. Así el código del cliente usa siempre
rutas relativas y CORS nunca entra en juego, ni en desarrollo ni desplegado.

> **Nota:** la API usa el puerto **8010** y no el 8000 para no chocar con otros servicios
> locales. Si lo cambias, ajusta también el proxy de `vite.config.ts`.

---

## Credenciales de demo

Los tres roles con vistas diferenciadas. Contraseña común definida en `DEMO_PASSWORD`.

| Rol | Correo | Qué ve |
|---|---|---|
| Creador | `creator@alicorp.demo` | Crea marcas, genera y regenera manuales |
| Aprobador A · Texto | `approver.a@alicorp.demo` | Manuales en solo-lectura (+ Módulo III) |
| Aprobador B · Visual | `approver.b@alicorp.demo` | Manuales en solo-lectura (+ Módulo III) |

En `/login`, con `VITE_SHOW_DEMO_CREDENTIALS=true`, hay tres botones que entran directo a cada rol.

---

## Decisiones de diseño y trade-offs

### 1. Cada regla del manual es un objeto, no una frase

El schema del Manual de Marca modela cada regla como
`{id, statement, severity: hard|soft, modality: text|visual, check_hint}`.

El campo decisivo es **`check_hint`**: obliga al modelo a escribir reglas **medibles**.

| ❌ Inútil para auditar | ✅ Verificable |
|---|---|
| «el logo debe verse bien» | «el logo debe ocupar ≥ 8 % del ancho de la pieza» |
| «usar colores cálidos» | «`#E8552D` primario, máximo 40 % del área» |
| «buena legibilidad» | «contraste texto/fondo ≥ 4.5:1 (WCAG AA)» |

Sin esto el Módulo III no puede auditar imágenes de verdad — solo podría opinar sobre prosa — y
el Módulo II no puede citar qué regla aplicó.

### 2. Chunking semántico derivado del schema, no de tamaño fijo

Cada sección del manual produce un chunk con metadata `section` / `rule_type` / `modality`.
El argumento decisivo no es que el chunking fijo rompa frases, sino que **sin metadata limpia no
hay pre-filtrado**: un chunk que mezcla el final de «tono de voz» con el inicio de «paleta de
color» no puede etiquetarse, y entonces una consulta del Módulo III sobre el tamaño del logo
devuelve reglas de léxico.

```
Módulo II  → modality IN ('text','both')   AND rule_type IN ('tone','lexicon','grammar',…)
Módulo III → modality IN ('visual','both') AND rule_type IN ('color','logo','photography',…)
```

El filtro SQL da **precisión**; el vector da **recall** dentro del dominio correcto.

### 3. RAG para guía, SQL para restricciones duras

El léxico prohibido **no** se verifica por similitud vectorial: un check de palabra prohibida
necesita 100 % de recall y la búsqueda semántica no lo garantiza. Por eso:

- `manual_chunks` (vectores) → reglas de *guía*: tono, composición, estética.
- `brand_manuals.content` (JSONB) → listas *duras* leídas por SQL directo (`get_hard_lexicon`),
  aplicadas como post-filtro determinista sobre lo que genere el LLM.

### 4. Embeddings a 1536 dimensiones, no 3072

**pgvector no puede indexar más de 2000 dimensiones con el tipo `vector`**, y el default de
Gemini es 3072. Con 3072 la tabla funciona pero el índice HNSW **no se crea** — un fallo
silencioso que aparecería recién al usar el RAG en el Módulo II.

Se usa `output_dimensionality=1536`, verificado empíricamente: `gemini-embedding-2` devuelve el
vector con **norma L2 = 1.0000** al truncar, así que auto-normaliza y no hace falta normalizar a
mano (con `gemini-embedding-001` sí era obligatorio). Hay un test que lo vigila como guarda.

### 5. `gemini-embedding-2` en vez de `gemini-embedding-001`

Se pierde el parámetro `task_type` (la asimetría documento/consulta se implementa por instrucción
en el prompt). A cambio el modelo es **multimodal**: en el Módulo III la imagen subida podrá
embeberse en el **mismo espacio vectorial** que las reglas visuales, y recuperar reglas por
similitud con la imagen y no solo por consulta de texto. `gemini-embedding-001` no puede hacerlo.

### 6. `202 Accepted` + polling, no streaming ni `await` bloqueante

La generación del manual tarda 20–60 s.

- **Sobrevive al refresh.** Con `await`, recargar la página pierde el trabajo y una llamada del
  cupo gratuito. Con polling el estado vive en Postgres.
- **Desacopla el cold start de la generación.** Un `await` haría que el peor caso sea
  *cold start + generación* (~120 s) en un solo request HTTP.
- **Es la misma maquinaria del Módulo III**, donde el flujo es `pending → approved/rejected`
  sobre una entidad persistida. `StatusBadge`, `query-keys` y `refetchInterval` se reutilizan.
- **Permite mostrar etapas reales** (`drafting_visual`, `embedding`…). Una barra que avanza por
  etapas nombradas durante 45 s se percibe como un sistema serio; un spinner, como un cuelgue.

No SSE: el manual es *structured output*, y un JSON parcial no es renderizable. Además
`EventSource` no envía el header `Authorization`.

### 7. Generación multi-etapa, no una sola llamada

Pedir los ~200 campos del schema en una llamada hace que el modelo trunque listas e ignore
`minItems`. El agente genera en etapas: estrategia → (verbal ∥ visual ∥ compliance) en paralelo.
Cada schema es 4–6× menor (mucha mayor adherencia), cada etapa se reintenta sola, y las etapas
alimentan el progreso real de la UI.

### 8. JWT propio, no Supabase Auth

Control total del RBAC con una dependencia (`require_role`) y cero integración extra entre
frontend, Supabase y backend. Contrapartida asumida: el backend se conecta con un rol que
**bypassa RLS**, así que la autorización real vive en FastAPI. Por eso la migración `0002`
**cierra la puerta de PostgREST** — sin eso, cualquiera con la `anon key` (pública por diseño)
podría leer `users.password_hash`.

Librerías: **PyJWT** (no `python-jose`, abandonado con CVE-2024-33663 sin parche) y **bcrypt
directo** (no `passlib`, sin mantenimiento y roto con `bcrypt>=4.1`).

### 9. JWT en `localStorage` con Bearer

Como el SPA proxea `/api/*` desde su propio origen, una cookie `httpOnly` + `SameSite=Lax`
**sí sería viable** y es más segura. Se descarta porque (a) dependería de que el proxy de rewrite
de Render reenvíe `Set-Cookie`/`Cookie` correctamente — justo el eslabón menos verificado del
despliegue, y el auth no debería depender de él; y (b) Bearer funciona idéntico en same-origin y
cross-origin, así que el plan B de CORS no obliga a tocar nada de auth.

Sin cookies no hay superficie CSRF. La mitigación de XSS es que todo el contenido generado se
renderiza como datos tipados, **nunca** con `dangerouslySetInnerHTML`.

*Próximo paso anotado:* migrar a cookie `httpOnly` + CSRF token una vez validado el proxy.

### 10. Los aprobadores leen los manuales

En el Módulo III el Aprobador A juzga si un texto respeta el léxico prohibido y el B si una
imagen respeta la paleta: sin acceso al manual, aprobar sería arbitrario. Y **RBAC bien hecho es
una matriz de permisos, no muros** — tres roles sobre el *mismo* recurso con capacidades distintas
demuestra que el modelo es real. El riesgo no es que un aprobador lea el manual, es que lo altere:
la restricción va sobre las **mutaciones** y la aplica el backend.

---

## Esquema de base de datos

| Tabla | Propósito |
|---|---|
| `users` | 3 roles: `creator`, `approver_a`, `approver_b` (+`admin`) |
| `brands` | Marca + `brief` JSONB con los parámetros cortos del usuario |
| `brand_manuals` | Versiones del manual: `content` JSONB, `status`, `stage`, `langfuse_trace_id` |
| `manual_chunks` | Chunks + `embedding vector(1536)` + metadata de pre-filtrado + `content_tsv` |
| `content_pieces` | *(Módulo II)* con `retrieved_rule_ids` para trazabilidad del RAG |
| `approvals`, `visual_audits` | *(Módulo III)* hallazgos que **citan** el `rule_id` evaluado |

Índices clave: HNSW sobre `embedding`, compuesto `(brand_id, modality, rule_type)` para el
pre-filtrado, único parcial de «un solo manual publicado por marca», y GIN sobre `content` JSONB.

Funciones: `match_manual_chunks(...)` (búsqueda híbrida estructurada) y `get_hard_lexicon(...)`.

Las migraciones son idempotentes y se aplican con `python scripts/migrate.py`, que lleva registro
en `schema_migrations`. También se pueden pegar a mano en el SQL Editor de Supabase, en orden.

---

## Contrato de API

Todos los errores salen con la misma forma, para que el cliente tenga un solo camino de manejo:

```json
{ "detail": { "code": "rate_limited",
              "message": "Se alcanzó el límite de la API de Gemini.",
              "retry_after_seconds": 24 } }
```

| Método | Ruta | Rol | Estado |
|---|---|---|---|
| `GET` | `/health` | público | ✅ |
| `GET` | `/health/ready` | público | ✅ incluye BD, Gemini y Langfuse |
| `POST` | `/api/v1/auth/login` | público | ✅ |
| `GET` | `/api/v1/auth/me` | auth | ✅ |
| `POST` | `/api/v1/auth/logout` | auth | ✅ |
| `POST` | `/api/v1/brands` | **creator** | 🚧 202 + BackgroundTasks |
| `GET` | `/api/v1/brands` · `/{id}` · `/{id}/status` | los 3 | 🚧 |
| `POST` | `/api/v1/rag/search` | auth | 🚧 contrato que consumirán II y III |
| `GET` | `/api/v1/brands/{id}/hard-rules` | auth | 🚧 |

Documentación interactiva en `/docs`.

---

## Limitaciones conocidas

- **Cold start.** El web service del free tier de Render duerme tras 15 min sin tráfico y tarda
  ~1 min en despertar. Mitigado con doble keep-alive (GitHub Actions + un pinger externo), ping a
  `/health` al montar el login, y un banner explícito. El static site no duerme, así que la app
  siempre carga.
- **Presupuesto de Render.** 750 h/mes por workspace y un mes tiene 744: mantener la API
  despierta 24/7 consume casi todo el cupo, y pasarse suspende *todos* los servicios gratis. El
  keep-alive corre en ventana horaria por eso.
- **El timeout del proxy de rewrite de Render no está documentado.** Si resultara menor a ~60 s,
  la primera llamada contra una API dormida se cortaría en el proxy. Plan B listo: cambiar
  `VITE_API_BASE_URL` a la URL absoluta de la API — el middleware de CORS ya está configurado.
- **Rate limits del free tier de Gemini.** Se siembran marcas ya generadas para que la demo del
  visor no dependa de una llamada en vivo.
- **`BackgroundTasks` no sobrevive a un redeploy.** Hay reconciliación al arrancar: los manuales
  que quedaron en `generating` más de 10 min pasan a `failed` con mensaje explícito.
- **El contenido generado por IA requiere validación legal y nutricional** antes de uso comercial.
  El schema incluye `compliance` y `forbidden_claims`, y el manual lleva ese disclaimer al pie.
- **Los tipos TypeScript son un espejo manual** de los schemas Pydantic. Para un módulo es la
  opción correcta; si el contrato crece, el paso natural es `openapi-typescript` contra
  `/openapi.json`.

---

## Estructura del repositorio

```
Content-Suite/
├── render.yaml              # Blueprint único: API (web) + SPA (static) + rewrite /api/*
├── backend/
│   ├── app/
│   │   ├── core/            # config · security · deps (RBAC) · exceptions · enums
│   │   ├── db/              # session (Session Pooler) · models
│   │   ├── ai/              # ⭐ compartido por los 4 módulos
│   │   └── modules/         # auth · brand_dna · creative(II) · governance(III)
│   ├── db/migrations/       # SQL idempotente y numerado
│   └── scripts/             # verify_setup · migrate · seed_users
└── frontend/
    └── src/
        ├── app/             # router.tsx ← registro de rutas
        ├── config/          # nav.ts ← registro de navegación
        ├── features/        # auth · brands(I) · content(II) · governance(III)
        └── types/api.ts     # espejo de los schemas Pydantic
```

`app/ai/` vive **fuera** de `modules/` a propósito: el Módulo II necesita `retrieval.py` y el III
`gemini` con visión. Si esas piezas vivieran dentro de `brand_dna/`, los módulos siguientes
importarían «hacia adentro» de otro módulo — el anti-patrón que obliga a refactorizar.

Añadir un módulo = una carpeta nueva, una línea en `api.py`, una fila en `nav.ts` y un `<Route>`.
