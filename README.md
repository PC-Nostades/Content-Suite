# Content Suite

> Plataforma de consistencia de marca para lanzamientos masivos de producto.
> **Los 4 módulos implementados y funcionando.**

Cuando una compañía de consumo masivo lanza cientos de productos al año, el cuello de botella no
es generar contenido: es que todo ese contenido **suene y se vea** como la misma marca. Content
Suite convierte las reglas de marca en un artefacto que las máquinas pueden leer, aplicar y auditar.

---

## 🔗 Demo

| | |
|---|---|
| **App** | `https://content-suite-web.onrender.com` |
| **API (Swagger)** | `https://content-suite-api.onrender.com/docs` |
| **Langfuse** | *(URL del proyecto — ver sección Observabilidad)* |

> ⚠️ El backend corre en el free tier de Render, que duerme tras 15 min de inactividad.
> **La primera petición puede tardar ~60 s.** El frontend NO duerme (es un static site), así que la
> app carga al instante y muestra un aviso mientras la API despierta. Hay keep-alive configurado.

### Credenciales — los 3 roles

Contraseña común: la definida en `DEMO_PASSWORD`.

| Rol | Correo | Qué puede hacer |
|---|---|---|
| **Creador** | `creator@alicorp.demo` | Crea marcas, genera manuales y contenido |
| **Aprobador A** · texto | `approver.a@alicorp.demo` | Revisa y aprueba/rechaza textos |
| **Aprobador B** · visual | `approver.b@alicorp.demo` | Audita imágenes contra el manual |

En `/login` hay tres botones que entran directo a cada rol: se prueban las tres vistas en 15 segundos.

### Guion de demo sugerido (3 min)

1. **Login como Creador.** Abrir una marca ya generada → recorrer el manual: espectro de voz,
   léxico con chips rojos/verdes, paleta con contraste WCAG calculado, y las **reglas con su
   `check_hint`**.
2. **Creative Engine.** Generar un post. Fijarse en los `rule_id` que se aplicaron y, si aparece,
   en el bloque de violaciones que el guardrail corrigió.
3. **Login como Aprobador A.** La misma app, otra navegación. Aprobar el texto.
4. **Login como Aprobador B.** Subir `backend/tests/fixtures/images/pieza_mala.png` →
   el dictamen dice *«el logo ocupa cerca del 4.1 % del ancho, por debajo del mínimo de 8 %»*
   citando `visual.visual.el_logo_debe_ocupar_al_menos`.
5. **Langfuse.** Mostrar la traza: el contexto recuperado del RAG, el prompt y las latencias.

---

## Los 4 módulos

| Módulo | Estado | Dónde vive |
|---|---|---|
| **I — Brand DNA Architect** | ✅ | `backend/app/modules/brand_dna/` · `frontend/src/features/brands/` |
| **II — Creative Engine** | ✅ | `backend/app/modules/creative/` · `frontend/src/features/content/` |
| **III — Governance & Multimodal Audit** | ✅ | `backend/app/modules/governance/` · `frontend/src/features/governance/` |
| **IV — Observabilidad (Langfuse)** | ✅ | `backend/app/ai/observability.py` + instrumentación transversal |

---

## Arquitectura

```
┌──────────────────────────┐        ┌────────────────────────────────┐
│  Render Static Site      │        │  Render Web Service            │
│  React 19 · Vite · TS    │        │  FastAPI · Python 3.13         │
│  Tailwind v4 · shadcn/ui │        │                                │
│                          │        │  modules/                      │
│  rewrite /api/*  ────────┼───────►│    auth · brand_dna            │
│  (mismo origen: sin CORS)│        │    creative(LangGraph)         │
│  rewrite /* → index.html │        │    governance                  │
│  NO duerme               │        │  ───────────────────────────   │
└──────────────────────────┘        │  ai/  (compartido)             │
                                    │    llm ─┬─ openai_provider     │
                                    │         └─ gemini_provider     │
                                    │    chunking · embeddings       │
                                    │    retrieval · postprocess     │
                                    └────────┬──────────┬────────────┘
                                             │          │
                              ┌──────────────▼──┐  ┌────▼──────────────┐
                              │ Supabase        │  │ OpenAI            │
                              │ Postgres 17     │  │ gpt-5.6-luna      │
                              │ pgvector(1536)  │  │ embedding-3-small │
                              │ HNSW · RLS      │  └───────────────────┘
                              └─────────────────┘           │
                                                   ┌────────▼────────┐
                                                   │ Langfuse Cloud  │
                                                   └─────────────────┘
```

**Todo en Render, un solo Blueprint.** El static site proxea `/api/*` hacia la API, así que
frontend y backend comparten origen y **CORS desaparece por completo**.

---

## Correr en local

**Requisitos:** Python 3.13, Node 22, un proyecto de Supabase, una API key de OpenAI.

```bash
# Backend
cd backend
python -m venv ../.venv && ../.venv/Scripts/activate   # Linux/macOS: source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # rellenar DATABASE_URL y OPENAI_API_KEY

python scripts/verify_setup.py   # 5 comprobaciones: BD, pgvector, modelos, dims, Langfuse
python scripts/migrate.py        # aplica db/migrations/*.sql en orden
python scripts/seed_users.py     # los 3 usuarios de demo
python scripts/seed_demo.py      # 2 marcas con manual ya generado e indexado

uvicorn app.main:app --reload --port 8010    # → http://127.0.0.1:8010/docs
```

```bash
# Frontend
cd frontend && npm install && cp .env.example .env && npm run dev   # → http://localhost:5173
```

El `vite.config.ts` proxea `/api` a `127.0.0.1:8010`, reproduciendo en local la misma condición de
mismo-origen que hay en producción. Así CORS no entra en juego ni en desarrollo ni desplegado.

### Scripts de demostración

```bash
python scripts/demo_rag.py     # el pre-filtrado por dominio, consulta a consulta
python scripts/demo_audit.py   # auditoría multimodal sobre dos piezas controladas
python scripts/demo_e2e.py     # el flujo completo de los 4 módulos contra la API
python scripts/make_test_images.py   # genera las piezas de prueba
```

---

## Decisiones de diseño y trade-offs

### 1. Cada regla del manual es un objeto, no una frase

El schema modela cada regla como
`{id, statement, severity: hard|soft, modality: text|visual, check_hint}`.

El campo decisivo es **`check_hint`**: obliga al modelo a escribir reglas **medibles**.

| ❌ Inútil para auditar | ✅ Verificable |
|---|---|
| «el logo debe verse bien» | «el logo debe ocupar ≥ 8 % del ancho de la pieza» |
| «usar colores cálidos» | «`#E8552D` primario, máximo 40 % del área» |
| «buena legibilidad» | «contraste texto/fondo ≥ 4.5:1 (WCAG AA)» |

Sin esto, el Módulo III solo podría opinar. **Con esto, mide**: sobre una pieza con el logo al 4 %,
el dictamen real fue *«el logo ocupa cerca del 4.1 % del ancho, por debajo del mínimo exigido de 8 %»*.

### 2. Chunking semántico derivado del schema, no de tamaño fijo

El argumento decisivo no es que el chunking fijo rompa frases, sino que **sin metadata limpia no
hay pre-filtrado**: un chunk que mezcla el final de «tono de voz» con el inicio de «paleta de color»
no puede etiquetarse, y entonces una consulta sobre el logo devuelve reglas de léxico.

```
Módulo II  → modality IN ('text','both')   AND rule_type IN ('tone','lexicon','grammar',…)
Módulo III → modality IN ('visual','both') AND rule_type IN ('color','logo','photography',…)
```

Verificado: la consulta *«¿qué palabras están prohibidas?»* con filtro `text` devuelve `lexicon`
como primer resultado; **la misma consulta con filtro `visual` no devuelve ni una regla de léxico**.

### 3. RAG para guía, código para restricciones duras

El léxico prohibido **no** se verifica por similitud vectorial: un check de palabra prohibida
necesita 100 % de recall, y la búsqueda semántica podría devolver 8 de 15 términos.

- `manual_chunks` (vectores) → reglas de *guía*: tono, composición, estética.
- `brand_manuals.content` (JSONB) → listas *duras* por SQL directo (`get_hard_lexicon`), aplicadas
  con el `match_mode` de cada término (`exact` → `\bpalabra\b`, `stem` → raíz y derivados,
  `regex` → patrón). Elegir `exact` donde hacía falta `stem` dejaría pasar «adelgazante».

### 4. LangGraph solo en el Módulo II

El Módulo I es un fan-out sin ciclos (`estrategia → verbal ∥ visual ∥ compliance`): `asyncio.gather`
lo expresa mejor y envolverlo en un grafo sería ceremonia. El Módulo II sí tiene una **arista
condicional y un ciclo**:

```
retrieve ──► generate ──► validate ──┬─ sin violaciones ─► END
   ▲                                 │
   └────────── repair ◄──────────────┘  violaciones hard y intentos < 2
```

Los nodos llaman a `app/ai/llm.py`: **no entra `langchain-openai`** y la abstracción de proveedor
sigue intacta.

### 5. Capa de proveedor intercambiable — y por qué se pagó sola

`LLM_PROVIDER=openai|gemini` despacha al módulo correspondiente. No es abstracción especulativa:
el proyecto empezó con Gemini y hubo que migrar a mitad de camino al descubrir que **su free tier
limita a 20 peticiones AL DÍA por modelo** (`GenerateRequestsPerDayPerProjectPerModel`, verificado
contra la API). Con 4 llamadas por manual son 5 manuales diarios contando los del evaluador: la
demo habría muerto con un 429. **La migración tocó un archivo.**

Se usa `gpt-5.6-luna` con `reasoning.effort = "none"`: estas tareas son generación estructurada
guiada por prompts detallados, no resolución de problemas.

### 6. Embeddings a 1536 dimensiones

**pgvector no puede indexar más de 2000 dimensiones con el tipo `vector`.** Con las 3072 por
defecto de Gemini, la tabla funciona pero el índice HNSW **no se crea** — un fallo silencioso que
aparecería recién al usar el RAG. `text-embedding-3-small` es nativo de 1536: cero truncado, cero
migración.

### 7. `202 Accepted` + polling en el Módulo I

La generación del manual tarda ~80 s. Con `await`, recargar la página perdería el trabajo y una
llamada de cupo; el peor caso sería *cold start + generación* en un solo request HTTP. Con polling,
el estado vive en Postgres y el frontend muestra un **stepper con las etapas reales** del agente.

El Módulo II sí es síncrono (~15 s): reservar el patrón asíncrono para lo que de verdad tarda un
minuto mantiene la UI simple donde puede serlo.

### 8. Generación multi-etapa, no una sola llamada

El schema completo son ~22 KB de JSON Schema; a esa escala el modelo trunca listas e ignora
`minItems`. Cada etapa es 2-7× menor, se reintenta sola, y las etapas alimentan el progreso real.

### 9. JWT propio, no Supabase Auth

Control total del RBAC con una dependencia (`require_role`) y cero integración extra. Contrapartida
asumida: el backend se conecta con un rol que **bypassa RLS**, así que la autorización vive en
FastAPI. Por eso la migración `0002` **cierra la puerta de PostgREST** — sin eso, cualquiera con la
`anon key` (pública por diseño) podría leer `users.password_hash`.

Librerías: **PyJWT** (no `python-jose`, abandonado con CVE-2024-33663 sin parche) y **bcrypt
directo** (no `passlib`, roto con `bcrypt>=4.1`).

### 10. Los aprobadores leen los manuales

En el Módulo III el Aprobador A juzga si un texto respeta el léxico y el B si una imagen respeta la
paleta: sin acceso al manual, aprobar sería arbitrario. **RBAC bien hecho es una matriz de permisos,
no muros** — tres roles sobre el *mismo* recurso con capacidades distintas. La restricción va sobre
las **mutaciones** y la aplica el backend.

---

## Observabilidad (Módulo IV)

Dos capas:

1. **Automática.** `langfuse.openai` es un reemplazo directo del SDK: cada llamada genera su span
   con modelo, prompt, respuesta, tokens y latencia, sin código adicional.
2. **Árbol manual** mediante el helper `traced()`:

```
TRACE  brand_manual.generate
├─ GENERATION  gpt-5.6-luna · strategy
├─ GENERATION  gpt-5.6-luna · verbal / visual / compliance  (en paralelo)
├─ SPAN  manual.chunk        {chunks: 29, by_modality: {...}}
└─ SPAN  manual.embed        text-embedding-3-small · 1536 dims

TRACE  creative.generate
├─ RETRIEVER  rag.retrieve   ⭐ query, filtros y los chunks recuperados con su similarity
├─ GENERATION gpt-5.6-luna
└─ output     {rules_used, violations_fixed, repair_attempts}

TRACE  visual_audit          {verdict, findings, rules_checked, latency_ms}
```

El `rag.retrieve` registra **qué contexto se recuperó**, con `rank`, `section`, `rule_type`,
`similarity` y un preview de cada chunk — el requisito literal del enunciado. Se instrumenta en
`retrieval.py` y no en cada módulo, para que ninguno pueda olvidarlo.

El `langfuse_trace_id` se **persiste** en `brand_manuals` y `content_pieces` y se devuelve por la
API, así que desde la UI se puede saltar a la traza.

---

## Base de datos

| Tabla | Propósito |
|---|---|
| `users` | 3 roles: `creator`, `approver_a`, `approver_b` (+`admin`) |
| `brands` | Marca + `brief` JSONB con los parámetros del usuario |
| `brand_manuals` | Versiones: `content` JSONB, `status`, `stage`, `langfuse_trace_id` |
| `manual_chunks` | Chunks + `embedding vector(1536)` + metadata de pre-filtrado + `content_tsv` |
| `content_pieces` | Módulo II, con `retrieved_rule_ids` para trazabilidad del RAG |
| `approvals` | Historial completo de decisiones: quién aprobó qué y cuándo |
| `visual_audits` | Hallazgos que **citan** el `rule_id` evaluado |

Índices: HNSW sobre `embedding`, compuesto `(brand_id, modality, rule_type)` para el pre-filtrado,
único parcial de «un solo manual publicado por marca», y GIN sobre `content`.
Funciones: `match_manual_chunks(...)` y `get_hard_lexicon(...)`.

Migraciones idempotentes con registro en `schema_migrations` (`python scripts/migrate.py`).

---

## Tests

```bash
cd backend && pytest        # 63 tests, sin red, sobre un fixture escrito a mano
```

Cubren lo que de romperse falla en silencio: los tres `match_mode` del validador de léxico
(incluidos falsos positivos y regex inválidos), el ciclo del grafo (converge, se detiene en
`MAX_REPAIRS` y reporta lo no resuelto), la separación de dominios del chunking, el RBAC devolviendo
403, y los invariantes de configuración (dimensión indexable, dominios RAG disjuntos).

El fixture de manual está **escrito a mano con los propios modelos Pydantic**: hace imposible un
fixture inválido y permite desarrollar chunking, RAG y UI sin gastar llamadas al modelo.

---

## Limitaciones conocidas

- **Cold start.** El web service duerme tras 15 min y tarda ~1 min en despertar. Mitigado con
  keep-alive doble, ping al montar el login y un banner explícito. El static site no duerme.
- **Presupuesto de Render.** 750 h/mes por workspace y el mes tiene 744: el keep-alive corre en
  ventana horaria porque pasarse **suspende todos** los servicios gratis de la cuenta.
- **El timeout del proxy de rewrite de Render no está documentado.** Si resultara menor a ~60 s, la
  primera llamada contra una API dormida se cortaría. Plan B listo: cambiar `VITE_API_BASE_URL` a la
  URL absoluta — el middleware de CORS ya está configurado para eso.
- **La auditoría visual estima, no mide con precisión de píxel.** El modelo aproxima proporciones
  mirando la imagen; en las pruebas acertó (44 px medidos sobre 43 px reales), pero para reglas
  críticas lo correcto sería complementar con visión por computador clásica. Los hallazgos llevan
  `confidence` justamente para no tratar una estimación dudosa como un hecho.
- **`BackgroundTasks` no sobrevive a un redeploy.** Hay reconciliación al arrancar: los manuales en
  `generating` con más de 10 min pasan a `failed` con mensaje explícito.
- **Las imágenes auditadas se guardan como data URI** en la BD. En producción irían a Supabase
  Storage; para la evaluación evita depender de un bucket más.
- **Los tipos TypeScript son un espejo manual** de los schemas Pydantic. Para este alcance es lo
  correcto; si el contrato crece, el paso natural es `openapi-typescript` contra `/openapi.json`.
- **El contenido generado por IA requiere validación legal y nutricional** antes de uso comercial.

---

## Despliegue

1. **Supabase** → SQL Editor: `create extension if not exists vector;` y luego
   `python scripts/migrate.py` con el connection string del **Session Pooler**
   (la conexión directa es IPv6-only y Render no la alcanza).
2. **Render** → New → Blueprint → conectar el repo. `render.yaml` declara los dos servicios.
   Rellenar los secretos marcados `sync: false`: `DATABASE_URL`, `OPENAI_API_KEY`,
   `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `DEMO_PASSWORD`.
3. Si Render asigna otro host a la API, actualizar el `destination` del rewrite en `render.yaml`.
4. Sembrar en producción: `python scripts/seed_users.py && python scripts/seed_demo.py`.
5. Configurar un pinger externo (cron-job.org) además del workflow de GitHub Actions.

**El orden de las `routes` del static site importa:** el rewrite de `/api/*` va **primero**; si el
fallback SPA quedara arriba, se tragaría las llamadas a la API.

---

## Estructura

```
Content-Suite/
├── render.yaml              # Blueprint único: API + SPA + rewrite /api/*
├── backend/
│   ├── app/
│   │   ├── core/            # config · security · deps(RBAC) · exceptions · enums
│   │   ├── db/              # session(Session Pooler) · models
│   │   ├── ai/              # ⭐ compartido por los 4 módulos
│   │   │   ├── llm.py       #   dispatcher de proveedor
│   │   │   ├── providers/   #   openai · gemini
│   │   │   ├── schemas/     #   brand_manual.py ← el contrato central
│   │   │   └── chunking · embeddings · retrieval · postprocess · observability
│   │   └── modules/         # auth · brand_dna · creative · governance
│   ├── db/migrations/       # SQL idempotente y numerado
│   ├── scripts/             # verify_setup · migrate · seed · demo_*
│   └── tests/
└── frontend/src/
    ├── app/router.tsx       # ← registro de rutas
    ├── config/nav.ts        # ← registro de navegación
    └── features/            # auth · brands(I) · content(II) · governance(III)
```

`app/ai/` vive **fuera** de `modules/` a propósito: el Módulo II necesita `retrieval` y el III
`generate_vision`. Si esas piezas vivieran dentro de `brand_dna/`, los módulos siguientes
importarían «hacia adentro» de otro módulo — el anti-patrón que obliga a refactorizar.
