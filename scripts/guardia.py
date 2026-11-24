#!/usr/bin/env python3
"""
guardia.py — revisa una respuesta antes de que vaya a un formulario. Claude redacta con tu voz y tu
perfil; esto revisa en frío lo que se cuela: frases de IA, números (en dígitos o en letras) que no están
en tu perfil, títulos que no tienes o que tu perfil niega, huecos confesados, promesas y largo. Con
--aviso también marca nombres propios (clientes, herramientas, empresas) que no están en tu perfil ni
en el aviso. Es un filtro de texto, no entiende lo que lee: baja el riesgo, no lo elimina.

    python3 guardia.py revisar --tipo why --texto "Ustedes ..."      # tipos: why, cover, corta, default
    echo "texto" | python3 guardia.py revisar --tipo cover --aviso aviso.txt
    python3 guardia.py pregunta "Do you require visa sponsorship?"   # ¿la contesta el agente o tú?

Salida: JSON {"ok": bool, "problemas": [...]}. Con un problema, se reescribe; no se envía igual.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config

FRASES_IA = [
    "i'm excited about the opportunity", "i am excited about the opportunity", "passionate about", "leverage",
    "strong reputation", "commitment to innovation", "seamless", "in today's fast-paced", "look forward to the opportunity",
    "i believe i would be a great fit", "i am confident that", "i'm confident that", "extensive experience",
    "proven track record", "dynamic team", "synergy", "delve", "tapestry", "game-changer", "cutting-edge",
    "estoy muy interesado en la oportunidad", "me apasiona", "prestigiosa", "líder en su industria", "reconocida empresa",
    "amplia experiencia", "aporte de valor significativo", "sinergia", "en el mundo actual", "it's not just",
]

HUECOS = [
    r"no he trabajado (con|en)", r"no tengo experiencia", r"\bi haven'?t (worked|done|used|delivered)",
    r"\bi have not (worked|done|used)", r"\bi'?m not from", r"\bno vengo de", r"(new|nuevo|nueva)s? (to|para) m[eií]",
    r"need to (learn|ramp)", r"(tendría|tendria|tengo) que aprender", r"ramp up", r"learn (it )?fast",
    r"aprend(o|er) r[aá]pido", r"dispuesto a (aprender|certificar)", r"willing to learn", r"me certific",
    r"(get|getting|sacar) (the |la )?certifica",
]

TITULO = re.compile(r"\b(b\.?sc|bachelor'?s?|master'?s?|mba|ph\.?d|licenciad[oa]|titulad[oa]|ingenier[oa] (civil|comercial)|"
                    r"my degree|i hold a degree|tengo (un )?título|graduated|me titulé|egresé)\b", re.I)

LARGO = {"why": 60, "cover": 120, "corta": 40, "default": 80}

# preguntas que el agente no contesta por ti: queda en borrador y te pregunta
SOLO_TU = [
    (r"notice period|aviso previo|start date|when can you start|cu[aá]ndo (puedes|podr[ií]as) (empezar|comenzar)|"
     r"earliest start|availability to start", "fecha de inicio / aviso previo"),
    (r"sponsor|visa|work permit|authori[sz]ed to work|legally (able|authori[sz]ed)|right to work|"
     r"permiso de trabajo|autorizaci[oó]n para trabajar|citizen|ciudadan", "autorización de trabajo / visa"),
    (r"current (salary|compensation|pay)|sueldo actual|renta actual|salario actual|[uú]ltima renta", "sueldo actual"),
    (r"\breferenc(e|es|ias?)\b", "referencias"),
    (r"gender|g[eé]nero|race|ethnic|etnia|disabilit|discapacidad|veteran|pronoun|orientaci[oó]n|sexual", "pregunta demográfica"),
    (r"date of birth|fecha de nacimiento|passport|pasaporte|\brut\b|\bdni\b|\bcurp\b|social security|home address|"
     r"direcci[oó]n", "dato personal"),
    (r"transcript|gpa|promedio|certificado de notas|security clearance", "documento o dato académico"),
    (r"\b(ai|artificial intelligence|chatgpt|llm)\b.{0,60}\b(use|used|assist|help|wrote|write)|"
     r"certify|attest|declar|confirmo que", "declaración o certificación (la firmas tú)"),
    (r"video|loom|record yourself|gr[aá]bate", "video"),
]


# números escritos con letras: "lideré a diez personas" es tan número como "10". Del cuatro para arriba
# (uno, dos y tres son ruido, igual que en dígitos). "once" queda fuera: en inglés es otra palabra.
NUM_PALABRA = {"cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "doce": 12, "quince": 15,
               "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "cien": 100,
               "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
               "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100}
_NUM_PALABRA_RX = re.compile(r"\b(" + "|".join(NUM_PALABRA) + r")\b", re.I)

# una línea del perfil que niega ("no tengo MBA", "sin terminar") no respalda un título
_NIEGA = re.compile(r"\b(no|sin|not|never|nunca|without|ni|incomplet\w*|unfinished|inconclus\w*|pendiente|dropped)\b", re.I)

# palabras con mayúscula que no son un cliente, una herramienta ni una empresa
_NO_ES_NOMBRE = {"i", "i'm", "i've", "i'd", "i'll", "latam", "latin", "america", "américa", "americas", "english", "spanish",
                 "español", "inglés", "usd", "us", "usa", "europe", "europa", "ai", "ia", "api", "saas", "b2b", "b2c",
                 "kpi", "kpis", "okr", "okrs", "cv", "ceo", "cto", "coo", "cfo", "pm", "po", "qa", "ux", "ui", "it", "hr",
                 "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february",
                 "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}
_NOMBRE_RX = re.compile(r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ0-9&+#'’-]+")


def _afirma(perfil: str, termino: str) -> bool:
    """El perfil nombra `termino` en una línea que no lo niega."""
    t = termino.lower()
    return any(t in l.lower() and not _NIEGA.search(l) for l in perfil.splitlines())


def nombres_sin_fuente(texto: str, fuente: str) -> list[str]:
    """Nombres propios (clientes, herramientas, empresas) de la respuesta que no están en `fuente`.
    No mira la primera palabra de cada frase: ahí la mayúscula no dice nada."""
    fl, out = fuente.lower(), []
    for m in _NOMBRE_RX.finditer(texto):
        antes = texto[:m.start()].rstrip()
        if not antes or antes[-1] in ".!?:;¿¡\"“(\n":
            continue
        w = m.group(0).strip("'’-")
        base = w.lower()
        if base in _NO_ES_NOMBRE or base.rstrip("s") in fl or base in fl:
            continue
        if w not in out:
            out.append(w)
    return out


def _norm_num(s: str) -> str:
    return re.sub(r"[.,\s]", "", s)


def _frases_voz() -> list[str]:
    """Frases de la sección 'Frases que nunca uso' de voz.md."""
    if not config.VOZ.exists():
        return []
    txt = config.VOZ.read_text(encoding="utf-8")
    m = re.search(r"##\s*Frases que nunca uso\s*\n(.*?)(\n##|\Z)", txt, re.S | re.I)
    return [l.strip("-• \t").lower() for l in (m.group(1).splitlines() if m else []) if l.strip("-• \t")]


def revisar(texto: str, tipo: str = "default", aviso: str = "", permitidos: list[str] | None = None) -> dict:
    problemas, low = [], texto.lower()
    perfil = config.PERFIL.read_text(encoding="utf-8") if config.PERFIL.exists() else ""
    if not texto.strip():
        return {"ok": False, "problemas": ["respuesta vacía"]}
    for f in dict.fromkeys(FRASES_IA + _frases_voz()):
        if f and f in low:
            problemas.append(f"frase de IA o que no usas: '{f}'")
    # números: cada número de la respuesta tiene que estar en tu perfil (o en el aviso, o ser el sueldo pedido)
    fuentes_ok = {_norm_num(x.rstrip(".,")) for x in re.findall(r"\d[\d.,]*", perfil + " " + aviso + " " + " ".join(permitidos or []))}
    for n in re.findall(r"\d[\d.,]*", texto):
        nn = _norm_num(n.rstrip(".,"))
        if len(nn) == 1 and nn in "0123":   # "1 a 3 frases", "2 cosas": ruido
            continue
        if nn and nn not in fuentes_ok:
            problemas.append(f"número que no está en tu perfil: {n.rstrip('.,')}")
    for m in _NUM_PALABRA_RX.finditer(texto):
        if str(NUM_PALABRA[m.group(1).lower()]) not in fuentes_ok and m.group(1).lower() not in (perfil + " " + aviso).lower():
            problemas.append(f"número que no está en tu perfil: {m.group(1)}")
    m = TITULO.search(texto)
    if m and not _afirma(perfil, m.group(0)):
        problemas.append(f"afirma un título o grado que tu perfil no dice: '{m.group(0)}'")
    if aviso:   # sin el aviso, el nombre de la empresa a la que postulas saldría siempre como desconocido
        for w in nombres_sin_fuente(texto, perfil + " " + aviso + " " + " ".join(permitidos or [])):
            problemas.append(f"nombre que no está en tu perfil ni en el aviso: '{w}' (si es real, anótalo en perfil.md)")
    for rx in HUECOS:
        if re.search(rx, low):
            problemas.append("confiesa un hueco o promete algo (eso va a huecos.md, no al formulario)")
            break
    tope = LARGO.get(tipo, LARGO["default"])
    n = len(texto.split())
    if n > tope * 1.3:
        problemas.append(f"muy largo: {n} palabras (máximo ~{tope} para '{tipo}')")
    if "•" in texto or len(re.findall(r"^\s*[-*]\s", texto, re.M)) > 1:
        problemas.append("usa viñetas en una respuesta abierta")
    if texto.count("—") > 1:
        problemas.append("más de un guion largo (—): suena a IA")
    return {"ok": not problemas, "problemas": problemas}


def pregunta(q: str) -> dict:
    t = q.lower()
    for rx, que in SOLO_TU:
        if re.search(rx, t):
            return {"responde": "tú", "por_que": que}
    return {"responde": "agente", "por_que": "se contesta con tu perfil y tu voz"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("revisar")
    r.add_argument("--tipo", default="default", choices=list(LARGO))
    r.add_argument("--texto", default=None)
    r.add_argument("--aviso", default=None, help="archivo con el texto del aviso: sus números y nombres valen, y activa la revisión de nombres propios")
    r.add_argument("--permitir", action="append", default=[], help="número extra que vale (ej. el sueldo pedido)")
    p = sub.add_parser("pregunta")
    p.add_argument("q")
    a = ap.parse_args()
    if a.cmd == "revisar":
        texto = a.texto if a.texto is not None else sys.stdin.read()
        aviso = Path(a.aviso).read_text(encoding="utf-8") if a.aviso else ""
        print(json.dumps(revisar(texto, a.tipo, aviso, a.permitir), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(pregunta(a.q), ensure_ascii=False, indent=2))
