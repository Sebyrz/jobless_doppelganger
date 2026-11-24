#!/usr/bin/env python3
"""
radar.py — junta todas las fuentes, filtra con un solo criterio, ordena por puntaje y deja la cola.
No envía nada.

    python3 radar.py                       # todas las fuentes -> ~/.doppelganger/cola.jsonl y cola.md
    python3 radar.py --fuentes getonbrd    # solo GetOnBoard
    python3 radar.py --sin-tableros        # salta el barrido de bolsas de empresas (más rápido)
    python3 radar.py --top 40              # cuántos muestra cola.md (default 30)

La cola es una foto: se rehace en cada corrida. Lo ya postulado sale de postulados.jsonl
(misma URL, o título + empresa parecidos).

veredicto:
    match    pasa todo: entra a la próxima tanda.
    revisar  vale una mirada tuya (rol discutible, o el aviso no dice desde qué países).
"""
from __future__ import annotations
import argparse, datetime, json, os, re, sys, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config, criterio, fuentes, getonbrd_api as gob

C = config.cargar()
LOG, COLA, COLA_MD, MANUAL = config.POSTULADOS, config.COLA, config.COLA_MD, config.MANUAL

# estados del log que NO cuentan como "ya postulado": se pueden reintentar
REINTENTABLES = {"falta_dato", "revisar_calce", "borrador", "error_formulario"}

STOP = {"the", "and", "for", "senior", "ssr", "full", "time", "part", "de", "of", "a", "el", "la",
        "sr", "jr", "i", "ii", "iii", "remote", "remoto", "freelance"}


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _tokens(s):
    return {t for t in _norm(s).split() if len(t) > 2 and t not in STOP}


def hechos() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


_COLA_URL = re.compile(r"/(apply|application|thanks|confirmation)$", re.I)
# palabras que muchas empresas comparten: no sirven para decir que dos nombres son la misma empresa
EMPRESA_GENERICA = {"ai", "labs", "lab", "inc", "llc", "ltd", "group", "grupo", "the", "co", "io", "hq", "app", "tech",
                    "technologies", "technology", "software", "global", "latam", "solutions", "systems", "digital",
                    "company", "corp", "spa", "sa", "data", "cloud", "health", "capital", "studio", "studios"}


def clave_url(url: str) -> str:
    """Lo que identifica a UN aviso. El último tramo de la URL no sirve: en Lever y Workable es 'apply',
    en Ashby 'application', y en el sitio propio de una empresa 'careers' (el id va en ?gh_jid=)."""
    u = urllib.parse.urlsplit((url or "").strip())
    host = u.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    if "getonbrd" in host:   # los logs viejos guardan /jobs/<categoría>/<slug>, la API /jobs/<slug>
        return "getonbrd:" + gob.slug(url)
    path = _COLA_URL.sub("", u.path.rstrip("/"))
    gh = urllib.parse.parse_qs(u.query).get("gh_jid")
    return host + path + (f"?gh_jid={gh[0]}" if gh else "")


def misma_empresa(a: str, b: str) -> bool:
    """'Acme' = 'Acme Inc' = 'acme'; 'Scale AI' = 'scaleai'. 'Scale AI' no es 'Harvey AI'."""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    ja, jb = a.replace(" ", ""), b.replace(" ", "")
    if ja == jb or (min(len(ja), len(jb)) >= 5 and (ja in jb or jb in ja)):
        return True
    ta, tb = set(a.split()) - EMPRESA_GENERICA, set(b.split()) - EMPRESA_GENERICA
    return bool(ta) and bool(tb) and (ta <= tb or tb <= ta)


def ya_postulado(job: dict, done: list[dict]) -> bool:
    """Mismo aviso (misma URL sin el tramo de postular), o título muy parecido (Jaccard) + misma empresa."""
    claves = {clave_url(u) for u in (job.get("url"), job.get("apply_url")) if u}   # se registra con cualquiera de las dos
    nt = _tokens(job["title"])
    for r in done:
        if r.get("status") in REINTENTABLES:
            continue
        if r.get("url") and clave_url(r["url"]) in claves:
            return True
        rt = _tokens(r.get("title", ""))
        if not nt or not rt:
            continue
        jac = len(nt & rt) / len(nt | rt)
        if jac >= 0.6 and misma_empresa(job["company"], r.get("company", "")):
            return True
    return False


def veredicto(job: dict) -> tuple[str, str]:
    if job["source"] == "getonbrd":
        return gob.veredicto(job)
    if job.get("seniority") == "Junior":
        return "skip", "junior"
    nivel, why = criterio.rol(job["title"])
    if nivel is None:
        return "skip", why
    ok, why_s = criterio.sueldo_ok(job)
    if not ok:
        return "skip", why_s
    if job["loc"] == "no":
        return "skip", job["loc_why"]
    if nivel == "C":
        return "revisar", "rol técnico de cara al cliente"
    if job["loc"] == "duda":
        return "revisar", job["loc_why"]
    if criterio.exige_de_mas(job):   # la experiencia pedida dice que no: lo decides tú
        return "revisar", f"pide {criterio.exige_de_mas(job)}+ años"
    return "match", job["loc_why"]


def armar(cuales: list[str] | None = None, tableros_si=True) -> list[dict]:
    jobs = []
    if not cuales or "getonbrd" in cuales:
        try:
            g = gob.fetch(); print(f"[getonbrd] {len(g)} avisos", file=sys.stderr); jobs += g
        except Exception as e:   # una fuente caída no bota el radar
            print(f"[getonbrd] falló: {str(e)[:80]}", file=sys.stderr)
    otras = [f for f in (cuales or list(fuentes.FUENTES)) if f in fuentes.FUENTES]
    if otras:
        jobs += fuentes.fetch(otras)
    if tableros_si and (not cuales or "tableros" in cuales):
        import tableros
        t = tableros.fetch(); print(f"[tableros] {len(t)} avisos con formulario directo", file=sys.stderr); jobs += t
    if MANUAL.exists():
        jobs += [json.loads(l) for l in MANUAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    done, cola, vistos = hechos(), [], set()
    for j in jobs:
        v, why = veredicto(j) if j["source"] != "manual" and not j.get("veredicto_fijo") else (j.get("veredicto_fijo", "match"), j.get("por_que", "agregado a mano"))
        if v == "skip":
            continue
        key = (_norm(j["title"]), _norm(j["company"]))
        if key in vistos or ya_postulado(j, done):
            continue
        vistos.add(key)
        pts, razones = criterio.puntaje(j)
        cola.append({**{k: j.get(k) for k in ("id", "source", "url", "title", "company", "min_salary", "max_salary",
                                               "seniority", "lang", "published_at", "location_raw", "desc", "company_about",
                                               "company_country", "apply_url", "ats", "ats_lugar", "ats_tablero", "ats_id")},
                     "veredicto": v, "por_que": why, "puntaje": pts, "razones": razones, "pedir": criterio.pedir(j),
                     "pedir_texto": criterio.pedir_texto(j)})
    cola.sort(key=lambda r: (r["veredicto"] != "match", -r["puntaje"]))
    return cola


def escribir(cola: list[dict], top=30):
    COLA.parent.mkdir(parents=True, exist_ok=True)
    COLA.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in cola), encoding="utf-8")
    hoy = datetime.datetime.now()
    L = [f"# Cola de postulación · {hoy:%Y-%m-%d %H:%M}\n\n",
         f"Piso USD {C['piso_usd_mes']}/mes · {'solo remoto' if C['solo_remoto'] else 'remoto o en tu país'} desde {C['pais'] or '(país sin configurar)'} · sin lo ya postulado. "
         f"{sum(r['veredicto'] == 'match' for r in cola)} para postular, {sum(r['veredicto'] == 'revisar' for r in cola)} por revisar.\n\n"]
    directos = [r for r in cola if r.get("apply_url") and r["veredicto"] == "match"]
    if directos:
        L.append(f"## Con formulario directo ({len(directos)})\n\nSe pueden llenar y enviar sin crear cuenta. Partir por estos.\n\n"
                 "| Pts | Aviso | Empresa | Sueldo publicado | Pedir | Dónde | Formulario |\n|---|---|---|---|---|---|---|\n")
        for r in directos[:top]:
            sal = f"{r['min_salary'] or '?'}–{r['max_salary'] or '?'}" if (r["min_salary"] or r["max_salary"]) else "no publica"
            L.append(f"| {r['puntaje']} | {r['title'][:60]} | {r['company'][:28]} | {sal} | {r['pedir_texto']} | "
                     f"{(r.get('ats_lugar') or '')[:40]} | [{r['ats']}]({r['apply_url']}) |\n")
        L.append("\n")
    for titulo, v in (("Para postular", "match"), ("Por revisar (decides tú)", "revisar")):
        rows = [r for r in cola if r["veredicto"] == v][:top]
        if not rows:
            continue
        L.append(f"## {titulo}\n\n| # | Pts | Aviso | Empresa | Sueldo publicado | Pedir | Fuente | Por qué |\n|---|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(rows, 1):
            sal = f"{r['min_salary'] or '?'}–{r['max_salary'] or '?'}" if (r["min_salary"] or r["max_salary"]) else "no publica"
            L.append(f"| {i} | {r['puntaje']} | [{r['title'][:60]}]({r['url']}) | {r['company'][:28]} | {sal} | {r['pedir_texto']} | "
                     f"{r['source']} | {r['por_que']}; {', '.join(r['razones'][:3])} |\n")
        L.append("\n")
    COLA_MD.write_text("".join(L), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuentes", default="", help="separadas por coma: getonbrd,himalayas,remotive,remoteok,workingnomads,tableros")
    ap.add_argument("--sin-tableros", action="store_true", help="salta el barrido de bolsas de empresas")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--directo", type=int, default=80, metavar="N",
                    help="busca el formulario directo (Greenhouse/Ashby/Lever) de los N mejores; 0 lo salta")
    a = ap.parse_args()
    falta = config.estado()
    if any(f.startswith("config.json") for f in falta):
        sys.exit("[radar] falta configurar: " + "; ".join(f for f in falta if f.startswith("config.json")) +
                 "\nCorre el skill `perfil` (o edita " + str(config.CONFIG) + ").")
    cola = armar([f.strip() for f in a.fuentes.split(",") if f.strip()] or None, not a.sin_tableros)
    if a.directo:
        import directo
        print(f"[directo] {directo.enlazar(cola, a.directo)} avisos con formulario directo", file=sys.stderr)
    config.HOME.mkdir(parents=True, exist_ok=True)
    escribir(cola, a.top)
    m = [r for r in cola if r["veredicto"] == "match"]
    print(f"[radar] {len(m)} para postular, {len(cola) - len(m)} por revisar -> {COLA_MD}")
    for r in cola[:a.top]:
        sal = f"{r['min_salary'] or '?'}-{r['max_salary'] or '?'}" if (r["min_salary"] or r["max_salary"]) else "s/sueldo"
        print(f"[{r['veredicto']:7}] {r['puntaje']:3} | {r['title'][:46]:46} | {r['company'][:18]:18} | {sal:11} | {r['source']:9} | {r['por_que'][:44]}")
