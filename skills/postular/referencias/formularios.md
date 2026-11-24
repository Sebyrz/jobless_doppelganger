# Cómo se llena cada formulario

Aprendido llenando formularios reales con Claude in Chrome. Úsalo como guía, no como verdad:
los sitios cambian. Si algo no calza, mira la página (`read_page`, `find`, captura) antes de insistir.

## General

- **Un formulario a la vez.** Las tandas de acciones del navegador (`browser_batch`) se cortan si son
  largas: de 6 a 8 acciones como máximo. Si la conexión se cae, revisa el estado de la página antes de
  repetir nada (puede que el envío sí haya salido).
- **Cada página nueva pierde las funciones JS** que hayas definido: vuelve a definirlas.
- **No devuelvas URLs ni valores con datos personales** desde `javascript_tool` (la herramienta puede
  bloquear el resultado si trae tokens de la URL): devuelve largos, `true/false` o conteos.
- **CV:** sube el PDF con `file_upload` sobre el `input[type=file]` (búscalo con `find "resume"` o
  `find "attach"`). Usa el CV que calce con el rol si hay varios en `~/.postula/cv/`.
- **Contacto** (nombre, correo, teléfono, LinkedIn, ciudad): de `perfil.md`. Si falta, se pregunta.
- **Preguntas demográficas** (género, etnia, discapacidad, veterano): en blanco si son opcionales;
  si son obligatorias, "Prefiero no responder" / "Decline to self-identify".
- **Declaraciones** ("no usé IA", "certifico que...", términos y privacidad obligatorios): las acepta o
  firma la persona. Muéstraselas y espera su sí para esa declaración.
- **Éxito:** confirma siempre con algo que la página muestre (URL o texto). Sin confirmación, no se
  marca como enviada.

Helper para campos de texto en React (Greenhouse, Ashby y otros ignoran `value=` a secas):

```js
window.__fill = (el, v) => {
  const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
  ['input', 'change', 'blur'].forEach(t => el.dispatchEvent(new Event(t, { bubbles: true })));
};
// llena por el comienzo del texto del <label for="...">; devuelve qué encontró
window.__porLabel = (M) => Object.fromEntries(Object.entries(M).map(([k, v]) => {
  const lab = [...document.querySelectorAll('label[for]')]
    .find(l => l.textContent.trim().toLowerCase().startsWith(k.toLowerCase()));
  const el = lab && document.getElementById(lab.htmlFor);
  if (el) __fill(el, v);
  return [k, !!el];
}));
```

## GetOnBoard

Con la sesión de la persona abierta en Chrome.

1. Abre el aviso. En vez de hacer click en "Apply now"/"Postular", lee el `href` de ese botón y
   **navega a esa URL** (el click a veces no avanza).
2. **Paso 1:** textos guardados en su perfil de GetOnBoard. No los toques. Si "Next" por referencia no
   avanza, click por coordenadas.
3. **Paso 2:** CV (el predeterminado de su perfil, o el que calce), **sueldo bruto mensual en USD en
   múltiplos de 50** (`criterio.pedir()` ya lo redondea así) y "¿Por qué te interesa?".
4. **Paso 3:** preguntas propias de la empresa; cada pregunta está en el `<div>` anterior a su textarea.
   Se contestan con la verdad aunque sea "no". **Quedan bloqueadas al enviar**: revísalas bien.
5. **Paso 4:** vista previa y "Send application now" / "Enviar postulación".
6. Éxito: en su lista de postulaciones la fila dice SENT / Enviada. Después de enviar se puede editar
   el paso 2 (CV, sueldo, por qué), no el 3.

## Greenhouse

- Si el sitio propio de la empresa falla (rechaza el teléfono, carga mal), usa el formulario embebido:
  `https://job-boards.greenhouse.io/embed/job_app?for=<tablero>&token=<id>`
  (en Europa: `https://job-boards.eu.greenhouse.io/<tablero>/jobs/<id>`).
- Preguntas antes de abrir: `python3 "$S/directo.py" "Empresa" "Título"` (vienen de la API).
- Texto: `__porLabel({"First Name": ..., "Last Name": ..., "Email": ..., "Phone": ..., "LinkedIn": ...})`.
- Listas desplegables con búsqueda (país, `#candidate-location`, `question_<id>`): click o foco en el
  campo, escribir el valor, esperar la opción y Enter (o click en la opción).
- Éxito: la URL pasa a contener `confirmation`, o la página dice "Thank you for applying".

## Ashby

- URL del formulario: `https://jobs.ashbyhq.com/<tablero>/<id>/application`.
- Preguntas antes de abrir: `python3 "$S/ashby_preguntas.py" <tablero> <id>`.
- El texto del label está en el `<label>` padre del campo (no siempre usa `for`).
- Sí/No son **botones**, no radios: click en el botón.
- Ubicación: lista con búsqueda; si su ciudad no está, su país.
- Si "Submit Application" por referencia no hace nada, click por coordenadas en el botón.
- Éxito: "Your application was successfully submitted" / "successfully submitted".

## Lever

- URL: `https://jobs.lever.co/<tablero>/<id>/apply`.
- Campos por `name` (`name`, `email`, `phone`, `urls[LinkedIn]`, `cards[...]`).
- Ubicación: triple click en el campo, escribir, y **click en la opción del menú** (Enter no basta).
- Éxito: la URL termina en `/thanks`.

## Workable

- URL: `https://apply.workable.com/<cuenta>/j/<shortcode>/apply/`.
- Campos por `name` (`firstname`, `lastname`, `email`, `phone`, preguntas `QA_<n>`).
- Radios: click en la referencia del **label**, no del input.
- Listas con búsqueda: abrir el menú y click en la opción.
- Las preguntas propias no salen por API: léelas en la página antes de llenar.
- Éxito: "submitted successfully".
- No sondees muchas cuentas de Workable seguidas: bloquea la IP un rato (429).

## Manatal (careers-page.com) y otros

Mismo método: lee la página, llena por label o por `name`, sube el CV, confirma el éxito. Si pide crear
cuenta, para y pregúntale a la persona.

## LinkedIn (Easy Apply)

- **Solo con la persona presente** y como máximo `linkedin_max_dia` al día (10 por defecto).
- Puedes llenar los pasos del modal con sus datos y tus respuestas ya aprobadas. **El botón final
  "Enviar solicitud" / "Submit application" lo aprieta ella.**
- Nada de scripts, scraping, ni abrir decenas de avisos seguidos: su cuenta está en juego.
- Si el aviso manda al sitio de la empresa, busca el formulario directo con `directo.py`.

## Señales para parar y preguntar

- Pide crear cuenta, video (Loom), certificado de notas, prueba técnica con plazo, o datos que no
  están en `perfil.md` (visa, fecha de inicio, sueldo actual, documento de identidad).
- Pide declarar algo en su nombre.
- El aviso exige vivir en otro país o ir a una oficina, y ella dijo solo remoto.
- El formulario muestra un error que no entiendes después de un reintento.
