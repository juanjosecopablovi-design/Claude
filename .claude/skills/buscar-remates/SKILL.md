---
name: buscar-remates
description: Busca remates judiciales (inmuebles y vehículos) publicados en Publicaciones Procesales de la Rama Judicial de Colombia para Medellín (incluye Santa Elena), Rionegro, Sabaneta, Barbosa, Envigado, La Estrella y Puerto Boyacá; descarga los autos que fijan fecha, extrae fecha, hora, radicado, bien y avalúo, y arma la tabla de remates vigentes. También busca un proceso concreto (mandamiento de pago, seguir adelante la ejecución, estados, actas) dentro de las publicaciones de un juzgado o en su micrositio. Usar cuando el usuario pida buscar remates, carteles de remate, autos que fijan fecha de remate, remates vigentes o actuaciones de un proceso ejecutivo.
---

# Buscar remates

Herramientas para el despacho de asesoría a inversionistas en remates judiciales.
Fuente: Publicaciones Procesales (`publicacionesprocesales.ramajudicial.gov.co`), que solo tiene
publicaciones desde el **14 de mayo de 2024**. Para fechas anteriores use el micrositio del juzgado.

## Regla de oro

- No inventar normas, jurisprudencia ni datos del proceso. Citar solo fuentes verificables y vigentes
  (ver `references/normas.md`, con enlaces oficiales). Si algo no se pudo verificar, decirlo.
- Los datos extraídos automáticamente (fecha, hora, avalúo, matrícula) son una ayuda:
  **confirmar siempre contra el PDF del auto** antes de asesorar a un cliente.
- Nombres de demandantes y demandados son datos personales: no usarlos en publicidad.

## Preparación (una vez por sesión)

```bash
export REMATES_WORK=~/.cache/buscar-remates   # o el scratchpad de la sesión
bash .claude/skills/buscar-remates/scripts/setup.sh
```

Instala `playwright-core` en `$REMATES_WORK` y `pypdfium2`. Usa Chromium en `/opt/pw-browsers/chromium`
o en `CHROME_PATH`.

## 1. Remates vigentes en las ciudades configuradas

```bash
S=.claude/skills/buscar-remates/scripts
node $S/buscar_remates.js --ciudades todas --desde 2026-05-01 --hasta 2026-11-05 --out DIR
python3 -I $S/analizar_autos.py --out DIR --hoy 2026-11-05
```

- `--ciudades`: `medellin,rionegro,sabaneta,barbosa,envigado,la-estrella,puerto-boyaca` o `todas`.
  **Santa Elena** es corregimiento de Medellín: la cubren los juzgados de Medellín.
- `--tipos "Civil Municipal,Promiscuo Municipal"` limita por clase de juzgado.
- `--despachos 050013403001,... --depto 05` busca despachos concretos (por ejemplo, un circuito
  con sede en otro municipio).
- Los scripts paran a los 8 minutos (`--max-min`) y guardan su avance: si imprimen `INCOMPLETO`,
  **vuelva a ejecutar el mismo comando**. Para rangos largos, ejecute por tramos de 1–2 meses.

Resultados en `DIR/`:
- `vigentes.md`: tabla de remates con fecha ≥ hoy (el auto más reciente de cada radicado), actas de
  remate publicadas (adjudicado/desierto) y publicaciones que hay que revisar a mano.
- `remates.csv` y `autos.json`: todos los documentos con los datos extraídos.
- `autos/`: los PDF descargados.

Cobertura de juzgados (`config/despachos.json`, 113 despachos):
- Medellín: civiles del circuito, civiles del circuito de ejecución (y su oficina de apoyo), civiles
  municipales, civiles municipales de ejecución (y su oficina de apoyo), pequeñas causas.
- En los demás municipios no hay juzgados de ejecución: rematan los mismos juzgados que conocen del
  ejecutivo (civiles del circuito, civiles municipales, promiscuos municipales, pequeñas causas).
- Rionegro y Envigado: también sus centros de servicios (Rionegro publica allí los remates de sus
  juzgados).
- Para agregar una ciudad: editar `CIUDADES` en `scripts/actualizar_despachos.js` y ejecutarlo.

Al presentar resultados al usuario:
1. Ordenar por fecha de remate y dar el enlace al PDF del auto y al expediente (SharePoint) cuando exista.
2. Señalar las filas con nota ("memorial de parte", "resumen de la publicación"): la fecha no viene
   del auto y debe confirmarse.
3. Listar las publicaciones sin PDF (solo expediente) para revisión manual.
4. Ofrecer el análisis de riesgos del bien con `references/checklist_riesgos.md`.

## 2. Buscar un proceso concreto (mandamiento, sentencia, estados, actas)

```bash
node $S/buscar_proceso.js --depto 50 --despacho 505733189002 --desde 2026-01-01 --hasta 2026-11-05 --out DIR2
python3 -I $S/grep_radicado.py --out DIR2 --radicado 50573318900220180003700 --palabras "nombre del predio"
```

- `--despacho` son los 12 primeros dígitos del radicado (municipio DANE 5 + entidad/especialidad 4 +
  número 3). `--depto` son los 2 primeros.
- `buscar_proceso.js` lista todas las publicaciones del juzgado (estados, autos, remates, traslados…);
  `--categorias "Estados,Remates"` filtra por tipo.
- `grep_radicado.py` descarga los PDF y busca el radicado en sus variantes (`2018-00037`, con o sin
  espacios) y las palabras dadas. Informe en `DIR2/hallazgos.md`. Los PDF escaneados no tienen texto:
  se listan para revisión manual.
- Antes de mayo de 2024, o si el juzgado publica en su página: 
  `node $S/micrositio.js --sitio <slug-del-micrositio> --out DIR3 [--filtro "2019|estados"]` y luego
  `grep_radicado.py --out DIR3 ...`. El slug es la parte de `ramajudicial.gov.co/web/<slug>/inicio`.
  Si el sitio responde 403 o "Service unavailable", reintentar más tarde (el script lo deja en cola).
- Consulta de Procesos (`consultaprocesos.ramajudicial.gov.co`) suele rechazar conexiones automáticas;
  si se necesita, pedir al usuario que la consulte o que aporte el expediente.

## Códigos útiles

Entidad/especialidad (dígitos 6–9 del despacho): 3103/3112 Civil del Circuito · 3403 Civil del Circuito
de Ejecución · 3189 Promiscuo del Circuito · 4003 Civil Municipal · 4303 Civil Municipal de Ejecución ·
4189 Pequeñas Causas y Competencia Múltiple · 4089 Promiscuo Municipal.

Departamentos: 05 Antioquia · 15 Boyacá · 50 Meta. La categoría Remates del portal es `idStructure=6098997`.

## Referencias

- `references/normas.md`: normas del remate verificadas, con enlace oficial.
- `references/checklist_riesgos.md`: lista de revisión del bien antes de recomendar una postura.
