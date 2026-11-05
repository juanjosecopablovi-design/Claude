# Revisión en el navegador

Úselo cuando `rama.py` termina con código 3 (la API no responde desde esa red) y hay un
navegador disponible en el equipo del abogado (Claude en Chrome o el navegador integrado de la
app de escritorio). Desde servidores en la nube no funciona: la API rechaza esas conexiones.

## A. Por lotes (recomendado)

1. Abra https://consultaprocesos.ramajudicial.gov.co/Procesos/Index y espere a que cargue.
2. Obtenga la lista de radicados activos:
   `python3 scripts/rama.py lista-radicados --registro procesos/procesos.csv`
3. Ejecute en la página el contenido de `assets/consulta_navegador.js` y luego
   `await consultarCPNU([...radicados...])`. Con Claude en Chrome, use su herramienta de
   JavaScript sobre la pestaña del portal; si no hay herramienta de JavaScript, pida al abogado
   que lo pegue en la consola (F12 → Consola).
4. El script descarga `consultas_cpnu_AAAA-MM-DD.json` (carpeta de descargas) y devuelve un
   resumen: total, errores, no encontrados y última actuación por radicado. Si la descarga se
   bloquea, el resultado queda en `window.__consultasCPNU`.
5. Procese el archivo:
   `python3 scripts/rama.py revisar --entrada <ruta>/consultas_cpnu_AAAA-MM-DD.json`

## B. Manual, proceso por proceso

1. En `Procesos/Index` elija *Consulta de Procesos por Número de Radicación*.
2. Marque **"Todos los Procesos (consulta completa, menos rápida)"**.
3. Escriba los 23 dígitos (sin guiones) y pulse **Consultar**.
4. Haga clic en el número de radicación del resultado.
5. Lea las pestañas **Datos del Proceso**, **Sujetos Procesales** y **Actuaciones** (fechas de
   actuación, anotación y, si existen, *Fecha inicia Término* / *Fecha finaliza Término*).
6. Use **Volver** para el siguiente radicado.

Registre lo leído con el mismo criterio del informe automático (novedades frente a la revisión
anterior, términos vigentes, inactividad). Sea explícito en que la revisión fue manual.

## Cuidados
- Pausa entre consultas (el script usa 0,8 s) para no saturar el servicio.
- No ingrese credenciales en nombre del abogado. La consulta por número y por nombre es pública.
- Los procesos privados (`esPrivado`) no muestran actuaciones: indíquelo.
