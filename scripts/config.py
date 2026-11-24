#!/usr/bin/env python3
"""
config.py — dónde viven tus datos y qué buscas. El plugin no trae nada personal: todo lo tuyo
vive en ~/.postula (o en la carpeta que diga la variable POSTULA_HOME).

    python3 config.py init     # crea ~/.postula con las plantillas (no pisa lo que ya existe)
    python3 config.py ver      # muestra la configuración efectiva (archivo + valores por defecto)
    python3 config.py ruta     # imprime la carpeta de datos
    python3 config.py estado   # qué falta para empezar a postular
"""
from __future__ import annotations
import copy, json, os, shutil, sys
from pathlib import Path

HOME = Path(os.environ.get("POSTULA_HOME") or Path.home() / ".postula").expanduser()
PLANTILLAS = Path(__file__).resolve().parent.parent / "plantillas"

CONFIG = HOME / "config.json"
PERFIL = HOME / "perfil.md"          # hechos tuyos: la única fuente de verdad de las respuestas
VOZ = HOME / "voz.md"                # cómo escribes, sacado de textos tuyos
BANCO = HOME / "banco.jsonl"         # respuestas reales que ya diste (ejemplos de tono y largo)
CV_DIR = HOME / "cv"                 # tus CV en PDF
POSTULADOS = HOME / "postulados.jsonl"   # registro único de lo enviado o descartado
COLA = HOME / "cola.jsonl"
COLA_MD = HOME / "cola.md"
MANUAL = HOME / "cola_manual.jsonl"  # avisos agregados a mano (LinkedIn, un link que te mandaron)
HUECOS = HOME / "huecos.md"          # lo que piden los avisos y tu perfil aún no muestra
CACHE = HOME / "cache"

DEFAULT: dict = {
    # dónde vives y desde dónde puedes trabajar
    "pais": "",                     # en inglés, como lo escriben los avisos: "Chile", "Mexico", "Colombia"
    "pais_iso": "",                 # "CL", "MX", "CO"
    "pais_getonbrd": "",            # cómo lo nombra GetOnBoard: "chile", "mexico", "colombia"
    "ciudades": [],                 # opcional: si un aviso nombra tu ciudad, cuenta como tu país
    "zonas_ok": ["latam", "latin america", "south america", "americas", "worldwide", "anywhere", "global",
                 "work from anywhere", "any location", "international"],
    "solo_remoto": True,
    "idiomas": ["spanish", "english"],  # los que hablas a nivel de trabajo (en inglés)
    "idioma_local": "es",           # idioma de los avisos de empresas de tu país

    # sueldo, en USD BRUTOS al mes (los rangos publicados son brutos)
    "piso_usd_mes": 0,              # bajo esto no postulas
    "pedir_usd_mes": 0,             # lo que pides cuando el aviso no publica rango
    "pedir_tope_si_publican": True,  # con rango publicado, pides el tope
    # empresas de tu país que publican en tu idioma suelen pagar en moneda local:
    # {"codigo": "CLP", "por_usd": 950, "piso": 2000000, "pedir": 2500000, "etiqueta": "líquidos"}
    "moneda_local": None,

    # qué roles buscas (frases en minúscula; se buscan dentro del título del aviso)
    "roles": {
        "A": [],    # tu rol objetivo
        "B": [],    # roles donde tu historia calza directo
        "C": [],    # calce posible pero discutible: los decides tú
        "NO": [],   # títulos que nunca quieres ver
    },
    "excluir_junior": True,
    "anos_en_rol": 0,               # tus años en el rol A: si un aviso A pide 3+ más, baja en la cola
    "industrias": [],               # donde ya trabajaste: suben en la cola
    "palabras_clave": [],           # habilidades que te distinguen: suben en la cola
    "bonus_ingles": True,           # los avisos en inglés suelen pagar más

    # búsquedas que el radar le hace a cada bolsa
    "busquedas": [],
    "getonbrd_categorias": ["programming", "innovation-agile", "operations-management", "customer-support",
                            "sales", "technical-support", "machine-learning-ai", "design-ux", "data-science-analytics", "hr",
                            "digital-marketing", "other"],

    # límites
    "max_por_tanda": 10,
    "linkedin_max_dia": 10,
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def cargar() -> dict:
    data = {}
    if CONFIG.exists():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"[postula] {CONFIG} no es JSON válido: {e}")
    data = {k: v for k, v in data.items() if not k.startswith("_")}   # claves "_nota" son comentarios
    return _merge(DEFAULT, data)


def iniciar() -> list[str]:
    """Crea la carpeta de datos con las plantillas. Nunca pisa un archivo que ya existe."""
    HOME.mkdir(parents=True, exist_ok=True)
    CV_DIR.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    creados = []
    for src, dst in (("config.json", CONFIG), ("perfil.md", PERFIL), ("voz.md", VOZ), ("banco.jsonl", BANCO)):
        if not dst.exists():
            shutil.copy(PLANTILLAS / src, dst)
            creados.append(dst.name)
    return creados


def estado() -> list[str]:
    """Lo que falta para que el radar y las respuestas funcionen bien."""
    c, falta = cargar(), []
    if not HOME.exists():
        return ["no existe la carpeta de datos: corre `python3 config.py init`"]
    if not c["pais"] or not c["pais_iso"]:
        falta.append("config.json: pais y pais_iso")
    if not c["piso_usd_mes"] or not c["pedir_usd_mes"]:
        falta.append("config.json: piso_usd_mes y pedir_usd_mes")
    if not (c["roles"]["A"] or c["roles"]["B"]):
        falta.append("config.json: roles A o B (qué cargos buscas)")
    if not c["busquedas"]:
        falta.append("config.json: busquedas")
    for p, marca in ((PERFIL, "PENDIENTE"), (VOZ, "PENDIENTE")):
        if not p.exists() or marca in p.read_text(encoding="utf-8")[:400]:
            falta.append(f"{p.name}: sin completar (skill perfil)")
    if not any(CV_DIR.glob("*.pdf")):
        falta.append(f"no hay CV en PDF en {CV_DIR}")
    return falta


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ver"
    if cmd == "init":
        nuevos = iniciar()
        print(f"[postula] carpeta de datos: {HOME}")
        print("[postula] creados: " + (", ".join(nuevos) if nuevos else "nada (ya existía todo)"))
    elif cmd == "ruta":
        print(HOME)
    elif cmd == "estado":
        f = estado()
        print("[postula] listo para postular" if not f else "[postula] falta:\n  - " + "\n  - ".join(f))
    else:
        print(json.dumps(cargar(), ensure_ascii=False, indent=2))
