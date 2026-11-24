#!/usr/bin/env python3
"""
getonbrd_api.py — avisos desde la API pública de GetOnBoard (sin navegador ni cuenta).

La API trae modalidad remota, países, sueldo, seniority, idioma y descripción como datos,
así los filtros no adivinan sobre el texto. Categorías y búsquedas salen de config.json.

    python3 getonbrd_api.py          # lista los que pasan, por puntaje
    python3 getonbrd_api.py --all    # también los descartados y por qué
"""
from __future__ import annotations
import json, re, html, sys, time, urllib.request, urllib.parse
import config, criterio

C = config.cargar()
API = "https://www.getonbrd.com/api/v0"
CATEGORIES = tuple(C["getonbrd_categorias"])
QUERIES = tuple(C["busquedas"])

# seniority de la API: 1 sin experiencia, 2 junior, 3 semi senior, 4 senior, 5 expert
SENIORITY = {1: "No experience", 2: "Junior", 3: "Semi Senior", 4: "Senior", 5: "Expert"}


def _get(path: str, params: dict) -> dict:
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _text(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def slug(url: str) -> str:
    """Último tramo de la URL: los logs viejos guardan /jobs/<categoría>/<slug>, la API /jobs/<slug>."""
    return url.rstrip("/").split("?")[0].rsplit("/", 1)[-1]


def to_job(item: dict) -> dict:
    a = item["attributes"]
    comp = ((a.get("company") or {}).get("data") or {}).get("attributes") or {}
    sen = ((a.get("seniority") or {}).get("data") or {}).get("id")
    tenants = [t["id"] for t in ((a.get("location_tenants") or {}).get("data") or [])]
    desc = " ".join(_text(a.get(k)) for k in ("description", "functions", "desirable", "benefits") if a.get(k))
    lang = a.get("lang") or "es"
    if lang not in ("es", "en"):   # la API a veces dice "lang_not_specified": se mira el texto
        lang = "en" if len(re.findall(r"\b(the|and|with|you|our|will)\b", desc.lower())) > \
                       len(re.findall(r"\b(el|la|los|con|para|que|nuestro)\b", desc.lower())) else "es"
    return {
        "id": item["id"],
        "source": "getonbrd",
        "url": item["links"]["public_url"],
        "title": a["title"].strip(),
        "company": comp.get("name", ""),
        "company_about": _text(comp.get("long_description") or comp.get("description"))[:600],
        "company_country": comp.get("country") or "",    # país de la empresa: criterio.local() decide la moneda
        "remote": a.get("remote"),
        "remote_modality": a.get("remote_modality"),     # fully_remote | remote_local | hybrid | no_remote
        "remote_zone": a.get("remote_zone"),
        "countries": a.get("countries") or [],
        "tenants": tenants,                               # país desde donde se puede trabajar (remote_local)
        "min_salary": a.get("min_salary"),
        "max_salary": a.get("max_salary"),
        "seniority": SENIORITY.get(sen, ""),
        "lang": lang,
        "category": a.get("category_name", ""),
        "published_at": a.get("published_at"),
        "applications": a.get("applications_count"),
        "desc": desc[:6000],
    }


def fetch(categories=CATEGORIES, queries=QUERIES, per_page=100, max_pages=5) -> list[dict]:
    jobs, seen, seen_tc = [], set(), set()

    def take(items):
        for it in items:
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            job = to_job(it)
            tc = (job["title"].lower(), job["company"].lower())   # mismo aviso publicado en dos ciudades
            if tc in seen_tc:
                continue
            seen_tc.add(tc); jobs.append(job)

    expand = '["company","location_tenants"]'
    for cat in categories:
        for page in range(1, max_pages + 1):
            try:
                d = _get(f"categories/{cat}/jobs", {"per_page": per_page, "page": page, "expand": expand})
            except Exception as e:   # una categoría mal escrita o caída no bota el feed
                print(f"[getonbrd] categoría '{cat}' falló: {str(e)[:60]}", file=sys.stderr); break
            take(d.get("data", []))
            if page >= (d.get("meta") or {}).get("total_pages", 1):
                break
            time.sleep(0.4)
    for q in queries:
        try:
            d = _get("search/jobs", {"query": q, "per_page": per_page, "expand": expand})
        except Exception as e:   # una búsqueda caída no bota el feed
            print(f"[api] búsqueda '{q}' falló: {str(e)[:60]}", file=sys.stderr); continue
        take(d.get("data", []))
        time.sleep(0.4)
    return jobs


# ---------- filtros ----------
JUNIORES = ("No experience", "Junior")


def role_ok(job: dict) -> tuple[bool, str]:
    if C["excluir_junior"] and job["seniority"] in JUNIORES:
        return False, f"seniority {job['seniority']}"
    nivel, why = criterio.rol(job["title"])
    return (nivel in ("A", "B"), why if nivel != "C" else "rol por revisar")


def location_ok(job: dict) -> tuple[bool, str]:
    # remote_modality: fully_remote (desde cualquier lugar) | remote_local (remoto solo desde los países de
    # location_tenants) | hybrid | no_remote
    mod, pais = job["remote_modality"], (C["pais_getonbrd"] or C["pais"] or "").lower()
    if mod == "fully_remote":
        return True, "remoto desde cualquier lugar"
    if mod == "remote_local":
        if pais and pais in job["tenants"]:
            return True, f"remoto desde {C['pais'] or pais}"
        if not job["tenants"]:
            return False, "remoto local sin país declarado"
        return False, f"remoto solo desde {', '.join(job['tenants'])}"
    if not C["solo_remoto"] and pais and pais in job["tenants"]:
        return True, f"{mod} en {C['pais'] or pais}"
    return False, f"no es remoto ({mod})"


def salary_ok(job: dict) -> tuple[bool, str]:
    return criterio.sueldo_ok(job)


def screen(job: dict) -> tuple[bool, str]:
    for check in (role_ok, location_ok, salary_ok):
        ok, why = check(job)
        if not ok:
            return False, why
    return True, location_ok(job)[1]


def veredicto(job: dict) -> tuple[str, str]:
    """match (para la tanda) | revisar (lo decides tú) | skip."""
    ok, why = screen(job)
    if ok:
        if criterio.exige_de_mas(job):
            return "revisar", f"pide {criterio.exige_de_mas(job)}+ años"
        return "match", why
    s_ok, _ = salary_ok(job)
    if not s_ok or (C["excluir_junior"] and job["seniority"] in JUNIORES):
        return "skip", why
    nivel, _ = criterio.rol(job["title"])
    loc_ok, loc_why = location_ok(job)
    if nivel == "C" and loc_ok:
        return "revisar", "calce discutible"
    if nivel in ("A", "B") and loc_why == "remoto local sin país declarado":
        return "revisar", "remoto, pero el aviso no dice desde qué países"
    return "skip", why


if __name__ == "__main__":
    show_all = "--all" in sys.argv
    jobs = fetch()
    print(f"[api] {len(jobs)} avisos ({len(CATEGORIES)} categorías + {len(QUERIES)} búsquedas)")
    rows = []
    for j in jobs:
        v, why = veredicto(j)
        rows.append((criterio.puntaje(j)[0] if v != "skip" else -1, v, why, j))
    for pts, v, why, j in sorted(rows, key=lambda r: -r[0]):
        if v != "skip" or show_all:
            sal = f"{j['min_salary'] or '?'}-{j['max_salary'] or '?'}"
            print(f"[{v:7}] {pts:3} | {j['title'][:48]:48} | {j['company'][:20]:20} | {sal:11} | {why}")
