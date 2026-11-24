#!/usr/bin/env python3
"""
fuentes.py — bolsas remotas con API pública (Himalayas, Remotive, RemoteOK, Working Nomads),
llevadas a un mismo formato. Solo ENCUENTRAN: la postulación se hace en el sitio de cada empresa.

Cada fuente devuelve dicts con: id, source, url, title, company, company_about, location_raw,
loc ("ok" | "duda" | "no"), min_salary, max_salary (USD/mes), seniority, lang, published_at, desc.
"""
from __future__ import annotations
import calendar, html, json, re, sys, time, urllib.parse, urllib.request
import config

C = config.cargar()
UA = {"User-Agent": "Mozilla/5.0 (jobless_doppelganger: radar personal de empleo)", "Accept": "application/json"}


def consultas() -> list[str]:
    return list(C["busquedas"]) or ["product manager", "project manager", "customer success", "operations manager"]


def _get(url: str, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _txt(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


# ---------- ubicación ----------
def _palabras_pais() -> list[str]:
    return [x for x in [C["pais"], C["pais_getonbrd"]] + list(C["ciudades"]) if x]


def nombra_pais(texto: str) -> bool:
    """El texto nombra tu país o tu ciudad."""
    pal = [re.escape(p.lower()) for p in _palabras_pais()]
    return bool(pal) and bool(re.search(r"\b(" + "|".join(pal) + r")\b", (texto or "").lower()))


def abre_zona(texto: str) -> bool:
    """El texto abre la puerta a tu región (LatAm, Americas, worldwide... según config.zonas_ok)."""
    pal = [re.escape(z.lower()) for z in C["zonas_ok"] if z]
    return bool(pal) and bool(re.search(r"\b(" + "|".join(pal) + r")\b", (texto or "").lower()))


GENERICAS = {"worldwide", "anywhere", "global", "international", "any location", "work from anywhere"}


def nombra_region(texto: str) -> bool:
    """Para descripciones largas: tu país o una zona concreta (LatAm, Americas). 'Global' en una
    descripción casi siempre habla del equipo o los clientes, no de desde dónde se puede trabajar."""
    pal = [re.escape(z.lower()) for z in C["zonas_ok"] if z and z.lower() not in GENERICAS]
    return nombra_pais(texto) or (bool(pal) and bool(re.search(r"\b(" + "|".join(pal) + r")\b", (texto or "").lower())))


def ubicacion(raw) -> tuple[str, str]:
    """ok: se puede trabajar desde tu país · duda: el aviso no lo dice · no: restringido a otra parte."""
    if isinstance(raw, (list, tuple)):
        if not raw:
            return "ok", "remoto desde cualquier lugar"
        if any(nombra_pais(x) for x in raw):
            return "ok", f"remoto, {C['pais']} en la lista de países" + (f" ({len(raw)} países)" if len(raw) > 1 else "")
        return "no", f"solo desde {', '.join(raw[:3])}"
    s = (raw or "").strip()
    if not s or s.lower() in ("remote", "remoto"):
        return "duda", "remoto, sin decir desde dónde"
    if nombra_pais(s) or abre_zona(s):
        return "ok", f"remoto ({s[:40]})"
    return "no", f"solo desde {s[:40]}"


# ---------- sueldo ----------
FX = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.73, "AUD": 0.65}   # aproximado; solo para ordenar


def mensual(lo, hi, moneda="USD", periodo="annual"):
    """Lleva un rango a USD/mes. Devuelve (min, max) o (None, None) si no se puede comparar."""
    fx = FX.get((moneda or "USD").upper())
    if not fx or not (lo or hi):
        return None, None
    p = (periodo or "annual").lower()
    div = 12 if p.startswith(("ann", "year")) else 1 if p.startswith("month") else None
    if div is None:
        return None, None
    conv = lambda v: int(round(v * fx / div)) if v else None
    return conv(lo), conv(hi)


def sueldo_texto(s: str):
    """'$120k - $150k' · '$90,000 - $110,000' · 'USD 4000-6000/month' -> USD/mes. Por hora: no se compara."""
    s = (s or "").lower()
    if not s or re.search(r"/ ?h|hour|hora", s):
        return None, None
    nums = []
    for m in re.finditer(r"(\d[\d.,]*)\s*(k)?", s):
        raw, k = m.group(1), m.group(2)
        v = float(raw.replace(",", ".")) if k else float(re.sub(r"[.,]", "", raw) or 0)
        v = v * 1000 if k else v
        if v >= 500:
            nums.append(v)
    if not nums:
        return None, None
    lo, hi = min(nums), max(nums)
    periodo = "monthly" if (re.search(r"month|mes|/mo", s) or hi < 20000) else "annual"
    return mensual(lo, hi, "USD", periodo)


def _epoch(s) -> float | None:
    if isinstance(s, (int, float)):
        return float(s)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    return float(calendar.timegm((int(m[1]), int(m[2]), int(m[3]), 0, 0, 0))) if m else None


def _job(source, id_, url, title, company, location_raw, lo=None, hi=None, seniority="", published=None, desc="", about=""):
    loc, loc_why = ubicacion(location_raw)
    return {"id": f"{source}:{id_}", "source": source, "url": url, "title": (title or "").strip(),
            "company": (company or "").strip(), "company_about": about[:600],
            "location_raw": location_raw if isinstance(location_raw, str) else ", ".join(location_raw[:6]),
            "loc": loc, "loc_why": loc_why, "min_salary": lo, "max_salary": hi, "seniority": seniority,
            "lang": "en", "published_at": _epoch(published), "desc": _txt(desc)[:6000]}


consultas_ = consultas


# ---------- Himalayas: la mejor, trae países permitidos, sueldo y seniority ----------
def himalayas(consultas=None, paginas=2) -> list[dict]:
    out = []
    filtros = ([f"country={C['pais_iso']}"] if C["pais_iso"] else []) + ["worldwide=true"]
    for q in (consultas or consultas_()):
        for filtro in filtros:
            for p in range(paginas):
                url = f"https://himalayas.app/jobs/api/search?q={urllib.parse.quote(q)}&{filtro}&offset={p * 20}"
                d = None
                for espera in (0, 20, 45):   # limita por ráfaga (429): espera y reintenta
                    time.sleep(espera)
                    try:
                        d = _get(url); break
                    except Exception as e:
                        err = str(e)
                        if "429" not in err:
                            break
                if d is None:
                    print(f"[himalayas] '{q}' {filtro} falló: {err[:60]}", file=sys.stderr); break
                js = d.get("jobs", [])
                for j in js:
                    lo, hi = mensual(j.get("minSalary"), j.get("maxSalary"), j.get("currency") or "USD", j.get("salaryPeriod"))
                    sen = " / ".join(j.get("seniority") or [])
                    out.append(_job("himalayas", j.get("guid") or j.get("applicationLink"), j.get("applicationLink") or j.get("guid"),
                                    j.get("title"), j.get("companyName"), j.get("locationRestrictions") or [], lo, hi,
                                    "Junior" if "Entry" in sen else sen, j.get("pubDate"), j.get("description") or j.get("excerpt")))
                time.sleep(1.5)
                if len(js) < 20 or (p + 1) * 20 >= (d.get("totalCount") or 0):
                    break
    return out


# ---------- Remotive ----------
def remotive(consultas=None) -> list[dict]:
    out = []
    for q in (consultas or consultas_())[:5]:   # piden pocas llamadas al día: 5 búsquedas, no todo el catálogo
        try:
            d = _get(f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(q)}&limit=60")
        except Exception as e:
            print(f"[remotive] '{q}' falló: {str(e)[:60]}", file=sys.stderr); continue
        for j in d.get("jobs", []):
            lo, hi = sueldo_texto(j.get("salary"))
            out.append(_job("remotive", j["id"], j["url"], j["title"], j["company_name"],
                            j.get("candidate_required_location") or "", lo, hi, "", j.get("publication_date"), j.get("description")))
        time.sleep(0.5)
    return out


# ---------- RemoteOK ----------
def remoteok() -> list[dict]:
    out = []
    for j in _get("https://remoteok.com/api")[1:]:
        if not j.get("position"):
            continue
        lo, hi = mensual(j.get("salary_min") or None, j.get("salary_max") or None, "USD", "annual")
        out.append(_job("remoteok", j["id"], j.get("url") or j.get("apply_url"), j["position"], j.get("company"),
                        j.get("location") or "", lo, hi, "", j.get("epoch") or j.get("date"), j.get("description")))
    return out


# ---------- Working Nomads ----------
def workingnomads() -> list[dict]:
    return [_job("workingnomads", j["url"], j["url"], j["title"], j.get("company_name"), j.get("location") or "",
                 None, None, "", j.get("pub_date"), j.get("description"))
            for j in _get("https://www.workingnomads.com/api/exposed_jobs/")]


FUENTES = {"himalayas": himalayas, "remotive": remotive, "remoteok": remoteok, "workingnomads": workingnomads}


def fetch(cuales=None) -> list[dict]:
    jobs, seen = [], set()
    for name in (cuales or FUENTES):
        try:
            got = FUENTES[name]()
        except Exception as e:   # una bolsa caída no bota el radar
            print(f"[{name}] falló: {type(e).__name__} {str(e)[:80]}", file=sys.stderr); continue
        n = 0
        for j in got:
            key = (re.sub(r"\W+", " ", j["title"].lower()).strip(), re.sub(r"\W+", " ", j["company"].lower()).strip())
            if j["id"] in seen or key in seen or not j["url"]:
                continue
            seen.update((j["id"], key)); jobs.append(j); n += 1
        print(f"[{name}] {n} avisos", file=sys.stderr)
    return jobs


if __name__ == "__main__":
    for j in fetch(sys.argv[1:] or None)[:40]:
        print(f"{j['source']:13} | {j['title'][:45]:45} | {j['company'][:18]:18} | {j['loc']:4} | {j['min_salary']}-{j['max_salary']}")
