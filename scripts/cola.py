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
                     enviando: se anota ANTES de apretar enviar. Si la sesión se corta, el aviso no
                     vuelve a la cola ni se manda dos veces; `resumen` lo muestra para revisarlo a mano.
    python3 cola.py marcar ... --cv cv/pm.pdf --pedir "4000 USD"   # con qué CV y qué sueldo se postuló
    python3 cola.py resumen      # cuántas enviadas, por semana y por estado
    python3 cola.py elegibles    # modo automático: qué avisos se pueden enviar solos hoy (y cuántos quedan)
    python3 cola.py marcar ... --modo auto --respuestas resp.json   # guarda lo que se envió, para auditar
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


def marcar(url, estado, titulo="", empresa="", nota="", modo="", respuestas=None, cv="", pedir="") -> None:
    rec = {"url": url, "title": titulo, "company": empresa, "status": estado, "nota": nota,
           "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    if cv:
        rec["cv"] = cv           # el archivo que se subió
    if pedir:
        rec["pedir"] = pedir     # el sueldo que se escribió en el formulario
    if modo:
        rec["modo"] = modo
    if respuestas:
        rec["respuestas"] = respuestas   # [{"q": ..., "a": ...}] tal como se enviaron
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def auto_hoy(rows: list[dict] | None = None) -> int:
    """Envíos automáticos de hoy (para el tope diario)."""
    hoy = datetime.date.today().isoformat()
    return sum(1 for r in (rows if rows is not None else _rows(LOG))
               if r.get("modo") == "auto" and r.get("status") == "submitted" and r.get("ts", "")[:10] == hoy)


def por_que_no_auto(r: dict, c: dict) -> str:
    """Motivo por el que un aviso de la cola NO se envía solo ('' si puede)."""
    if r.get("veredicto") != "match":
        return "por revisar: lo decides tú"
    if (r.get("puntaje") or 0) < c["auto_puntaje_min"]:
        return f"puntaje {r.get('puntaje')} bajo {c['auto_puntaje_min']}"
    if r.get("source") == "linkedin" or "linkedin.com" in (r.get("url") or "") or r.get("easy_apply"):
        return "LinkedIn: el envío final es tuyo"
    if not (r.get("apply_url") or r.get("source") == "getonbrd"):
        return "sin formulario directo (pediría crear cuenta)"
    if r.get("pedir") and r["pedir"] < criterio.piso(r):
        return "lo que se pediría queda bajo tu piso"
    return ""


def elegibles(cola: list[dict] | None = None) -> tuple[list[dict], list[tuple[dict, str]], int]:
    """Modo automático: (los que se envían hoy, [(aviso, por qué no)], cupo que queda)."""
    c = config.cargar()
    cupo = max(0, int(c["auto_max_dia"]) - auto_hoy())
    si, no = [], []
    import radar   # acá y no arriba: radar es pesado y solo hace falta para este cruce
    done = radar.hechos()
    for r in (cola if cola is not None else _rows(COLA)):
        # la cola es una foto de la última corrida del radar: lo enviado después sigue en ella
        why = "ya postulado (o envío sin confirmar)" if radar.ya_postulado(r, done) else por_que_no_auto(r, c)
        if why:
            no.append((r, why))
        elif len(si) < cupo:
            si.append(r)
        else:
            no.append((r, f"tope diario de {c['auto_max_dia']} envíos automáticos"))
    return si, no, cupo - len(si)


def sin_confirmar(rows: list[dict] | None = None) -> list[dict]:
    """Avisos cuyo último estado es 'enviando': se apretó (o se iba a apretar) enviar y no hay confirmación."""
    import radar
    ultimo = {}
    for r in (rows if rows is not None else _rows(LOG)):
        ultimo[radar.clave_url(r.get("url", ""))] = r
    return [r for r in ultimo.values() if r.get("status") == "enviando"]


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
    colgados = sin_confirmar(rows)
    if colgados:
        print(f"[registro] OJO: {len(colgados)} envíos quedaron a medias (se anotó 'enviando' y nunca la confirmación). "
              "Revisa en el sitio si salieron y márcalos submitted o borrador:")
        for r in colgados:
            print(f"    {r['ts'][:16]} | {r.get('title', '')[:40]} @ {r.get('company', '')[:20]} | {r['url']}")
    auto = sum(1 for r in rows if r.get("modo") == "auto" and r["status"] == "submitted")
    if auto:
        print(f"[registro] enviadas en modo automático: {auto} (hoy {auto_hoy(rows)})")


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
    m.add_argument("--modo", default="", choices=["", "auto", "revisado"], help="auto = se envió sin que vieras la tanda")
    m.add_argument("--respuestas", default="", help="JSON con [{q, a}] tal como se enviaron")
    m.add_argument("--cv", default="", help="archivo de CV que se subió")
    m.add_argument("--pedir", default="", help="sueldo que se escribió en el formulario")
    sub.add_parser("elegibles")
    v = sub.add_parser("ver")
    v.add_argument("--top", type=int, default=20); v.add_argument("--fuente", default="")
    sub.add_parser("resumen")
    args = ap.parse_args()
    if args.cmd == "agregar":
        ok, why = agregar(args.fuente, args.url, args.titulo, args.empresa, args.ubicacion, args.min, args.max, args.desc, args.easy, args.lang,
                          local=args.local)
        print(("[cola] agregado: " if ok else "[cola] no entra: ") + why)
    elif args.cmd == "marcar":
        resp = json.loads(Path(args.respuestas).read_text(encoding="utf-8")) if args.respuestas else None
        marcar(args.url, args.estado, args.titulo, args.empresa, args.nota, args.modo, resp, args.cv, args.pedir); print(f"[registro] {args.estado}: {args.titulo} @ {args.empresa}")
    elif args.cmd == "resumen":
        resumen()
    elif args.cmd == "elegibles":
        c = config.cargar()
        if c["envio"] != "automatico":
            print('[auto] el modo automático está apagado (config.json: "envio": "revisar")')
        si, no, queda = elegibles()
        print(f"[auto] {len(si)} se envían solos hoy · cupo que queda después: {queda}")
        for r in si:
            print(f"  ✓ {r['puntaje']:3} | {r['title'][:50]:50} | {r['company'][:20]:20} | {r.get('apply_url') or r['url']}")
        motivos = {}
        for _, why in no:
            k = "puntaje bajo" if why.startswith("puntaje") else why.split(":")[0]
            motivos[k] = motivos.get(k, 0) + 1
        print("[auto] no van solos: " + ", ".join(f"{k} {v}" for k, v in sorted(motivos.items(), key=lambda x: -x[1])))
    else:
        rows = [r for r in _rows(COLA) if not args.fuente or r["source"] == args.fuente][:args.top]
        for r in rows:
            sal = f"{r['min_salary'] or '?'}-{r['max_salary'] or '?'}" if (r["min_salary"] or r["max_salary"]) else "s/sueldo"
            print(f"[{r['veredicto']:7}] {r['puntaje']:3} | {r['title'][:46]:46} | {r['company'][:18]:18} | {sal:11} | {r['source']:9} | {r['url']}")


if __name__ == "__main__":
    main()
