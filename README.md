# jobless_doppelganger

*Tu doble sin pega. Postula por ti mientras tú haces otra cosa.*

**Tu agente de postulación en Claude. Aprende tu historia y tu forma de escribir, encuentra los
trabajos remotos que calzan contigo y llena los formularios por ti. Tú solo dices "envía".**

[English](README.en.md) · Gratis y de código abierto (MIT)

---

Buscar trabajo remoto desde Latinoamérica es un segundo trabajo. Revisar diez bolsas, descartar los
avisos que en letra chica dicen "solo EE. UU.", escribir por quinta vez en la semana por qué te
interesa una empresa, copiar tu experiencia en un formulario que no lee tu CV. Cuarenta minutos por
postulación, y la mayoría no contesta.

Tu doppelganger hace ese trabajo contigo dentro de Claude:

| | Qué hace | Lo que te ahorras |
|---|---|---|
| **1. Empezar** | Crea tu carpeta privada, conecta Claude a tu Chrome y te deja con la sesión abierta en GetOnBoard y LinkedIn. | Configurar cosas. Son 10 minutos. |
| **2. Perfil** | Lee tu CV, tu LinkedIn y tus postulaciones pasadas. Arma tu perfil (solo hechos, con su fuente) y aprende cómo escribes tú. Si no tienes CV, te lo pide o lo arma contigo. | Explicarle a cada formulario quién eres. |
| **3. Mejorar CV** | Compara tu CV y tu LinkedIn con lo que piden los avisos reales de tu rol y te dice qué cambiar, por qué y cómo queda, listo para pegar. | Adivinar por qué no te llaman. |
| **4. Radar** | Barre GetOnBoard, Himalayas, Remotive, RemoteOK, Working Nomads y las bolsas de una lista de 340 empresas que contratan remoto (un día cualquiera, cerca de la mitad tiene avisos abiertos). Filtra por tu rol, tu piso de sueldo y tu país. Ordena por calce. | Horas de scroll y avisos que no eran para ti. |
| **5. Postular** | Arma tandas de 5 a 10 avisos, escribe cada respuesta con tu voz, te muestra todo junto, y con tu OK (o en modo automático) llena y envía los formularios (GetOnBoard, Greenhouse, Ashby, Lever, Workable). | Los 40 minutos por postulación. |

## Lo que lo hace distinto

**Escribe como tú, no como ChatGPT.** Aprende tu tono de textos que tú escribiste. Antes de que
cualquier respuesta llegue a un formulario, un revisor la pasa por un filtro: frases de IA ("I'm
passionate about...", "me apasiona"), guiones largos, viñetas donde no van, respuestas infladas.
Si algo suena a robot, se reescribe.

**Escribe solo con tus hechos.** Antes de enviar, un revisor rechaza la respuesta si trae un número,
un título o un nombre (cliente, herramienta, empresa) que no está en tu perfil ni en el aviso. Lo que
no sabe, te lo pregunta y lo anota para la próxima. El revisor es un filtro de texto y se le pueden
pasar cosas: por eso cada respuesta enviada queda guardada y la puedes leer.

**Vende con pruebas, no con adjetivos.** Para cada aviso elige la prueba tuya que le sirve a esa
empresa: el número, el cliente, el proyecto. "Ustedes necesitan X; yo hice Y" le gana a "soy
proactivo y orientado a resultados".

**Busca donde se puede postular de verdad.** Prioriza los avisos con formulario directo, sin crear
cuenta, y descarta los "remote" que en la descripción exigen vivir en EE. UU.

**Tú eliges cuánto mirar.** Por defecto ves cada respuesta tal como se va a enviar y das un sí por
tanda. Si prefieres no mirar, activa el modo automático (`"envio": "automatico"` en tu config): le
dices "postula" y envía solo lo que pasa todos los filtros (calce alto, formulario directo, ninguna
pregunta que te toque a ti, hasta 15 al día). Lo dudoso queda en borrador y al final te muestra qué
mandó, con cada respuesta. En los dos modos, contraseñas, códigos y CAPTCHAs los pones tú, y en
LinkedIn el botón final lo aprietas tú.

**Tus datos viven en tu computador.** Todo lo tuyo está en `~/.doppelganger`. El plugin no tiene
servidor propio ni manda tus datos a nadie. Claude los lee para trabajar, igual que cualquier archivo
que le muestras, y cada formulario recibe lo que tú apruebas enviarle.

## Cómo se ve

```
Tú:      corre el radar
Claude:  412 avisos revisados. 23 calzan contigo, 9 con formulario directo.
         1. Product Manager, Payments · Fintech X · 4.500–6.000 USD · LATAM · Ashby
         2. Implementation Lead · SaaS Y · sin rango (pedirías 3.800) · Remote Americas · Greenhouse
         ...
Tú:      arma una tanda con los 6 primeros
Claude:  [muestra cada aviso, el CV que sube y cada respuesta tal como se enviaría;
          2 preguntas que te tocan a ti: fecha de inicio en el 3, visa en el 5]
Tú:      fecha de inicio: dos semanas. el 5 sácalo. envía
Claude:  5 enviadas (con confirmación de cada sitio), registradas. El 5 quedó descartado.
```

## Instalar

Necesitas [Claude Code](https://claude.com/claude-code) y, para leer LinkedIn y llenar formularios,
la extensión **Claude in Chrome** (planes pagos de Claude). Python 3.9 o más (ya viene en Mac y Linux).

**Desde GitHub** (en Claude Code):

```
/plugin marketplace add Sebyrz/jobless_doppelganger
/plugin install jobless-doppelganger@jobless-doppelganger
```

**Desde el zip:** descomprímelo donde quieras y, en Claude Code:

```
/plugin marketplace add /ruta/a/jobless_doppelganger
/plugin install jobless-doppelganger@jobless-doppelganger
```

Después escribe **"configura mi doppelganger"** y sigue las instrucciones.

## Lo que no hace

- No inventa experiencia, años, títulos ni resultados.
- No envía nada sin que se lo pidas en el chat: en modo normal, un sí por tanda; en automático, tu
  "postula" de esa sesión. Una corrida programada sin ti deja la tanda lista y no envía.
- No automatiza LinkedIn: lee contigo presente y el envío final es tuyo. LinkedIn prohíbe los bots
  y tu cuenta vale más que diez postulaciones.
- No crea cuentas por ti ni escribe tus contraseñas.
- No firma declaraciones en tu nombre ("no usé IA", certificaciones): te las muestra y decides.
- No garantiza entrevistas. Te da más postulaciones buenas por hora, con tu voz.

## Preguntas

**¿Sirve si no soy de tecnología?** Sirve para cualquier rol que se publique en esas bolsas. El
radar trae más avisos de tecnología, producto, operaciones, customer success y diseño porque es lo
que más se contrata remoto, pero los roles los defines tú.

**¿Sirve fuera de Chile o de Latinoamérica?** Sí. País, ciudades, zonas aceptadas, sueldo y moneda
local se configuran en tu perfil.

**¿Cuánto cuesta?** El plugin es gratis. Usa tu plan de Claude.

**¿Y si una empresa nota que usé IA?** Las respuestas salen de tus hechos y tu forma de escribir, y
las apruebas una por una. Si un formulario te pide declarar que no usaste IA, el agente no lo firma
por ti.

**¿Qué pasa con mis datos?** Quedan en `~/.doppelganger` en tu computador. Claude los lee para armar las respuestas. Las búsquedas de avisos van a
las APIs públicas de cada bolsa, sin datos tuyos.

## Para quien quiera mirar el código

```
skills/        empezar · perfil · mejorar-cv · radar · postular (+ guía de formularios)
scripts/       radar, fuentes, criterio, guardia (revisor de respuestas), cola y registro
plantillas/    lo que se copia a ~/.doppelganger la primera vez
tests/         python3 -m unittest discover -s tests
```

Solo biblioteca estándar de Python. Sin dependencias, sin servidores, sin claves de API.

Licencia MIT. Hecho para regalarlo.
