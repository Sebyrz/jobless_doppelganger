#!/usr/bin/env python3
"""
cola.py — entra y saca avisos de la cola a mano. Es lo que usa Claude cuando lee LinkedIn contigo
en tu Chrome (LinkedIn no se automatiza con scripts: ver el skill `postular`), o cuando le pasas un link.

    python3 cola.py agregar --fuente linkedin --url https://www.linkedin.com/jobs/view/123/ \
            --titulo "Deployment Strategist" --empresa ElevenLabs --ubicacion "LATAM (Remote)" [--easy]
    python3 cola.py marcar --url <url> --estado submitted --titulo ... --empresa ... [--nota "..."]
    python3 cola.py ver [--top 20] [--fuente linkedin]

`agregar` pasa el aviso por el mismo criterio (rol, piso de sueldo) y lo deja en cola_manual.jsonl;
el radar lo mezcla con el resto. `marcar` escribe en postulados.jsonl, el registro único de lo
postulado (todas las fuentes).
Estados de `marcar`: submitted · descartado · entrevista · rechazado · sin_respuesta · oferta
                     falta_dato · borrador (estos dos vuelven a aparecer en el radar)
    python3 cola.py resumen      # cuántas enviadas, por semana y por estado
"""
from __future__ import annotations
import argparse, datetime, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config, criterio

MANUAL, LOG, COLA = config.MANUAL, config.POSTULADOS, config.COLA


def _rows(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def agregar(fuente, url, titulo, empresa, ubicacion="", lo=None, hi=None, desc="", easy=False, lang="en", nota="", local=False) -> tuple[bool, str]:
    nivel, why = criterio.rol(titulo)
    job = {"id": f"{fuente}:{url}", "source": fuente, "url": url, "title": titulo.strip(), "company": empresa.strip(),
           "company_about": "", "company_country": (config.cargar()["pais_iso"] if local else ""),
           "location_raw": ubicacion, "loc": "ok", "loc_why": ubicacion or "agregado a mano",
           "min_salary": lo, "max_salary": hi, "seniority": "", "lang": lang, "published_at": time.time(),
           "desc": desc[:2500], "easy_apply": bool(easy), "nota": nota}
    if nivel is None:
        return False, why
    ok, why_s = criterio.sueldo_ok(job)
    if not ok:
        return False, why_s
    if any(r["url"] == url for r in _rows(MANUAL)):
        return False, "ya estaba en la cola"
    job["veredicto_fijo"] = "revisar" if nivel == "C" else "match"
    job["por_que"] = (ubicacion or "agregado a mano") + (" · Easy Apply" if easy else "")
    MANUAL.parent.mkdir(parents=True, exist_ok=True)
    with MANUAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(job, ensure_ascii=False) + "\n")
    return True, f"nivel {nivel}"


def marcar(url, estado, titulo="", empresa="", nota="") -> None:
    rec = {"url": url, "title": titulo, "company": empresa, "status": estado, "nota": nota,
           "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def resumen() -> None:
    rows = _rows(LOG)
    if not rows:
        print("[registro] todavía no hay postulaciones"); return
    por_estado, por_semana = {}, {}
    for r in rows:
        por_estado[r["status"]] = por_estado.get(r["status"], 0) + 1
        if r["status"] == "submitted":
            sem = datetime.date.fromisoformat(r["ts"][:10]).strftime("%G-S%V")
            por_semana[sem] = por_semana.get(sem, 0) + 1
    print("[registro] por estado: " + ", ".join(f"{k} {v}" for k, v in sorted(por_estado.items(), key=lambda x: -x[1])))
    print("[registro] enviadas por semana: " + ", ".join(f"{k}: {v}" for k, v in sorted(por_semana.items())))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("agregar")
    a.add_argument("--fuente", default="linkedin"); a.add_argument("--url", required=True)
    a.add_argument("--titulo", required=True); a.add_argument("--empresa", required=True)
    a.add_argument("--ubicacion", default=""); a.add_argument("--min", type=int); a.add_argument("--max", type=int)
    a.add_argument("--desc", default=""); a.add_argument("--easy", action="store_true"); a.add_argument("--lang", default="en")
    a.add_argument("--local", action="store_true", help="empresa de tu país que publica en tu idioma (se pide en moneda local)")
    m = sub.add_parser("marcar")
    m.add_argument("--url", required=True); m.add_argument("--estado", required=True)
    m.add_argument("--titulo", default=""); m.add_argument("--empresa", default=""); m.add_argument("--nota", default="")
    v = sub.add_parser("ver")
    v.add_argument("--top", type=int, default=20); v.add_argument("--fuente", default="")
    sub.add_parser("resumen")
    args = ap.parse_args()
    if args.cmd == "agregar":
        ok, why = agregar(args.fuente, args.url, args.titulo, args.empresa, args.ubicacion, args.min, args.max, args.desc, args.easy, args.lang,
                          local=args.local)
        print(("[cola] agregado: " if ok else "[cola] no entra: ") + why)
    elif args.cmd == "marcar":
        marcar(args.url, args.estado, args.titulo, args.empresa, args.nota); print(f"[registro] {args.estado}: {args.titulo} @ {args.empresa}")
    elif args.cmd == "resumen":
        resumen()
    else:
        rows = [r for r in _rows(COLA) if not args.fuente or r["source"] == args.fuente][:args.top]
        for r in rows:
            sal = f"{r['min_salary'] or '?'}-{r['max_salary'] or '?'}" if (r["min_salary"] or r["max_salary"]) else "s/sueldo"
            print(f"[{r['veredicto']:7}] {r['puntaje']:3} | {r['title'][:46]:46} | {r['company'][:18]:18} | {sal:11} | {r['source']:9} | {r['url']}")


if __name__ == "__main__":
    main()
