#!/usr/bin/env python3
"""
directo.py — busca el link directo de postulación de un aviso en la bolsa pública de la empresa
(Greenhouse, Ashby, Lever; también Workable, Recruitee, SmartRecruiters y Breezy). Sin navegador y sin cuenta.

Por qué: varias bolsas esconden el botón de postular detrás de crear una cuenta, y LinkedIn manda
al sitio de la empresa. Greenhouse, Ashby y Lever publican sus avisos con una API abierta: ahí está
el texto completo, desde qué país se puede trabajar y el formulario sin login. Un aviso con link
directo es uno que el agente puede llenar de punta a punta (y enviar con tu OK).

    python3 directo.py "Empresa" "Título del aviso"
    from directo import enlazar; enlazar(filas_de_la_cola)   # agrega apply_url / ats / ats_lugar

Greenhouse además entrega las preguntas del formulario: `preguntas("able", "8610714002")`.
Sirve para saber antes de abrirlo si pide algo que solo tú puedes contestar (certificado de notas, visa).
"""
from __future__ import annotations
import concurrent.futures as cf, json, re, sys, urllib.request
from pathlib import Path

import config, fuentes

CACHE = config.CACHE / "links_directos.json"
UA = {"User-Agent": "Mozilla/5.0 (postula: radar personal de empleo)", "Accept": "application/json"}
RUIDO = {"the", "and", "of", "senior", "sr", "remote", "latam", "only", "job", "id", "for", "to", "in", "a"}


def _get(url: str, timeout=12):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def toks(empresa: str) -> list[str]:
    """Cómo puede llamarse la empresa en la URL de su bolsa: 'Customer.io' -> customerio, customer."""
    n = re.sub(r"\(.*?\)|,? (inc|llc|ltd|limited|corp|corporation|company|co|spa)\.?$", "", (empresa or "").lower()).strip()
    base = re.sub(r"[^a-z0-9 ]", "", n)
    partes = base.split()
    out = {"".join(partes), "-".join(partes)}
    if partes:
        out.add(partes[0])
    return sorted(t for t in out if len(t) > 2)


def _pal(s: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()) - RUIDO


def _calza(pedido: str, hallado: str) -> bool:
    # todas las palabras de uno están en el otro ("Product Manager" ~ "Product Manager - Trading API").
    # Una palabra distinta ya es otro cargo: Program Manager no es Product Manager.
    a, b = _pal(pedido), _pal(hallado)
    return min(len(a), len(b)) >= 2 and (a <= b or b <= a)


def buscar(empresa: str, titulo: str) -> list[dict]:
    """Todas las publicaciones de esa empresa que calzan con el título (suele haber una por país)."""
    out = []
    for t in toks(empresa):
        d = _get(f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs")
        for j in (d or {}).get("jobs", []):
            if _calza(titulo, j["title"]):
                out.append({"ats": "greenhouse", "tablero": t, "titulo": j["title"].strip(),
                            "lugar": (j.get("location") or {}).get("name") or "", "url": j["absolute_url"], "id": str(j["id"])})
        d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{t}")
        for j in (d or {}).get("jobs", []):
            if _calza(titulo, j["title"]):
                out.append({"ats": "ashby", "tablero": t, "titulo": j["title"].strip(),
                            "lugar": j.get("location") or "", "url": j.get("applyUrl") or j.get("jobUrl"), "id": j.get("id", "")})
        d = _get(f"https://api.lever.co/v0/postings/{t}?mode=json")
        for j in (d if isinstance(d, list) else []):
            if _calza(titulo, j["text"]):
                out.append({"ats": "lever", "tablero": t, "titulo": j["text"].strip(),
                            "lugar": (j.get("categories") or {}).get("location") or "", "url": j.get("hostedUrl"), "id": j.get("id", "")})
        # bolsas menos comunes, misma idea: listado público sin cuenta
        d = _get(f"https://apply.workable.com/api/v1/widget/accounts/{t}?details=false")
        for j in (d or {}).get("jobs", []):
            if _calza(titulo, j.get("title", "")):
                lugar = ", ".join(x for x in (j.get("city"), j.get("country")) if x) + (" (remote)" if j.get("telecommuting") else "")
                out.append({"ats": "workable", "tablero": t, "titulo": j["title"].strip(), "lugar": lugar,
                            "url": j.get("url") or j.get("application_url"), "id": j.get("shortcode", "")})
        d = _get(f"https://{t}.recruitee.com/api/offers/")
        for j in (d or {}).get("offers", []):
            if _calza(titulo, j.get("title", "")):
                out.append({"ats": "recruitee", "tablero": t, "titulo": j["title"].strip(),
                            "lugar": (j.get("location") or "") + (" (remote)" if j.get("remote") else ""),
                            "url": j.get("careers_url"), "id": str(j.get("id", ""))})
        d = _get(f"https://api.smartrecruiters.com/v1/companies/{t}/postings?limit=100")
        for j in (d or {}).get("content", []):
            if _calza(titulo, j.get("name", "")):
                loc = j.get("location") or {}
                out.append({"ats": "smartrecruiters", "tablero": t, "titulo": j["name"].strip(),
                            "lugar": ", ".join(x for x in (loc.get("city"), loc.get("country")) if x) + (" (remote)" if loc.get("remote") else ""),
                            "url": f"https://jobs.smartrecruiters.com/{t}/{j.get('id')}", "id": str(j.get("id", ""))})
        d = _get(f"https://{t}.breezy.hr/json")
        for j in (d if isinstance(d, list) else []):
            if _calza(titulo, j.get("name", "")):
                loc = j.get("location") or {}
                out.append({"ats": "breezy", "tablero": t, "titulo": j["name"].strip(),
                            "lugar": (loc.get("name") or "") + (" (remote)" if loc.get("is_remote") else ""),
                            "url": j.get("url"), "id": j.get("id", "")})
        if out:
            break
    return out


# de las publicaciones de un mismo aviso (suele haber una por país), cuál sirve desde tu país
def elegir(hallazgos: list[dict]) -> dict | None:
    """La publicación que nombra tu país; si no, la que abre tu zona; si no, la que solo dice 'Remote'."""
    for ok in (lambda l: fuentes.nombra_pais(l), lambda l: fuentes.abre_zona(l),
               lambda l: re.fullmatch(r"\s*remote( job)?\s*(\(remote\))?\s*", l, re.I)):
        for h in hallazgos:
            if ok(h["lugar"] or ""):
                return h
    return None


def preguntas(tablero: str, job_id: str) -> list[dict]:
    """Preguntas del formulario de Greenhouse (sin las de contacto). [{label, required, type, opciones}]"""
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{tablero}/jobs/{job_id}?questions=true") or {}
    base = {"first name", "last name", "preferred first name", "email", "phone", "resume/cv", "cover letter"}
    out = []
    for q in d.get("questions", []):
        if q["label"].strip().lower() in base:
            continue
        f = q["fields"][0]
        out.append({"label": re.sub(r"\s+", " ", q["label"]).strip(), "required": bool(q.get("required")),
                    "type": f["type"], "opciones": [v["label"] for v in f.get("values", [])]})
    return out


# preguntas que el agente no responde por ti: el aviso queda para que lo decidas
SOLO_TU = re.compile(r"transcript|gpa|promedio ponderado|certificado de notas|sponsor|authorized to work in the u|"
                       r"security clearance|date of birth|passport|bachelor|degree|t[ií]tulo (universitario|profesional)|"
                       r"highest level of education", re.I)


def trabas(qs: list[dict]) -> list[str]:
    return [q["label"][:80] for q in qs if q["required"] and SOLO_TU.search(q["label"])]


def enlazar(filas: list[dict], tope=80) -> int:
    """Le agrega apply_url / ats / ats_lugar a las primeras `tope` filas de la cola. Devuelve cuántas quedaron con link."""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if isinstance(cache, list):   # formato viejo
        cache = {}
    pend = [f for f in filas[:tope] if f.get("source") != "getonbrd" and f"{f['company']}|{f['title']}" not in cache]
    with cf.ThreadPoolExecutor(3) as ex:   # con 12 hilos Workable bloqueó la IP por un rato (429)
        for f, h in zip(pend, ex.map(lambda f: buscar(f["company"], f["title"]), pend)):
            cache[f"{f['company']}|{f['title']}"] = h
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    n = 0
    for f in filas[:tope]:
        e = elegir(cache.get(f"{f['company']}|{f['title']}") or [])
        if e:
            f.update(apply_url=e["url"], ats=e["ats"], ats_lugar=e["lugar"], ats_tablero=e["tablero"], ats_id=e["id"])
            n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit('uso: python3 directo.py "Empresa" "Título del aviso"')
    hs = buscar(sys.argv[1], sys.argv[2])
    for h in hs:
        print(f"{h['ats']:10} | {h['titulo'][:50]:50} | {h['lugar'][:40]:40} | {h['url']}")
    e = elegir(hs)
    print("->", e["url"] if e else "sin publicación que sirva desde tu país")
    if e and e["ats"] == "greenhouse":
        qs = preguntas(e["tablero"], e["id"])
        for q in qs:
            print("   ", "*" if q["required"] else " ", q["label"][:110], "|", q["type"])
        if trabas(qs):
            print("    TRABA (lo tienes que contestar tú):", "; ".join(trabas(qs)))
