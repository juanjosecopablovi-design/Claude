# Fuentes oficiales de consulta

Verificado el 2026-11-05 contra los propios portales (código del portal CPNU y respuestas HTTP).
Si algo deja de funcionar, vuelva a verificar antes de suponer un cambio.

## Contenido
1. CPNU (Consulta de Procesos Nacional Unificada)
2. API de la CPNU (la usa `scripts/rama.py`)
3. Número de radicación (23 dígitos)
4. Otras plataformas
5. Limitaciones conocidas

## 1. CPNU — portal web

- **Entrada indicada por el abogado:** https://consultaprocesos.ramajudicial.gov.co/Procesos/Index
- Opciones del menú (títulos tal como aparecen en el portal):
  - *Consulta de Procesos por Número de Radicación* → `/Procesos/NumeroRadicacion`
  - *Consulta de Procesos por Nombre o Razón Social* → `/Procesos/NombreRazonSocial`
    (tipo de persona: Natural o Jurídica)
  - *Consulta de Procesos Construir Número de Radicación* → `/Procesos/ConstruirNumeroRadicacion`
    (arma el número eligiendo departamento, ciudad, entidad, especialidad y despacho)
  - *Consulta de Procesos por Juez Magistrado y Clase de Proceso*
  - *Consulta por identificación (CC / Nit / CE)* — consulta privada, exige autenticación.
  - *Seguimiento de procesos* (usuarios registrados): permite *Descargar plantilla* y
    *Cargar listado* en Excel para seguir varios procesos. Es complementaria a esta habilidad.
- Filtro obligatorio en las búsquedas:
  - "Procesos con Actuaciones Recientes (últimos 30 días)"
  - "Todos los Procesos (consulta completa, menos rápida)" ← use este para revisar.
- Pestañas del detalle de un proceso: **Datos del Proceso**, **Sujetos Procesales**,
  **Documentos del Proceso**, **Actuaciones**.
- En *Actuaciones* las columnas son: Fecha de Actuación, Actuación, Anotación,
  Fecha inicia Término, Fecha finaliza Término, Fecha de Registro.
  Las fechas de término solo aparecen cuando el despacho las registra.

## 2. API de la CPNU

Base: `https://consultaprocesos.ramajudicial.gov.co:448/api/v2` (puerto 448).
Son los mismos servicios que llama el portal; no requieren autenticación para procesos públicos.

| Uso | Ruta |
|---|---|
| Buscar por radicado | `GET /Procesos/Consulta/NumeroRadicacion?numero={23 dígitos}&SoloActivos=false&pagina=1` |
| Buscar por nombre | `GET /Procesos/Consulta/NombreRazonSocial?nombre={texto}&tipoPersona=nat\|jur&SoloActivos=false&codificacionDespacho=&pagina=1` |
| Detalle | `GET /Proceso/Detalle/{idProceso}` |
| Actuaciones | `GET /Proceso/Actuaciones/{idProceso}?pagina=1` (admite `fechaIni`, `fechaFin`) |
| Sujetos | `GET /Proceso/Sujetos/{idProceso}?pagina=1` |
| Documentos | `GET /Proceso/Documentos/{idProceso}` · `GET /Proceso/DocumentosActuacion/{idRegActuacion}` |
| Listas para decodificar el radicado | `/Lista/Departamentos`, `/Lista/Ciudades/{2}`, `/Lista/Entidades/{5}`, `/Lista/Especialidades/{7}`, `/Lista/Despachos/{9}` |

Campos útiles:
- Búsqueda: `idProceso`, `llaveProceso`, `fechaProceso`, `fechaUltimaActuacion`, `despacho`,
  `departamento`, `sujetosProcesales`, `esPrivado`, `paginacion.cantidadPaginas`.
- Detalle: `despacho`, `ponente`, `tipoProceso`, `claseProceso`, `subclaseProceso`, `recurso`,
  `ubicacion`, `contenidoRadicacion`, `fechaConsulta`, `ultimaActualizacion`.
- Actuación: `idRegActuacion`, `consActuacion`, `fechaActuacion`, `actuacion`, `anotacion`,
  `fechaInicial`, `fechaFinal`, `fechaRegistro`, `conDocumentos`.

Un mismo radicado puede devolver varios registros (`idProceso` distintos), por ejemplo por
migración entre sistemas de gestión. Revise todos.

## 3. Número de radicación

23 dígitos, en este orden (la CPNU lo construye por prefijos con las listas oficiales):

| Posición | Dígitos | Contenido |
|---|---|---|
| 1–5 | 5 | Código DANE: departamento (2) + municipio (3) |
| 6–7 | 2 | Entidad / corporación |
| 8–9 | 2 | Especialidad |
| 10–12 | 3 | Número del despacho |
| 13–16 | 4 | Año de radicación |
| 17–21 | 5 | Consecutivo |
| 22–23 | 2 | Recurso / instancia (`00` en el radicado original; otros valores identifican actuaciones posteriores, p. ej. una apelación) |

Para saber qué despacho corresponde a cada código, use `rama.py validar --decodificar`
(consulta las listas oficiales) en lugar de interpretar los códigos de memoria.

## 4. Otras plataformas

| Plataforma | Cuándo | Enlace |
|---|---|---|
| SAMAI | Jurisdicción de lo contencioso administrativo (Consejo de Estado, tribunales y juzgados administrativos) | https://samai.consejodeestado.gov.co/ |
| TYBA (Justicia XXI Web) | Despachos que publican en ese sistema | https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx |
| Procuraduría — Sede electrónica | Radicados tipo `E-AAAA-NNNNNN` (p. ej. conciliación extrajudicial) | https://www.procuraduria.gov.co/SedeElectronica/ |
| Corte Constitucional — Secretaría | Tutelas en revisión | https://www.corteconstitucional.gov.co/secretaria/ |

Estas plataformas no tienen cliente en `rama.py`: márquelas en la columna `plataforma` del
registro y consúltelas en el navegador.

## 5. Limitaciones conocidas

- La API (puerto 448) **rechaza conexiones desde servidores en la nube y fuera de Colombia**
  (comprobado el 2026-11-05: reinicio de conexión tanto con Python como con un navegador
  Chromium desde un centro de datos). El portal en el puerto 443 sí carga, pero sin la API no
  muestra resultados. Ejecute la revisión desde un equipo en Colombia.
- Los procesos con reserva (`esPrivado`) solo muestran el resumen.
- La CPNU es informativa: la notificación oficial es la que hace el despacho (estado
  electrónico, notificación personal o por mensaje de datos).
