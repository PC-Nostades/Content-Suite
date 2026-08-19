"""Flujo completo de los 4 módulos contra la API real.

    python scripts/demo_e2e.py

Recorre la cadena que verá el evaluador y comprueba las garantías que el reto
evalúa. Guardar esta salida: es la evidencia para la presentación.
"""

import asyncio
from pathlib import Path

import _bootstrap  # noqa: F401

import httpx

BASE = "http://127.0.0.1:8010"
PWD = "Alicorp2026!"
IMAGENES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "images"

OK, NO = "  OK  ", "FALLA "


async def login(c: httpx.AsyncClient, email: str) -> str:
    r = await c.post("/api/v1/auth/login", json={"email": email, "password": PWD})
    r.raise_for_status()
    return r.json()["access_token"]


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def main() -> int:
    fallos = 0
    async with httpx.AsyncClient(base_url=BASE, timeout=300) as c:
        creator = await login(c, "creator@alicorp.demo")
        aprob_a = await login(c, "approver.a@alicorp.demo")
        aprob_b = await login(c, "approver.b@alicorp.demo")
        print("Sesiones abiertas para los 3 roles.\n")

        # ── RBAC ────────────────────────────────────────────────────────────
        print("=" * 74)
        print("  GOBERNANZA · el RBAC se aplica en el servidor")
        print("=" * 74)
        r = await c.post("/api/v1/brands", headers=h(aprob_b), json={
            "brief": {"brand_name": "X", "product_category": "yyy",
                      "tone": "zzz", "target_audience": "wwww"}})
        estado = OK if r.status_code == 403 else NO
        if r.status_code != 403:
            fallos += 1
        print(f"  {estado} aprobador crea marca → {r.status_code} "
              f"({r.json().get('detail', {}).get('message', '')[:60]})")

        # ── RAG ─────────────────────────────────────────────────────────────
        brands = (await c.get("/api/v1/brands", headers=h(creator))).json()
        brand = next(b for b in brands if b["manual_status"] == "published")
        bid = brand["id"]
        print(f"\n  Marca de prueba: {brand['brand_name']}")

        print("\n" + "=" * 74)
        print("  RAG · el pre-filtrado por dominio")
        print("=" * 74)
        for modality in ("visual", "text"):
            r = await c.post("/api/v1/rag/search", headers=h(creator), json={
                "brand_id": bid, "query": "¿qué palabras están prohibidas?",
                "modality": modality, "top_k": 5})
            tipos = sorted({x["rule_type"] for x in r.json()["results"]})
            hay_lexico = "lexicon" in tipos
            esperado = (modality == "text")
            estado = OK if hay_lexico == esperado else NO
            if hay_lexico != esperado:
                fallos += 1
            print(f"  {estado} modality={modality:<7} → {tipos}")
        print("        ↑ la MISMA consulta: solo el filtro de texto alcanza el léxico")

        # ── Módulo II ───────────────────────────────────────────────────────
        print("\n" + "=" * 74)
        print("  MÓDULO II · Creative Engine (LangGraph)")
        print("=" * 74)
        r = await c.post("/api/v1/content", headers=h(creator), json={
            "brand_id": bid, "type": "social_post", "channel": "instagram",
            "brief": "Post de lanzamiento del formato 30 g para vuelta a clases."})
        if r.status_code != 200:
            print(f"  {NO} {r.status_code}: {r.text[:200]}")
            return 1
        pieza = r.json()
        print(f"  {OK} pieza generada · estado={pieza['status']}")
        print(f"        título   : {pieza['title'][:60]}")
        print(f"        reglas RAG aplicadas : {len(pieza['retrieved_rule_ids'])}")
        print(f"        violaciones corregidas: {len(pieza['fixed_violations'])}")
        print(f"        violaciones restantes : {len(pieza['remaining_violations'])}")

        # ── Módulo III ──────────────────────────────────────────────────────
        print("\n" + "=" * 74)
        print("  MÓDULO III · Gobernanza y auditoría multimodal")
        print("=" * 74)

        r = await c.post(f"/api/v1/submissions/{pieza['id']}/decision",
                         headers=h(aprob_b), json={"decision": "approved"})
        estado = OK if r.status_code == 403 else NO
        if r.status_code != 403:
            fallos += 1
        print(f"  {estado} Aprobador B decide en la etapa A → {r.status_code} (debe ser 403)")

        r = await c.post(f"/api/v1/submissions/{pieza['id']}/decision",
                         headers=h(aprob_a), json={"decision": "approved", "comment": "Tono correcto."})
        estado = OK if r.status_code == 200 else NO
        if r.status_code != 200:
            fallos += 1
        print(f"  {estado} Aprobador A aprueba el texto → estado={r.json().get('status')}")

        # Se compara el veredicto de la REGLA DEL LOGO, no el veredicto global.
        # Ambas piezas son sintéticas y carecen de octógonos, gramaje y sello de
        # origen, así que las dos incumplen otras reglas del manual — con razón.
        # La única variable controlada entre ellas es el tamaño del logo, y es
        # eso lo que la prueba debe medir.
        for nombre, esperado_logo in (("pieza_mala.png", "fail"), ("pieza_ok.png", "pass")):
            ruta = IMAGENES / nombre
            if not ruta.exists():
                print(f"  (falta {nombre}; ejecuta make_test_images.py)")
                continue
            r = await c.post(
                "/api/v1/audit/image", headers=h(aprob_b),
                data={"brand_id": bid, "content_piece_id": pieza["id"]},
                files={"file": (nombre, ruta.read_bytes(), "image/png")},
            )
            if r.status_code != 200:
                print(f"  {NO} auditoría de {nombre}: {r.status_code} {r.text[:150]}")
                fallos += 1
                continue
            a = r.json()
            logo = next((f for f in a["findings"] if "logo" in f["rule_id"]), None)
            veredicto_logo = logo["verdict"] if logo else "(no evaluada)"
            estado = OK if veredicto_logo == esperado_logo else NO
            if veredicto_logo != esperado_logo:
                fallos += 1
            print(f"  {estado} {nombre:<16} regla del logo → {veredicto_logo:<5} "
                  f"(global={a['verdict']}, {len(a['findings'])} hallazgos, {a['latency_ms']} ms)")
            if logo:
                print(f"        cita   : {logo['rule_id']}")
                print(f"        mide   : {logo['evidence'][:110]}")

        r = await c.post(f"/api/v1/submissions/{pieza['id']}/visual-decision",
                         headers=h(aprob_b), json={"decision": "approved", "comment": "Visual OK."})
        estado = OK if r.status_code == 200 else NO
        if r.status_code != 200:
            fallos += 1
        print(f"  {estado} Aprobador B cierra el flujo → estado={r.json().get('status')}")

    print("\n" + "=" * 74)
    print(f"  {'TODO CORRECTO' if fallos == 0 else f'{fallos} COMPROBACIONES FALLARON'}")
    print("=" * 74)
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
