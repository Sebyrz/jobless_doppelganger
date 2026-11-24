#!/usr/bin/env python3
"""Pruebas de postula. Sin red y sin modelo: solo las reglas, con la config de ejemplo.

    python3 -m unittest discover -s tests -v
"""
import json, os, shutil, sys, tempfile, time, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="postula-test-")
os.environ["POSTULA_HOME"] = TMP
shutil.copy(RAIZ / "plantillas" / "config.ejemplo.json", Path(TMP) / "config.json")
(Path(TMP) / "perfil.md").write_text("# Perfil\n- 4 años en producto, 7 en tecnología.\n- Subí la conversión 23% en Acme.\n"
                                     "## Educación\n- Ingeniería comercial, sin terminar.\n", encoding="utf-8")
(Path(TMP) / "voz.md").write_text("# Voz\n## Frases que nunca uso\n- a todo dar\n## Largo\n", encoding="utf-8")
sys.path.insert(0, str(RAIZ / "scripts"))

import config, criterio, fuentes, getonbrd_api as gob, guardia, radar, cola, directo, tableros  # noqa: E402


def aviso(**kw):
    base = {"source": "getonbrd", "url": "https://www.getonbrd.com/jobs/x-acme-remote", "title": "Product Manager",
            "company": "Acme", "company_about": "", "remote_modality": "fully_remote", "tenants": [],
            "min_salary": None, "max_salary": None, "seniority": "Senior", "lang": "en",
            "published_at": time.time(), "desc": ""}
    base.update(kw)
    return base


class Config(unittest.TestCase):
    def test_carga_y_merge(self):
        c = config.cargar()
        self.assertEqual(c["pais"], "Colombia")
        self.assertEqual(c["max_por_tanda"], 10)          # viene del default
        self.assertNotIn("_nota", c)

    def test_init_no_pisa(self):
        antes = (Path(TMP) / "perfil.md").read_text(encoding="utf-8")
        config.iniciar()
        self.assertEqual((Path(TMP) / "perfil.md").read_text(encoding="utf-8"), antes)
        self.assertTrue((Path(TMP) / "banco.jsonl").exists())


class Rol(unittest.TestCase):
    def test_niveles(self):
        self.assertEqual(criterio.rol("Senior Product Manager, Payments")[0], "A")
        self.assertEqual(criterio.rol("Implementation Manager")[0], "B")
        self.assertEqual(criterio.rol("Solutions Engineer")[0], "C")

    def test_descartes(self):
        for t in ("Backend Developer", "Product Owner Junior", "Part Time Project Manager",
                  "Product Manager (Volunteer)", "Product Manager (German speaker)", "Barista"):
            self.assertIsNone(criterio.rol(t)[0], t)

    def test_no_pierde_contra_objetivo(self):
        # "designer" está en NO, pero "product owner" es objetivo
        self.assertEqual(criterio.rol("Product Owner for Designer Tools")[0], "A")
        self.assertIsNone(criterio.rol("Senior Analytics & Implementation Developer")[0])


class Sueldo(unittest.TestCase):
    def test_piso(self):
        self.assertFalse(criterio.sueldo_ok(aviso(max_salary=2500))[0])
        self.assertTrue(criterio.sueldo_ok(aviso(max_salary=3200))[0])
        self.assertTrue(criterio.sueldo_ok(aviso())[0])

    def test_pedir(self):
        self.assertEqual(criterio.pedir(aviso()), 3800)
        self.assertEqual(criterio.pedir(aviso(min_salary=3000, max_salary=5000)), 5000)

    def test_empresa_local(self):
        j = aviso(company_country="CO", lang="es")
        self.assertTrue(criterio.local(j))
        self.assertEqual(criterio.pedir_texto(j), "entre 9.000.000 y 11.000.000 COP brutos")
        self.assertEqual(criterio.piso(j), 2250)   # 9.000.000 / 4.000, hacia arriba de 50 en 50
        self.assertFalse(criterio.local(aviso(company_country="CO", lang="en")))   # multinacional en inglés


class Anos(unittest.TestCase):
    def test_anos_pedidos(self):
        self.assertEqual(criterio.anos_pedidos("You have 8+ years of product management experience"), 8)
        self.assertEqual(criterio.anos_pedidos("Founded 12 years ago"), 0)

    def test_exige_de_mas(self):
        self.assertEqual(criterio.exige_de_mas(aviso(desc="10+ years of experience in product")), 10)
        self.assertEqual(criterio.exige_de_mas(aviso(desc="5 years of experience")), 0)


class Ubicacion(unittest.TestCase):
    def test_listas_y_texto(self):
        self.assertEqual(fuentes.ubicacion(["Colombia", "Mexico"])[0], "ok")
        self.assertEqual(fuentes.ubicacion(["United States"])[0], "no")
        self.assertEqual(fuentes.ubicacion("LATAM")[0], "ok")
        self.assertEqual(fuentes.ubicacion("Remote")[0], "duda")
        self.assertEqual(fuentes.ubicacion("Remote - Bogotá")[0], "ok")

    def test_getonbrd(self):
        self.assertTrue(gob.location_ok(aviso(remote_modality="remote_local", tenants=["colombia"]))[0])
        self.assertFalse(gob.location_ok(aviso(remote_modality="remote_local", tenants=["chile"]))[0])
        self.assertFalse(gob.location_ok(aviso(remote_modality="hybrid"))[0])

    def test_tableros(self):
        ok = lambda l, d="": tableros._lugar_ok({"lugar": l, "desc": d})[0]
        self.assertEqual(ok("Remote - LATAM"), "ok")
        self.assertEqual(ok("New York, United States"), "no")
        self.assertEqual(ok("Remote", "Must be based in the US"), "no")
        self.assertEqual(ok("Remote", "We hire across Latin America"), "ok")
        self.assertEqual(ok("Remote", "Join our global team serving customers worldwide"), "duda")

    def test_directo_elige_tu_pais(self):
        hs = [{"lugar": "Remote - US"}, {"lugar": "Remote - Colombia"}, {"lugar": "Remote"}]
        self.assertEqual(directo.elegir(hs)["lugar"], "Remote - Colombia")


class Radar(unittest.TestCase):
    def test_veredicto(self):
        self.assertEqual(radar.veredicto(aviso())[0], "match")
        self.assertEqual(radar.veredicto(aviso(title="Solutions Engineer"))[0], "revisar")
        self.assertEqual(radar.veredicto(aviso(title="Backend Developer"))[0], "skip")

    def test_dedup(self):
        cola.marcar("https://x.com/jobs/1", "submitted", "Product Manager", "Acme")
        hechos = radar.hechos()
        self.assertTrue(radar.ya_postulado(aviso(url="https://y.com/otro", title="Product Manager"), hechos))
        cola.marcar("https://x.com/jobs/2", "falta_dato", "Program Manager", "Beta")
        self.assertFalse(radar.ya_postulado(aviso(url="https://x.com/jobs/2", title="Program Manager", company="Beta"),
                                            radar.hechos()))


class Guardia(unittest.TestCase):
    def test_limpia(self):
        r = guardia.revisar("Subí la conversión 23% en Acme; hoy tengo 4 años en producto.", "why")
        self.assertTrue(r["ok"], r)

    def test_numero_inventado(self):
        r = guardia.revisar("Tengo 10 años en producto.", "why")
        self.assertFalse(r["ok"])
        self.assertIn("10", " ".join(r["problemas"]))

    def test_numero_del_aviso_vale(self):
        self.assertTrue(guardia.revisar("Ustedes atienden 40 países; yo subí la conversión 23%.", "why",
                                        aviso="We operate in 40 countries")["ok"])

    def test_frases(self):
        self.assertFalse(guardia.revisar("I'm passionate about payments.", "why")["ok"])
        self.assertFalse(guardia.revisar("Esto quedó a todo dar.", "why")["ok"])   # frase de voz.md

    def test_titulo_y_huecos(self):
        self.assertFalse(guardia.revisar("I hold a degree in economics.", "why")["ok"])
        self.assertFalse(guardia.revisar("No tengo experiencia con Jira, pero aprendo rápido.", "why")["ok"])

    def test_pregunta(self):
        self.assertEqual(guardia.pregunta("Will you now or in the future require visa sponsorship?")["responde"], "tú")
        self.assertEqual(guardia.pregunta("What is your gender?")["responde"], "tú")
        self.assertEqual(guardia.pregunta("Why do you want to work at Acme?")["responde"], "agente")


if __name__ == "__main__":
    unittest.main()
