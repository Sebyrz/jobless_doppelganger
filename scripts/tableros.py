#!/usr/bin/env python3
"""
tableros.py — barre las bolsas públicas (Greenhouse, Ashby, Lever, Manatal) de una lista de empresas
que contratan remoto, y deja los avisos que calzan en la misma forma que las demás fuentes. Todo lo
que sale de acá trae formulario directo, sin cuenta.

Por qué: las bolsas agregadoras entregan muchos avisos, pero pocos con formulario directo. Ir al revés
(empresa -> bolsa -> aviso) entrega avisos que sí se pueden llenar y enviar.

Puedes sumar empresas propias en config.json: "empresas_extra": ["acme", "otraempresa"] (el nombre
como aparece en la URL de su bolsa: boards.greenhouse.io/<nombre>, jobs.ashbyhq.com/<nombre>).

    python3 tableros.py            # imprime los que calzan
    from tableros import fetch     # [{... "apply_url": ..., "ats": ...}]
"""
from __future__ import annotations
import concurrent.futures as cf, html, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config, fuentes
import directo
from directo import _get

C = config.cargar()

# Listas públicas de empresas que han contratado remoto. Editables.
LOGISTICA = """flexport project44 fourkites shippo easypost shipbob freightos loadsmart stord nuvocargo nowports
sennder forto zencargo beacon transfix parade emerge turvo magaya shipwell arrive leaf shiphero overhaul tive
roambee controlant vizion portcast windward xeneta freightify samsara motive gomotive flockfreight onerail
kargo deliverr cargoone fleetzero altana everstream terminal49 haven shipmonk flowspace ware fabric""".split()

LATAM = """nubank rappi kavak bitso clip konfio truora platzi buk betterfly notco fintual xepelin tenpo dlocal ebanx
vtex wellhub gympass loft quintoandar creditas stone olist zenvia airtm belvo kushki conekta toku rankmi houm
lemontech jooycar comunidadfeliz bsale cornershop justo frubana merqueo addi habi truehome clara stori ualabis
pomelo nuvemshop tiendanube mercately treinta nowports yalo jelou workana revelo hotmart coderhouse henry
wizeline encora nearsure oowlish howdy arionkoder scalablepath xteam jobgether bairesdev toptal andela turing
lemon ripio buenbit ontop deel remotecom oysterhr multiplier papayaglobal velocityglobal rippling gusto
justworks safetywing""".split()

SAAS = """twilio okta zapier n8n make airtable notion clickup asana smartsheet miro canva loom calendly typeform hotjar
contentsquare fullstory mixpanel amplitude posthog segment braze iterable klaviyo attentive customerio intercom
zendesk freshworks gorgias front helpscout kustomer gladly ada forethought sierra decagon chargebee recurly
paddle maxio avalara anrok brex ramp mercury navan expensify tipalti zip vendr tropic vercel netlify supabase
retool appsmith pipedream postman kong grafana elastic mongodb datadog sentry pagerduty launchdarkly statsig
optimizely docker snyk wiz 1password bitwarden tailscale cloudflare auth0 stytch clerk workos persona onfido
sumsub veriff alloy sardine unit moderntreasury plaid flywire nuvei checkout toast lightspeed bigcommerce webflow
framer pipedrive close apollo outreach salesloft gong clari highspot seismic pandadoc ironclad juro spotdraft
workato tray celigo celonis uipath automationanywhere appian outsystems mendix airslate docebo gorgias
lattice cultureamp leapsome hibob factorial personio remote doist gitlab automattic hubspot canonical
clickhouse dbtlabs fivetran hightouch census rudderstack airbyte metabase hex mode sigma thoughtspot
anthropic openai cohere elevenlabs synthesia runway jasper writer glean harvey hebbia rogo sana
linear vanta drata secureframe thoropass hyperproof tines torq zip coupa procurify spendesk pleo
""".split()

# agencias y consultoras que contratan remoto en LatAm
AGENCIAS = """nimblegravity nearsure bitovi sweatworks cloudbeds optimove remotecom launchpad bairesdev arionkoder
wizeline encora endava globant perficient tenpearls zemoga applydigital sophilabs bigbangtech intive rootstrap
moove-it 10pearls gorilla gorillalogic jobsity bluecoding azumo distillery devsu growth-acceleration-partners
truelogic qubika teamwork-latam strider onstrider athyna howdy-com terminal remotely""".split()

# Manatal (careers-page.com): bolsa abierta con API pública
MANATAL = """nearshore-business-solutions lurecruiter idelsoft diffco-us archielabs a5-talent-finders talent-sam
hire-overseas""".split()

EMPRESAS = list(dict.fromkeys(list(C.get("empresas_extra") or []) + LOGISTICA + LATAM + SAAS + AGENCIAS))

TXT = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s or ""))).strip()


def _gh(t):
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true", timeout=20)
    out = []
    for j in (d or {}).get("jobs", []):
        out.append(dict(ats="greenhouse", tablero=t, id=str(j["id"]), title=j["title"], company=j.get("company_name") or t,
                        lugar=(j.get("location") or {}).get("name") or "", url=j["absolute_url"], desc=TXT(j.get("content"))))
    return out


def _ashby(t):
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true", timeout=20)
    out = []
    for j in (d or {}).get("jobs", []):
        lugar = j.get("location") or ""
        sec = ", ".join((x.get("location") or "") for x in j.get("secondaryLocations") or [])
        if j.get("isRemote") and "remote" not in lugar.lower():
            lugar += " (remote)"
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
        out.append(dict(ats="ashby", tablero=t, id=j.get("id", ""), title=j["title"], company=t,
                        lugar=(lugar + (", " + sec if sec else "")).strip(", "), url=j.get("applyUrl") or j.get("jobUrl"),
                        desc=TXT(j.get("descriptionHtml") or j.get("descriptionPlain")), comp=comp))
    return out


def _lever(t):
    d = _get(f"https://api.lever.co/v0/postings/{t}?mode=json", timeout=20)
    out = []
    for j in (d if isinstance(d, list) else []):
        cats = j.get("categories") or {}
        lugar = ", ".join(cats.get("allLocations") or [cats.get("location") or ""])
        if (j.get("workplaceType") or "") == "remote" and "remote" not in lugar.lower():
            lugar += " (remote)"
        desc = TXT(j.get("descriptionPlain") or j.get("description")) + " " + " ".join(
            TXT(l.get("content")) for l in j.get("lists") or [])
        sr = j.get("salaryRange") or {}
        out.append(dict(ats="lever", tablero=t, id=j.get("id", ""), title=j["text"], company=t, lugar=lugar,
                        url=(j.get("hostedUrl") or "") + "/apply", desc=desc, sr=sr))
    return out


def _manatal(t):
    out, url = [], f"https://api.manatal.com/open/v3/career-page/{t}/jobs/?page_size=100"
    d = _get(url, timeout=20)
    for j in (d or {}).get("results", []):
        lugar = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x) or (j.get("location_display") or "")
        if j.get("is_remote") and "remote" not in lugar.lower():
            lugar += " (remote)"
        out.append(dict(ats="manatal", tablero=t, id=j.get("hash", ""), title=j.get("position_name", ""), company=t,
                        lugar=lugar.strip(), url=f"https://www.careers-page.com/{t}/job/{j.get('hash')}",
                        desc=TXT(j.get("description"))))
    return out


# "Remote" a secas en estas bolsas suele ser EE. UU.; solo entra si el texto abre la puerta a tu país o zona
CIERRA = re.compile(r"(must|need to|required to) (be |reside |live |be located |be based )?(based |located )?in the (us|u\.s|united states)|"
                    r"us[- ]based only|united states only|authorized to work in the (us|united states)|us citizens?", re.I)


def _lugar_ok(j) -> tuple[str, str]:
    l = j["lugar"] or ""
    en_eeuu = (C["pais_iso"] or "").upper() == "US"
    if fuentes.nombra_pais(l):
        return "ok", f"remoto ({l[:40]})"
    if not en_eeuu and re.search(r"united states|\busa?\b|canada", l, re.I) and not fuentes.abre_zona(l):
        return "no", f"solo desde {l[:40]}"
    if fuentes.abre_zona(l) and re.search(r"remote|remoto|anywhere|home based", l + " remote", re.I):
        return "ok", f"remoto ({l[:40]})"
    if re.fullmatch(r"\s*(remote|remoto|anywhere)\s*(\(remote\))?\s*", l, re.I):
        if not en_eeuu and CIERRA.search(j["desc"]):
            return "no", "remoto pero solo EE. UU."
        if fuentes.nombra_region(j["desc"]):
            return "ok", "remoto; el aviso nombra tu país o zona"
        return "duda", "remoto, sin decir desde dónde"
    return "no", f"solo desde {l[:40]}"


def _sueldo(j):
    if j.get("sr", {}).get("min"):
        sr = j["sr"]
        return fuentes.mensual(sr.get("min"), sr.get("max"), sr.get("currency") or "USD",
                               "monthly" if "month" in (sr.get("interval") or "") else "annual")
    if j.get("comp"):
        return fuentes.sueldo_texto(j["comp"])
    return sueldo_en_texto(j["desc"])


_RANGO = re.compile(r"\$\s?\d[\d,.]*\s?k?\s?(?:-|–|—|to)\s?\$?\s?\d[\d,.]*\s?k?", re.I)
_ES_SUELDO = re.compile(r"salary|compensation|pay range|base pay|base range|pay band|pay scale|sueldo|salario|remuneraci|"
                        r"\brenta\b|\bote\b|per year|/ ?year|a year|annual|per month|/ ?month|monthly", re.I)
_NO_ES_SUELDO = re.compile(r"stipend|bonus|budget|revenue|\barr\b|\bacv\b|funding|raised|accounts?\b|deals?\b|allowance|"
                           r"reimburs|equity|valuation|contracts?\b|customers?\b|clients?\b", re.I)


def sueldo_en_texto(desc: str):
    """Sueldo publicado dentro de una descripción. Un rango en dólares vale solo si su frase habla de
    sueldo y lo que viene justo antes no habla de otra cosa (bono, presupuesto, cuentas, ACV, ingresos)."""
    desc = desc or ""
    for m in _RANGO.finditer(desc):
        ini = desc.rfind(". ", 0, m.start()) + 1
        fin = desc.find(". ", m.end())
        frase = desc[ini:fin if fin != -1 else len(desc)]
        antes = desc[max(m.start() - 30, ini):m.start()]   # lo que viene justo antes, dentro de la misma frase
        if not _ES_SUELDO.search(frase) or _NO_ES_SUELDO.search(antes):
            continue
        lo, hi = fuentes.sueldo_texto(m.group(0), desc[m.end():m.end() + 30] + " " + antes)
        if lo or hi:
            return lo, hi
    return None, None


def salud(con: dict, total: int, vivas: int) -> list[str]:
    """Avisos cuando el barrido se ve roto. Una bolsa caída o que cambió su API se ve igual que una sin
    avisos si nadie lo dice: acá se dice."""
    out = []
    for host, n in sorted(directo.FALLOS.items()):
        if any(h in host for h in ("greenhouse", "ashby", "lever", "manatal")):
            out.append(f"{n} llamadas a {host} fallaron (límite de llamadas, caída o cambio de API): faltan avisos de ahí")
    for ats in ("greenhouse", "ashby", "lever"):
        if total >= 20 and not con.get(ats):
            out.append(f"{ats} no devolvió ningún aviso de {total} empresas: lo más probable es que su API cambió")
    if total >= 20 and vivas < total * 0.25:
        out.append(f"solo {vivas} de {total} empresas respondieron con avisos: revisa tu conexión antes de confiar en esta cola")
    return out


def fetch(empresas=EMPRESAS) -> list[dict]:
    crudos, con, vivas = [], {"greenhouse": 0, "ashby": 0, "lever": 0, "manatal": 0}, 0
    directo.FALLOS.clear()
    with cf.ThreadPoolExecutor(8) as ex:
        for gh, ash, lev in ex.map(lambda t: (_gh(t), _ashby(t), _lever(t)), empresas):
            con["greenhouse"] += bool(gh); con["ashby"] += bool(ash); con["lever"] += bool(lev)
            vivas += bool(gh or ash or lev)
            crudos += gh + ash + lev
        for res in ex.map(_manatal, MANATAL):
            con["manatal"] += bool(res)
            crudos += res
    print(f"[tableros] {len(empresas)} empresas en la lista, {vivas} con avisos hoy, {len(crudos)} avisos en total "
          f"({', '.join(f'{k} {v}' for k, v in con.items())})", file=sys.stderr)
    for aviso in salud(con, len(empresas), vivas):
        print(f"[tableros] OJO: {aviso}", file=sys.stderr)
    out = []
    for j in crudos:
        loc, why = _lugar_ok(j)
        if loc == "no":
            continue
        lo, hi = _sueldo(j)
        job = fuentes._job("ats", j["url"], j["url"], j["title"], j["company"], j["lugar"], lo, hi, "", None, j["desc"])
        job.update(loc=loc, loc_why=why, apply_url=j["url"], ats=j["ats"], ats_lugar=j["lugar"],
                   ats_tablero=j["tablero"], ats_id=j["id"], desc=j["desc"][:6000])
        out.append(job)
    return out


if __name__ == "__main__":
    import criterio, radar
    done = radar.hechos()
    n = 0
    for j in fetch():
        v, why = radar.veredicto(j)
        if v == "skip" or radar.ya_postulado(j, done):
            continue
        pts, _ = criterio.puntaje(j)
        n += 1
        print(f"{v:7} {pts:3} | {j['title'][:55]:55} | {j['company'][:16]:16} | {j['ats_lugar'][:28]:28} | "
              f"{j['min_salary'] or ''}-{j['max_salary'] or ''} | {j['apply_url']}")
    print(n, "candidatos", file=sys.stderr)
