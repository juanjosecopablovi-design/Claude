# Normas verificadas

Regla del abogado: **no inventar jurisprudencia ni citas normativas; citar solo fuentes
verificables y vigentes.** Todo lo que está en este archivo se cotejó el 2026-11-05 con el texto
publicado por la Secretaría General del Senado (http://www.secretariasenado.gov.co/senado/basedoc/).
Cite únicamente estos artículos. Para cualquier otra norma, sentencia o término: diga que debe
verificarse y no lo afirme. Si pasó mucho tiempo desde la fecha de verificación, vuelva a
revisar la vigencia en la misma fuente antes de citar.

## Contenido
1. Cómputo de términos y ejecutoria (CGP)
2. Recursos (CGP)
3. Términos frecuentes (CGP)
4. Desistimiento tácito (CGP)
5. Notificaciones por medios electrónicos (Ley 2213 de 2022; CPACA)
6. Contencioso administrativo (CPACA)
7. Tutela (Decreto 2591 de 1991)
8. Festivos y vacancia
9. Pendiente de verificación (no citar como fundamento)

## 1. Cómputo de términos y ejecutoria — Ley 1564 de 2012 (CGP)
Fuente: `ley_1564_2012_pr004.html` y `ley_1564_2012_pr010.html`.

- **Art. 118 (cómputo de términos):** el término concedido fuera de audiencia corre a partir del
  día siguiente al de la notificación de la providencia que lo concedió; si es común, desde el
  día siguiente a la notificación a todas las partes. Mientras el expediente esté al despacho no
  corren términos. Los términos de meses o años vencen el mismo día del mes o año
  correspondiente (o el último día si ese mes no lo tiene) y, si cae en inhábil, se extienden al
  primer día hábil siguiente. "En los términos de días no se tomarán en cuenta los de vacancia
  judicial ni aquellos en que por cualquier circunstancia permanezca cerrado el juzgado."
- **Art. 302 (ejecutoria):** las providencias proferidas fuera de audiencia quedan ejecutoriadas
  tres (3) días después de notificadas, cuando carecen de recursos o vencieron los términos sin
  interponerlos.

## 2. Recursos — CGP
Fuente: `ley_1564_2012_pr011.html`.

- **Art. 318 (reposición):** contra auto pronunciado fuera de audiencia, por escrito dentro de los
  tres (3) días siguientes al de su notificación.
- **Art. 322 (apelación):** contra providencia dictada fuera de audiencia, en el acto de su
  notificación personal o por escrito dentro de los tres (3) días siguientes a su notificación por
  estado; la apelación de autos se sustenta dentro de los tres (3) días siguientes a su
  notificación o a la del auto que niega la reposición.

## 3. Términos frecuentes — CGP
Fuentes: `ley_1564_2012_pr012.html`, `pr013`, `pr015`.

- **Art. 369:** traslado de la demanda en proceso verbal: veinte (20) días.
- **Art. 391:** contestación en proceso verbal sumario: diez (10) días.
- **Art. 431:** el mandamiento de pago por suma de dinero ordena pagar en cinco (5) días.
- **Art. 442 num. 1:** excepciones de mérito dentro de los diez (10) días siguientes a la
  notificación del mandamiento ejecutivo.

## 4. Desistimiento tácito — CGP art. 317
Fuente: `ley_1564_2012_pr010.html`.

- **Num. 1:** cuando se requiera una carga procesal de quien promovió el trámite, el juez ordena
  cumplirla dentro de los treinta (30) días siguientes (providencia notificada por estado); si no
  se cumple, se tiene por desistida la actuación.
- **Num. 2:** proceso inactivo en la secretaría durante un (1) año en primera o única instancia
  (contado desde el día siguiente a la última notificación, diligencia o actuación) → terminación
  sin requerimiento previo. **Lit. b):** si hay sentencia ejecutoriada a favor del demandante o
  auto que ordena seguir adelante la ejecución, el plazo es de dos (2) años. **Lit. c):**
  cualquier actuación, de oficio o a petición de parte, interrumpe los términos.
- El artículo tiene notas de vigencia y jurisprudencia en la fuente; revíselas antes de
  fundamentar un escrito.

## 5. Notificaciones por medios electrónicos
**Ley 2213 de 2022** (fuente: `ley_2213_2022.html`):
- **Art. 8:** la notificación personal puede hacerse enviando la providencia como mensaje de datos
  a la dirección electrónica suministrada; "se entenderá realizada una vez transcurridos dos días
  hábiles siguientes al envío del mensaje y los términos empezarán a contarse cuando el iniciador
  recepcione acuse de recibo o se pueda por otro medio constatar el acceso del destinatario al
  mensaje".
- **Art. 9:** los estados se fijan virtualmente con inserción de la providencia (salvo medidas
  cautelares, menores o reserva). Parágrafo: si una parte acredita haber enviado por canal
  digital un escrito del que deba correrse traslado, este se entiende realizado a los dos (2) días
  hábiles siguientes al envío, y el término empieza a contarse cuando el iniciador recepcione
  acuse de recibo o se constate el acceso.

**CPACA (Ley 1437 de 2011)** (fuente: `ley_1437_2011_pr004.html`):
- **Art. 199** (mod. art. 48 Ley 2080 de 2021): el traslado o los términos que conceda el auto
  admisorio notificado por mensaje "solo se empezarán a contabilizar a los dos (2) días hábiles
  siguientes al del envío del mensaje y el término respectivo empezará a correr a partir del día
  siguiente".
- **Art. 205** (mod. art. 52 Ley 2080 de 2021): la notificación electrónica de providencias se
  entiende realizada transcurridos dos (2) días hábiles siguientes al envío del mensaje y los
  términos corren a partir del día siguiente al de la notificación.

Uso en `rama.py habiles --mas-dos`: suma los dos días hábiles posteriores al envío y cuenta el
término desde el día hábil siguiente. Advierta que, bajo la Ley 2213 art. 8, el inicio del
término depende además del acuse de recibo o de la constatación de acceso.

## 6. Contencioso administrativo — CPACA
Fuentes: `ley_1437_2011_pr004.html`, `ley_1437_2011_pr005.html`.

- **Art. 172:** traslado de la demanda por treinta (30) días, que corre según los arts. 199 y 200.
- **Art. 244 num. 3** (mod. art. 64 Ley 2080 de 2021): apelación de auto notificado por estado,
  interpuesta y sustentada por escrito dentro de los tres (3) días siguientes (dos en el medio de
  control electoral).
- **Art. 247 num. 1** (mod. art. 67 Ley 2080 de 2021): apelación de sentencia de primera
  instancia dentro de los diez (10) días siguientes a su notificación, también para sentencias
  dictadas en audiencia.

## 7. Tutela — Decreto 2591 de 1991
Fuente: `decreto_2591_1991.html`.
- **Art. 29:** el fallo se dicta dentro de los diez días siguientes a la presentación.
- **Art. 31:** impugnación dentro de los tres días siguientes a la notificación del fallo.

## 8. Festivos y vacancia
- **Ley 2578 de 2026, art. 6** (fuente: `ley_2578_2026.html`, Diario Oficial 53.510 del 2 de junio
  de 2026): declara festivo nacional el Día de Nuestra Señora del Rosario de Chiquinquirá
  (9 de julio) y remite a la Ley 51 de 1983 para el traslado del descanso. `rama.py` lo incluye
  desde 2026 (en 2026 se trasladó al 13 de julio; en 2027 cae el 12 de julio).
- El calendario de festivos de `rama.py` para 2026 y 2027 coincide con el calendario
  "Festivos en Colombia" de Google (comparado el 2026-11-05). Para cambios posteriores use
  `festivos_adicionales` / `festivos_excluidos` en `config.json`.
- **Ley 270 de 1996, art. 146** (mod. art. 74 Ley 2430 de 2024): las vacaciones de funcionarios y
  empleados de la Rama Judicial son colectivas, salvo, entre otros, los juzgados penales
  municipales y los de ejecución de penas y medidas de seguridad (vacaciones individuales). Para
  esos despachos use `--sin-vacancia`.

## 9. Pendiente de verificación (no citar como fundamento)
- **Fechas de la vacancia colectiva** (20 de diciembre a 10 de enero y Semana Santa): `rama.py`
  las aplica por defecto (lunes a miércoles santos; jueves y viernes santos son festivos), pero
  el texto de la norma que las fija no se pudo cotejar en fuente oficial en esta versión
  (fuentes secundarias remiten al Decreto 1660 de 1978). No lo cite sin verificarlo.
- **Código Procesal del Trabajo y de la Seguridad Social:** no se cotejó; no afirme términos
  laborales sin verificar el texto vigente.
- **Ley 906 de 2004 (penal)** y demás códigos: no incluidos.
- Acuerdos del Consejo Superior de la Judicatura sobre suspensión de términos o cierres de
  despachos: agréguelos como `cierres_extra` en `config.json` cuando el abogado los confirme.
