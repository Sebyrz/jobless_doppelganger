#!/usr/bin/env python3
"""
guardia.py — revisa una respuesta antes de que vaya a un formulario. Claude redacta con tu voz y tu
perfil; esto revisa en frío lo que se cuela: frases de IA, números que no están en tu perfil, títulos
que no tienes, huecos confesados, promesas y largo.

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
    m = TITULO.search(texto)
    if m and m.group(0).lower() not in perfil.lower():
        problemas.append(f"afirma un título o grado que tu perfil no dice: '{m.group(0)}'")
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
    r.add_argument("--aviso", default=None, help="archivo con el texto del aviso (sus números valen)")
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
