#!/usr/bin/env python3
"""Pruebas de los arreglos de la auditoría del 24-nov-2026. Sin red.

    python3 -m unittest discover -s tests -v
"""
import json, os, sys, time, unittest
from pathlib import Path

import test_doppelganger as base   # arma la carpeta de datos temporal y el perfil de prueba
from test_doppelganger import aviso

import config, criterio, fuentes, guardia, radar, cola, directo, tableros  # noqa: E402


class Registro(unittest.TestCase):
    def setUp(self):
        if config.POSTULADOS.exists():
            config.POSTULADOS.unlink()

    def test_un_envio_de_lever_no_esconde_otro_aviso_de_lever(self):
        cola.marcar("https://jobs.lever.co/acme/abc-123/apply", "submitted", "Product Manager", "Acme")
        otro = aviso(url="https://jobs.lever.co/zeta/999/apply", title="Customer Success Lead", company="Zeta")
        self.assertFalse(radar.ya_postulado(otro, radar.hechos()))
        mismo = aviso(url="https://jobs.lever.co/acme/abc-123", title="Otro título", company="Otra")
        self.assertTrue(radar.ya_postulado(mismo, radar.hechos()))

    def test_clave_por_bolsa(self):
        k = radar.clave_url
        self.assertEqual(k("https://jobs.ashbyhq.com/acme/uuid-1/application"), k("https://jobs.ashbyhq.com/acme/uuid-1"))
        self.assertNotEqual(k("https://jobs.ashbyhq.com/acme/uuid-1/application"), k("https://jobs.ashbyhq.com/beta/uuid-2/application"))
        self.assertNotEqual(k("https://acme.com/careers?gh_jid=1"), k("https://acme.com/careers?gh_jid=2"))
        self.assertEqual(k("https://apply.workable.com/acme/j/XYZ/apply/"), k("https://apply.workable.com/acme/j/XYZ"))
        # GetOnBoard: el log viejo guarda la categoría en la ruta, la API no
        self.assertEqual(k("https://www.getonbrd.com/jobs/product/pm-acme-remote"), k("https://www.getonbrd.com/jobs/pm-acme-remote"))

    def test_empresas_que_comparten_una_palabra_no_son_la_misma(self):
        cola.marcar("https://x.io/j/1", "submitted", "Product Manager", "Scale AI")
        self.assertFalse(radar.ya_postulado(aviso(url="https://y.io/j/2", company="Harvey AI"), radar.hechos()))
        self.assertTrue(radar.ya_postulado(aviso(url="https://y.io/j/3", company="scaleai"), radar.hechos()))
        self.assertTrue(radar.misma_empresa("Acme", "Acme Inc"))
        self.assertFalse(radar.misma_empresa("Acme Labs", "Beta Labs"))


class SueldoLeido(unittest.TestCase):
    def test_un_rango_que_no_es_sueldo_no_cuenta(self):
        s = tableros.sueldo_en_texto
        self.assertEqual(s("You will own accounts from $1,000 - $10,000 in ACV."), (None, None))
        self.assertEqual(s("We offer a $500 to $2,000 learning stipend. Salary: $120k - $150k"), (10000, 12500))
        self.assertEqual(s("A bonus of $5,000 - $10,000 comes on top of your salary."), (None, None))
        self.assertEqual(s("The base salary range is $90,000 - $110,000 plus bonus."), (7500, 9167))

    def test_anual_no_se_lee_como_mensual(self):
        self.assertEqual(tableros.sueldo_en_texto("Salary $18,000 - $19,500 per year"), (1500, 1625))
        self.assertEqual(fuentes.sueldo_texto("$18,000 - $19,500"), (None, None))        # sin período: no se adivina
        self.assertEqual(fuentes.sueldo_texto("USD 4000-6000/month"), (4000, 6000))
        self.assertEqual(fuentes.sueldo_texto("$120k - $150k"), (10000, 12500))

    def test_401k_y_moneda(self):
        self.assertEqual(fuentes.sueldo_texto("$120k-$150k plus 401k match"), (10000, 12500))
        self.assertEqual(fuentes.sueldo_texto("€60k - €72k"), (5400, 6480))

    def test_un_tope_absurdo_no_llega_al_formulario(self):
        j = aviso(max_salary=19500)                      # pides 3.800: 19.500 al mes es un sueldo mal leído
        self.assertEqual(criterio.pedir(j), 3800)
        self.assertEqual(criterio.pedir(aviso(max_salary=5000)), 5000)


class Bolsas(unittest.TestCase):
    def test_la_bolsa_se_busca_por_el_nombre_completo(self):
        self.assertEqual(directo.toks("Scale AI"), ["scale-ai", "scaleai"])
        self.assertEqual(directo.toks("The Hackett Group"), ["hackett-group", "hackettgroup"])
        self.assertEqual(directo.toks("Customer.io"), ["customerio"])
        self.assertEqual(directo.toks_dudosos("Open English"), ["open"])
        self.assertEqual(directo.toks_dudosos("Acme"), [])

    def test_un_error_no_se_ve_como_bolsa_vacia(self):
        directo.FALLOS.clear()
        self.assertIsNone(directo._get("http://127.0.0.1:9/nada", timeout=1))   # puerto cerrado: no es un 404
        self.assertEqual(sum(directo.FALLOS.values()), 1)

    def test_salud_avisa(self):
        directo.FALLOS.clear()
        self.assertEqual(tableros.salud({"greenhouse": 70, "ashby": 70, "lever": 22}, 342, 156), [])
        self.assertTrue(any("lever" in a for a in tableros.salud({"greenhouse": 70, "ashby": 70, "lever": 0}, 342, 140)))
        directo.FALLOS["greenhouse.io (429)"] = 40
        self.assertTrue(any("429" in a for a in tableros.salud({"greenhouse": 30, "ashby": 70, "lever": 22}, 342, 120)))
        directo.FALLOS.clear()


class GuardiaFina(unittest.TestCase):
    def setUp(self):
        self.perfil = config.PERFIL.read_text(encoding="utf-8")

    def tearDown(self):
        config.PERFIL.write_text(self.perfil, encoding="utf-8")

    def test_numero_en_letras(self):
        self.assertFalse(guardia.revisar("Lideré a diez personas.", "why")["ok"])
        self.assertTrue(guardia.revisar("Llevo cuatro años en producto.", "why")["ok"])     # el perfil dice 4

    def test_titulo_que_el_perfil_niega(self):
        config.PERFIL.write_text("# Perfil\n- 4 años en producto\n## Educación\n- No tengo MBA.\n", encoding="utf-8")
        self.assertFalse(guardia.revisar("I hold an MBA.", "why")["ok"])
        config.PERFIL.write_text("# Perfil\n## Educación\n- MBA, Universidad de los Andes (2019).\n", encoding="utf-8")
        self.assertTrue(guardia.revisar("I hold an MBA.", "why")["ok"])

    def test_nombres_propios_con_el_aviso(self):
        av = "Beta is hiring a Product Manager. We use Jira."
        r = guardia.revisar("Ustedes usan Jira; yo subí la conversión 23% en Acme con Salesforce.", "why", aviso=av)
        self.assertEqual([p for p in r["problemas"] if "nombre" in p and "Salesforce" in p].__len__(), 1)
        self.assertFalse(any("Jira" in p or "Acme" in p for p in r["problemas"]))
        self.assertTrue(guardia.revisar("Ustedes usan Jira; yo subí la conversión 23% en Acme.", "why", aviso=av)["ok"])
        # sin el aviso no se revisan nombres (la empresa a la que postulas saldría siempre)
        self.assertTrue(guardia.revisar("En Beta quiero repetir el 23% de Acme.", "why")["ok"])


class SinDuplicados(unittest.TestCase):
    """El modo automático no puede mandar dos veces: lo ya registrado tiene que seguir saliendo como postulado."""
    def setUp(self):
        if config.POSTULADOS.exists():
            config.POSTULADOS.unlink()

    def fila(self, **kw):
        base = {"veredicto": "match", "puntaje": 85, "source": "himalayas", "url": "https://himalayas.app/jobs/pm-acme",
                "apply_url": "https://jobs.ashbyhq.com/acme/uuid-1/application", "title": "Product Manager",
                "company": "Acme", "pedir": 4000, "company_country": "", "lang": "en"}
        base.update(kw)
        return base

    def test_registrado_con_el_link_del_formulario(self):
        for url in ("https://jobs.ashbyhq.com/acme/uuid-1/application", "https://jobs.ashbyhq.com/acme/uuid-1",
                    "https://himalayas.app/jobs/pm-acme"):
            config.POSTULADOS.write_text("", encoding="utf-8")
            cola.marcar(url, "submitted", "", "")          # sin título ni empresa: solo la URL lo reconoce
            self.assertTrue(radar.ya_postulado(self.fila(), radar.hechos()), url)
        config.POSTULADOS.write_text("", encoding="utf-8")
        cola.marcar("https://jobs.lever.co/acme/abc/thanks", "submitted", "", "")
        self.assertTrue(radar.ya_postulado(self.fila(apply_url="https://jobs.lever.co/acme/abc/apply"), radar.hechos()))

    def test_elegibles_no_repite_lo_enviado(self):
        filas = [self.fila(), self.fila(url="https://himalayas.app/jobs/pm-beta", company="Beta", title="Product Owner",
                                        apply_url="https://jobs.ashbyhq.com/beta/uuid-2/application")]
        self.assertEqual(len(cola.elegibles(filas)[0]), 2)
        cola.marcar(filas[0]["apply_url"], "submitted", "Product Manager", "Acme", modo="auto")
        si, no, _ = cola.elegibles(filas)
        self.assertEqual([r["company"] for r in si], ["Beta"])
        self.assertTrue(any("ya postulado" in why for _, why in no))

    def test_enviando_frena_el_reenvio_y_se_avisa(self):
        f = self.fila()
        cola.marcar(f["apply_url"], "enviando", "Product Manager", "Acme")
        self.assertTrue(radar.ya_postulado(f, radar.hechos()))
        self.assertEqual(len(cola.sin_confirmar()), 1)
        cola.marcar(f["apply_url"], "submitted", "Product Manager", "Acme", cv="cv/pm.pdf", pedir="4000 USD",
                    respuestas=[{"q": "Why?", "a": "Porque sí."}])
        self.assertEqual(cola.sin_confirmar(), [])
        ultimo = json.loads(config.POSTULADOS.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((ultimo["cv"], ultimo["pedir"], ultimo["respuestas"][0]["a"]), ("cv/pm.pdf", "4000 USD", "Porque sí."))


if __name__ == "__main__":
    unittest.main()
