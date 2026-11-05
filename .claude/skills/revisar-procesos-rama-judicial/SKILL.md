---
name: revisar-procesos-rama-judicial
description: Revisa los procesos judiciales del abogado Juan José Chavarriaga Ortiz en la Rama Judicial de Colombia (Consulta de Procesos Nacional Unificada, consultaprocesos.ramajudicial.gov.co) - detecta actuaciones nuevas, términos vigentes, inactividad y pendientes, y entrega un informe priorizado. Úsala siempre que el usuario pida revisar, consultar, monitorear o actualizar sus procesos, radicados o expedientes; pregunte qué hay nuevo en un juzgado o en la Rama Judicial; entregue una lista de radicados (Word, Excel, CSV) para seguimiento; quiera agregar un proceso al registro; o necesite calcular un vencimiento en días hábiles judiciales (festivos y vacancia), aunque no mencione la CPNU ni esta habilidad.
---

# Revisar procesos en la Rama Judicial

Habilidad de seguimiento procesal para el abogado **Juan José Chavarriaga Ortiz**. Consulta la
Consulta de Procesos Nacional Unificada (CPNU), compara con la revisión anterior y produce un
informe que dice qué cambió, qué términos corren y qué hay que hacer.

## Regla de oro: nada de citas inventadas

El abogado exige **no inventar jurisprudencia ni citas normativas; solo fuentes verificables y
vigentes**. Por eso:
- Cite solo lo que está en `references/normas.md` (cotejado con el texto oficial del Senado).
- Si algo no está allí (otra norma, una sentencia, un término laboral o penal), dígalo
  claramente: "debe verificarse", sin afirmar artículo ni número.
- Los datos procesales salen de la CPNU; nunca rellene fechas, autos o despachos que no
  aparezcan en la consulta. Si un dato falta, escriba que falta.

## Archivos

| Archivo | Para qué |
|---|---|
| `scripts/rama.py` | CLI (solo biblioteca estándar de Python 3.8+): `validar`, `consultar`, `buscar-nombre`, `agregar`, `lista-radicados`, `revisar`, `habiles`, `festivos` |
| `assets/consulta_navegador.js` | Consulta por lotes desde el navegador cuando la API no responde por red |
| `assets/registro_inicial.csv` | Procesos del abogado (si viene en el paquete; es privado) |
| `assets/plantilla_procesos.csv`, `assets/plantilla_config.json` | Plantillas vacías |
| `references/fuentes.md` | Portales, API, estructura del radicado, otras plataformas |
| `references/normas.md` | Únicas normas citables y lo pendiente de verificar |
| `references/navegador.md` | Procedimiento en el navegador (lotes y manual) |

## Datos de trabajo

Ejecute `scripts/rama.py` con la ruta completa de esta habilidad, desde el directorio de trabajo.
Los datos viven en una carpeta `procesos/` de ese directorio (o la que indique `PROCESOS_DIR`),
no dentro de la habilidad, porque la línea base se actualiza en cada revisión:

```
procesos/
├── procesos.csv     registro de procesos (fuente de verdad del abogado)
├── config.json      abogado, umbral de inactividad, cierres y festivos extra
├── estado/          última consulta de cada radicado (línea base para detectar novedades)
└── informes/        revision_AAAA-MM-DD_HHMMSS.md y .json
```

Si `procesos/procesos.csv` no existe: cópielo de `assets/registro_inicial.csv` si está; si no,
créelo desde la plantilla o desde el documento que entregue el abogado. Haga lo mismo con
`config.json`. Esta información es confidencial (secreto profesional): no la suba a
repositorios públicos ni la comparta fuera de la conversación.

Columnas del registro: `radicado, proceso, cliente, calidad, tipo_proceso, despacho,
plataforma, estado_interno, pendiente, notas`.
- `plataforma`: `CPNU` (por defecto), `SAMAI`, `TYBA`, `PROCURADURIA` u `OTRA`. Solo `CPNU` se
  consulta automáticamente; el resto aparece en el informe con su enlace.
- `estado_interno`: `activo` o `archivado`/`terminado` (estos se omiten).
- `pendiente`: la gestión que el abogado tiene por hacer o esperar (p. ej. "Admisión",
  "Allegar avalúo"). Es la clave para que el informe sea útil.

### Importar una lista del abogado
Cuando entregue un Word/Excel/CSV (como su tabla RADICADO | PROCESO | PENDIENTES): extraiga
cada radicado (una celda puede traer varios), quite guiones y espacios, valide los 23 dígitos
con `rama.py validar`, y mapee PROCESO → `proceso`, PENDIENTES → `pendiente`. Identificadores
que no son radicados judiciales (p. ej. un radicado `E-AAAA-NNNNNN` de la Procuraduría) van con su
plataforma. Use `rama.py agregar` o escriba el CSV; muestre al abogado cuántos importó y cuáles
no pudo validar.

## Flujo de revisión

1. **Preparar.** Ubique el registro y lea `procesos/config.json` si existe.
2. **Consultar por API (vía principal).**
   ```bash
   python3 scripts/rama.py revisar --registro procesos/procesos.csv
   ```
   Opciones: `--solo RAD1 RAD2` (algunos procesos), `--desde AAAA-MM-DD` (tratar como novedad
   todo lo posterior a esa fecha, útil en la primera revisión), `--no-guardar` (no mover la línea
   base). La primera vez solo guarda la línea base y muestra las 5 últimas actuaciones.
3. **Si termina con código 3** (la API no responde): la CPNU rechaza conexiones desde la nube y
   desde fuera de Colombia. Entonces:
   - Si hay navegador en el equipo del abogado (Claude en Chrome, navegador integrado), siga
     `references/navegador.md`: entrar por https://consultaprocesos.ramajudicial.gov.co/Procesos/Index,
     ejecutar `assets/consulta_navegador.js` y luego `rama.py revisar --entrada <archivo.json>`.
   - Si no, dígale al abogado que la consulta debe ejecutarse desde su computador en Colombia
     (Claude Code o la app de escritorio) y entréguele el comando exacto. No invente resultados.
4. **Analizar el informe** (`procesos/informes/revision_*.md`) y redactar la respuesta.

## Cómo redactar la respuesta al abogado

Empiece por lo urgente. Estructura sugerida:

1. **Urgente** — términos vigentes registrados por el despacho (fecha de vencimiento y días
   hábiles restantes) y novedades de prioridad ALTA (sentencias, inadmisiones, requerimientos,
   traslados, fijación de audiencias, mandamientos, desistimiento).
2. **Cruce con pendientes** — para cada proceso con `pendiente`, diga si la CPNU muestra algo que
   lo resuelva o lo afecte. Ejemplos: pendiente "Admisión" y aparece "auto admite" → avance;
   pendiente "Reparto de la apelación" y no hay actuación nueva → sigue pendiente;
   pendiente "Allegar poder" y aparece un requerimiento → urgente.
3. **Alertas** — inactividad prolongada (riesgo de desistimiento tácito, CGP art. 317, solo en
   procesos regidos por el CGP), procesos no encontrados (revisar número o plataforma),
   procesos privados.
4. **Sin novedades** — lista corta.
5. **Otras plataformas** — Procuraduría, SAMAI, TYBA: con enlace, recordando que no se
   consultaron automáticamente.

Para cada término que mencione, calcúlelo con `rama.py habiles` y diga los supuestos (fecha de
notificación, si fue por estado o por mensaje de datos). Si la CPNU trae *Fecha finaliza
Término*, priorice esa fecha y aclare que la registró el despacho. Cierre recordando que el
informe es orientativo y que la notificación oficial es la del despacho.

No modifique el registro (pendientes, estado) sin que el abogado lo confirme. Si pide agendar
vencimientos o audiencias en Google Calendar, cree los eventos solo con su confirmación.

## Otras tareas

- **Validar o desglosar un radicado:** `rama.py validar 11001310300120240000100`
  (`--decodificar` traduce los códigos con las listas oficiales; requiere acceso a la API).
- **Consultar un proceso puntual:** `rama.py consultar <radicado>` (JSON con detalle, sujetos y
  actuaciones).
- **Buscar procesos por nombre** (cliente, contraparte o el propio abogado):
  `rama.py buscar-nombre "JUAN JOSE CHAVARRIAGA ORTIZ" --tipo nat`. Devuelve procesos donde el
  nombre figura como sujeto procesal; un apoderado no siempre figura así, por lo que el registro
  propio sigue siendo la fuente principal. Proponga agregar los hallazgos, no los agregue solo.
- **Calcular un vencimiento:**
  `rama.py habiles --desde 2026-11-05 --dias 3` (notificado por estado el 5/nov)
  `rama.py habiles --desde 2026-11-05 --dias 20 --mas-dos` (mensaje de datos enviado el 5/nov)
  `rama.py habiles --desde 2026-01-31 --meses 1`
  `--sin-vacancia` para despachos con vacaciones individuales. Las fechas de cierre o suspensión
  de términos que el abogado confirme van en `config.json` → `cierres_extra`.
- **Festivos de un año:** `rama.py festivos 2027`.

## Interpretación de la CPNU (lo que suele confundir)

- "Fijación estado" es la publicación del estado; la providencia está en la anotación o en el
  estado electrónico del despacho: léala antes de concluir.
- Mientras el expediente está "al despacho" no corren términos (CGP art. 118), salvo
  excepciones del mismo artículo.
- *Fecha inicia/finaliza Término* solo aparece si el despacho la registró; su ausencia no
  significa que no corra un término.
- Un radicado puede tener varios registros (`idProceso`): revíselos todos.
- Radicados con terminación distinta de `00` (p. ej. `...01`) suelen corresponder a una
  actuación posterior (como una apelación); consúltelos por separado.
