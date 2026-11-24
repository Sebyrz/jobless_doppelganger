#!/usr/bin/env python3
"""
criterio.py — qué aviso vale la pena y en qué orden. Un solo filtro para todas las fuentes.
Todo lo personal (roles, sueldo, país, industrias) sale de config.json.

    rol(titulo)        -> (nivel, por qué)    nivel: "A" objetivo · "B" calce fuerte · "C" revisar · None
    local(job)         -> bool                empresa de tu país que publica en tu idioma (paga en moneda local)
    piso(job)          -> int                 piso en USD brutos al mes para ese aviso
    sueldo_ok(job)     -> (bool, por qué)     descarta si el tope publicado queda bajo tu piso
    pedir(job)         -> int                 cuánto pedir en USD brutos al mes
    pedir_texto(job)   -> str                 lo mismo para un campo de texto
    puntaje(job)       -> (0-100, [razones])  para ordenar la cola
"""
from __future__ import annotations
import re, time
import config

C = config.cargar()


def recargar():
    global C
    C = config.cargar()


# ---------- rol ----------
JUNIOR = ["junior", " jr ", " jr.", "trainee", "práctica", "practica", "intern ", "internship", "entry level",
          "entry-level", "pasantía", "pasantia", "becario"]
PARCIAL = ["part time", "part-time", "medio tiempo", "media jornada", "por hora", "hourly"]
SIN_PAGA = ["volunteer", "unpaid", "voluntari", "ad honorem", "commission only", "commission-only"]
IDIOMAS = ["spanish", "english", "russian", "german", "french", "portuguese", "mandarin", "chinese", "japanese",
           "korean", "arabic", "italian", "dutch", "polish", "turkish", "hebrew", "ukrainian", "swedish", "danish"]
# cargos que suelen pagar menos aunque el rol calce: bajan en la cola si no publican sueldo
BAJO = ["specialist", "especialista", "analyst", "analista", "associate", "coordinator", "coordinador",
        "representative", "agent ", "agente ", "assistant", "asistente"]
SENIOR = ["senior", "sr.", " sr ", "principal", "staff", "director", "head of", "vp ", "lead"]


def _t(title: str) -> str:
    return " " + re.sub(r"\s+", " ", (title or "").lower()) + " "


def _hay(lista, t) -> bool:
    return any(x.lower() in t for x in lista if x)


def rol(title: str) -> tuple[str | None, str]:
    t, R = _t(title), C["roles"]
    if C["excluir_junior"] and _hay(JUNIOR, t):
        return None, "junior / práctica"
    if _hay(PARCIAL, t):
        return None, "jornada parcial"
    if _hay(SIN_PAGA, t):
        return None, "sin sueldo (voluntariado o solo comisión)"
    otros = [i for i in IDIOMAS if i not in [x.lower() for x in C["idiomas"]]]
    if _hay(otros, t):
        return None, "pide un idioma que no hablas"
    if _hay(R["NO"], t) and not _hay(R["A"], t):   # "UX Product Owner" pasa; "Implementation Developer" no
        return None, "rol que no buscas"
    if _hay(R["A"], t):
        return "A", "rol objetivo"
    if _hay(R["B"], t):
        return "B", "calce fuerte"
    if _hay(R["C"], t):
        return "C", "calce discutible (revisar)"
    return None, f"rol no reconocido ({(title or '')[:35]})"


# ---------- sueldo ----------
def local(job: dict) -> bool:
    """Empresa de tu país que publica en tu idioma. Una multinacional que contrata por su oficina local
    suele publicar en inglés: a esa se le pide como a una de afuera."""
    iso = (C["pais_iso"] or "").upper()
    pais = (C["pais"] or "").upper()
    cc = (job.get("company_country") or "").strip().upper()
    return bool(C["moneda_local"]) and bool(cc) and cc in (iso, pais) and job.get("lang", C["idioma_local"]) == C["idioma_local"]


def _usd(monto_local: float) -> int:
    ml = C["moneda_local"]
    return int(-(-monto_local / float(ml["por_usd"]) // 50) * 50)   # hacia arriba, de 50 en 50


def piso(job: dict) -> int:
    return _usd(C["moneda_local"]["piso"]) if local(job) else int(C["piso_usd_mes"] or 0)


def _top(job: dict):
    return job.get("max_salary") or job.get("min_salary")


def sueldo_ok(job: dict) -> tuple[bool, str]:
    top, p = _top(job), piso(job)
    if top and p and top < p:
        return False, f"tope publicado {int(top)} USD (tu piso {p}{', empresa local' if local(job) else ''})"
    return True, f"{int(top)} USD" if top else "sin sueldo publicado"


def tope_creible(top) -> bool:
    """Un tope publicado de más de 4 veces lo que pides casi siempre es un sueldo mal leído (anual tomado
    como mensual, otra moneda). Sirve para ordenar la cola, pero no se escribe en un formulario."""
    ask = int(C["pedir_usd_mes"] or 0)
    return not ask or float(top) <= ask * 4


def pedir(job: dict) -> int:
    """USD brutos al mes. Con rango publicado: el tope (si la config lo dice), nunca bajo el piso."""
    top, p = _top(job), piso(job)
    if top and C["pedir_tope_si_publican"] and tope_creible(top):
        return max(int(top), p)
    if local(job):
        return _usd(C["moneda_local"]["pedir"])
    return max(int(C["pedir_usd_mes"] or 0), p)


def _miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def pedir_texto(job: dict) -> str:
    """Como se escribe en un campo de texto. Empresa local sin rango: en moneda local."""
    ml = C["moneda_local"]
    if local(job) and not _top(job):
        return f"entre {_miles(ml['piso'])} y {_miles(ml['pedir'])} {ml['codigo']} {ml.get('etiqueta', '')}".strip()
    return f"{pedir(job)} USD"


# ---------- años pedidos ----------
_ANOS_RX = re.compile(r"(\d{1,2})\s*\+?\s*(?:plus\s+|or more\s+|o más\s+|[-–]\s*\d{1,2}\s*)?(?:years|yrs|años)"
                      r"(?:\s+of|\s+de)?(?:\s+[\w/-]+){0,5}?\s+(?:experience|experiencia)", re.I)


def anos_pedidos(desc: str) -> int:
    """Años de experiencia que pide el aviso ('7+ years of product experience' -> 7). 0 si no lo dice."""
    return max((int(m.group(1)) for m in _ANOS_RX.finditer(desc or "") if int(m.group(1)) <= 20), default=0)


def exige_de_mas(job: dict) -> int:
    """Si el aviso pide 3 o más años sobre los tuyos en el rol, devuelve cuántos pide. Si no, 0."""
    tienes = int(C["anos_en_rol"] or 0)
    n = anos_pedidos(job.get("desc", ""))
    return n if tienes and n >= tienes + 3 else 0


# ---------- puntaje ----------
def _rx(palabras):
    pal = [re.escape(p.lower()) for p in palabras if p]
    return re.compile(r"\b(" + "|".join(pal) + r")\b", re.I) if pal else None


def puntaje(job: dict) -> tuple[int, list[str]]:
    nivel, _ = rol(job.get("title", ""))
    pts, por = {"A": 40, "B": 32, "C": 18}.get(nivel, 0), []
    por.append({"A": "rol objetivo", "B": "calce fuerte", "C": "rol por revisar"}.get(nivel, "rol fuera"))
    if exige_de_mas(job):
        pts -= 25; por.append(f"pide {exige_de_mas(job)}+ años (tienes {C['anos_en_rol']})")
    top, ask = _top(job), max(int(C["pedir_usd_mes"] or 0), 1)
    if top:
        s = 30 if top >= ask * 1.4 else 25 if top >= ask * 1.15 else 18 if top >= ask else 10 if top >= piso(job) else 0
        pts += s; por.append(f"tope {int(top)} USD")
    else:
        pts += 12; por.append("sin sueldo publicado")
    title, desc = job.get("title", ""), job.get("desc", "") or ""
    tl = _t(title)
    if nivel == "A" and _hay(SENIOR, tl) and int(C["anos_en_rol"] or 0) < 5:
        pts -= 8; por.append("cargo senior para tus años en el rol")
    if _hay(BAJO, tl) and not (top and top >= piso(job)):
        pts -= 10; por.append("cargo que suele pagar menos")
    kw = _rx(C["palabras_clave"])
    if kw:
        if kw.search(title):
            pts += 12; por.append("tus habilidades en el título")
        else:
            n = len(set(m.lower() for m in kw.findall(desc)))
            if n >= 3:
                pts += 8; por.append("pide tus habilidades")
            elif n:
                pts += 4
    ind = _rx(C["industrias"])
    if ind and ind.search(title + " " + desc + " " + (job.get("company_about") or "")):
        pts += 6; por.append("industria donde ya trabajaste")
    if C["bonus_ingles"] and job.get("lang") == "en":
        pts += 6; por.append("en inglés")
    pub = job.get("published_at")
    if pub:
        dias = (time.time() - float(pub)) / 86400
        if dias <= 14:
            pts += 6; por.append("publicado hace menos de 2 semanas")
        elif dias <= 30:
            pts += 3
        elif dias > 60:
            pts -= 5; por.append("aviso de más de 60 días")
    if job.get("apply_url") or job.get("source") == "getonbrd":
        pts += 4   # formulario directo: se puede llenar de punta a punta
    return max(0, min(100, pts)), por
