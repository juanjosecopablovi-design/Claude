#!/usr/bin/env python3
"""Consulta y seguimiento de procesos en la Rama Judicial de Colombia.

Fuente de datos: API pública de la Consulta de Procesos Nacional Unificada (CPNU),
https://consultaprocesos.ramajudicial.gov.co (los endpoints son los mismos que usa
el portal web). Solo usa la biblioteca estándar de Python 3.8+.

Subcomandos:
  validar       Valida y desglosa un número de radicación de 23 dígitos.
  consultar     Consulta un radicado (detalle, sujetos y actuaciones).
  buscar-nombre Busca procesos por nombre o razón social de un sujeto procesal.
  agregar       Agrega un proceso al registro (procesos.csv).
  revisar       Revisa todos los procesos activos del registro y genera un informe.
  habiles       Calcula vencimientos en días hábiles (festivos y vacancia judicial).
  festivos      Lista los festivos nacionales de un año.

Ejecute `python3 rama.py <subcomando> -h` para ver las opciones.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import socket
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"
PORTAL = "https://consultaprocesos.ramajudicial.gov.co"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; revision-procesos/1.0)",
    "Origin": PORTAL,
    "Referer": PORTAL + "/",
}
PAUSA_SEG = 0.8          # pausa mínima entre llamadas, para no saturar el servicio
MAX_PAGINAS = 60         # tope de seguridad al paginar
ESTADOS_INACTIVOS = {"archivado", "terminado", "inactivo", "cerrado"}
COLUMNAS_REGISTRO = ["radicado", "proceso", "cliente", "calidad", "tipo_proceso", "despacho",
                     "plataforma", "estado_interno", "pendiente", "notas"]
PLATAFORMAS_MANUALES = {
    "samai": "https://samai.consejodeestado.gov.co/",
    "tyba": "https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx",
    "procuraduria": "https://www.procuraduria.gov.co/SedeElectronica/",
}

# --------------------------------------------------------------------------- #
# Utilidades generales
# --------------------------------------------------------------------------- #


def hoy():
    return dt.date.today()


def sin_tildes(texto):
    texto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower()


def fecha(valor):
    """Convierte '2024-03-05T00:00:00' (u otros formatos ISO) en date; None si no aplica."""
    if not valor:
        return None
    if isinstance(valor, dt.date):
        return valor
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(valor))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def imprimir_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------- #
# Número de radicación
# --------------------------------------------------------------------------- #

SEGMENTOS = [  # (nombre, longitud)
    ("departamento", 2), ("municipio", 3), ("entidad", 2), ("especialidad", 2),
    ("despacho", 3), ("anio", 4), ("consecutivo", 5), ("recurso", 2),
]


def normalizar_radicado(texto):
    return re.sub(r"\D", "", str(texto or ""))


def desglosar_radicado(texto):
    n = normalizar_radicado(texto)
    if len(n) != 23:
        raise ValueError(
            f"El radicado debe tener 23 dígitos; se recibieron {len(n)} ('{texto}').")
    partes, i = {}, 0
    for nombre, largo in SEGMENTOS:
        partes[nombre] = n[i:i + largo]
        i += largo
    partes["codigo_dane"] = partes["departamento"] + partes["municipio"]
    partes["codigo_despacho_completo"] = n[:12]
    partes["radicado"] = n
    partes["formateado"] = "-".join([
        partes["codigo_dane"], partes["entidad"], partes["especialidad"],
        partes["despacho"], partes["anio"], partes["consecutivo"], partes["recurso"]])
    advertencias = []
    anio = int(partes["anio"])
    if anio < 1950 or anio > hoy().year + 1:
        advertencias.append(f"Año de radicación inusual: {anio}.")
    partes["advertencias"] = advertencias
    return partes


# --------------------------------------------------------------------------- #
# Cliente HTTP de la CPNU
# --------------------------------------------------------------------------- #


class CPNUNoDisponible(Exception):
    """La API no respondió (red bloqueada, fuera de Colombia, caída del servicio)."""


class CPNUError(Exception):
    """La API respondió con un error."""


_ultima_llamada = [0.0]


def api_get(ruta, params=None, intentos=3):
    url = API + ruta
    if params:
        url += "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    espera = PAUSA_SEG - (time.time() - _ultima_llamada[0])
    if espera > 0:
        time.sleep(espera)
    ultimo_error = None
    for intento in range(intentos):
        _ultima_llamada[0] = time.time()
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as resp:
                cuerpo = resp.read().decode("utf-8", "replace")
                return json.loads(cuerpo) if cuerpo.strip() else None
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", "replace")[:600]
            mensaje = cuerpo
            try:
                j = json.loads(cuerpo)
                mensaje = j.get("Message") or j.get("message") or cuerpo
            except (ValueError, AttributeError):
                pass
            if e.code in (429, 500, 502, 503, 504) and intento < intentos - 1:
                time.sleep(2 ** (intento + 1))
                continue
            raise CPNUError(f"HTTP {e.code} en {ruta}: {mensaje}")
        except (urllib.error.URLError, ConnectionError, socket.timeout, ssl.SSLError,
                TimeoutError, OSError) as e:
            ultimo_error = e
            if intento < intentos - 1:
                time.sleep(2 ** (intento + 1))
                continue
    raise CPNUNoDisponible(
        "La API de la CPNU no respondió desde esta red "
        f"({type(ultimo_error).__name__}: {ultimo_error}). El servicio suele rechazar "
        "conexiones desde fuera de Colombia o desde centros de datos. Ejecute la "
        "habilidad desde un equipo en Colombia o use el modo navegador "
        f"(entrar por {PORTAL}/Procesos/Index; ver references/navegador.md).")


def _paginar(ruta, params, clave):
    """Recorre todas las páginas de un endpoint paginado y devuelve la lista `clave`."""
    params = dict(params or {})
    elementos, pagina = [], 1
    while pagina <= MAX_PAGINAS:
        params["pagina"] = pagina
        datos = api_get(ruta, params) or {}
        elementos.extend(datos.get(clave) or [])
        pag = datos.get("paginacion") or {}
        total = pag.get("cantidadPaginas") or 1
        if pagina >= total:
            break
        pagina += 1
    return elementos


def buscar_por_radicado(numero, solo_recientes=False):
    return _paginar("/Procesos/Consulta/NumeroRadicacion",
                    {"numero": numero, "SoloActivos": str(solo_recientes).lower()},
                    "procesos")


def buscar_por_nombre(nombre, tipo_persona="nat", solo_recientes=False,
                      codificacion_despacho=""):
    return _paginar("/Procesos/Consulta/NombreRazonSocial",
                    {"nombre": nombre, "tipoPersona": tipo_persona,
                     "SoloActivos": str(solo_recientes).lower(),
                     "codificacionDespacho": codificacion_despacho},
                    "procesos")


def detalle(id_proceso):
    return api_get(f"/Proceso/Detalle/{id_proceso}") or {}


def actuaciones(id_proceso):
    return _paginar(f"/Proceso/Actuaciones/{id_proceso}", {}, "actuaciones")


def sujetos(id_proceso):
    return _paginar(f"/Proceso/Sujetos/{id_proceso}", {}, "sujetos")


def consultar(numero, con_sujetos=True):
    """Consulta completa de un radicado. Un mismo radicado puede tener varias
    'instancias' (registros con distinto idProceso, p. ej. por segunda instancia o
    por migración entre sistemas)."""
    numero = normalizar_radicado(numero)
    procesos = buscar_por_radicado(numero)
    resultado = {"radicado": numero, "consultado_en": dt.datetime.now().isoformat(
        timespec="seconds"), "fuente": API, "instancias": []}
    for p in procesos:
        inst = {"resumen": p, "privado": bool(p.get("esPrivado"))}
        idp = p.get("idProceso")
        if idp and not inst["privado"]:
            inst["detalle"] = detalle(idp)
            inst["actuaciones"] = actuaciones(idp)
            if con_sujetos:
                inst["sujetos"] = sujetos(idp)
        resultado["instancias"].append(inst)
    return resultado


def decodificar_radicado(numero):
    """Traduce los códigos del radicado a nombres con las listas oficiales de la CPNU."""
    p = desglosar_radicado(numero)
    n = p["radicado"]
    pasos = [("departamento", "/Lista/Departamentos", n[:2]),
             ("municipio", f"/Lista/Ciudades/{n[:2]}", n[:5]),
             ("entidad", f"/Lista/Entidades/{n[:5]}", n[:7]),
             ("especialidad", f"/Lista/Especialidades/{n[:7]}", n[:9]),
             ("despacho", f"/Lista/Despachos/{n[:9]}", n[:12])]
    nombres = {}
    for campo, ruta, prefijo in pasos:
        try:
            lista = api_get(ruta) or []
        except CPNUError as e:
            nombres[campo] = f"(error: {e})"
            continue
        segmento = p[campo]
        hallado = None
        for item in lista:
            cod = str(item.get("codigo", ""))
            if cod == prefijo or cod == segmento or cod.endswith(segmento) and len(cod) <= len(prefijo):
                hallado = item.get("nombre")
                if cod == prefijo:
                    break
        nombres[campo] = hallado or "(no encontrado en la lista oficial)"
    p["nombres"] = nombres
    return p


# --------------------------------------------------------------------------- #
# Festivos y días hábiles
# --------------------------------------------------------------------------- #


def pascua(anio):
    """Domingo de Pascua (algoritmo gregoriano anónimo)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(anio, mes, dia)


def _lunes_siguiente(d):
    return d + dt.timedelta(days=(7 - d.weekday()) % 7)


def festivos(anio, config=None):
    """Festivos nacionales de Colombia. Los trasladables se mueven al lunes siguiente
    (Ley 51 de 1983). Incluye desde 2026 el 9 de julio (Ley 2578 de 2026, art. 6)."""
    config = config or {}
    f = {}
    for mes, dia, nombre in [(1, 1, "Año Nuevo"), (5, 1, "Día del Trabajo"),
                             (7, 20, "Independencia de Colombia"),
                             (8, 7, "Batalla de Boyacá"),
                             (12, 8, "Inmaculada Concepción"), (12, 25, "Navidad")]:
        f[dt.date(anio, mes, dia)] = nombre
    trasladables = [(1, 6, "Reyes Magos"), (3, 19, "San José"),
                    (6, 29, "San Pedro y San Pablo"), (8, 15, "Asunción de la Virgen"),
                    (10, 12, "Día de la Raza"), (11, 1, "Todos los Santos"),
                    (11, 11, "Independencia de Cartagena")]
    if anio >= 2026:
        trasladables.append((7, 9, "Virgen del Rosario de Chiquinquirá"))
    for mes, dia, nombre in trasladables:
        f[_lunes_siguiente(dt.date(anio, mes, dia))] = nombre
    p = pascua(anio)
    for delta, nombre, mover in [(-3, "Jueves Santo", False), (-2, "Viernes Santo", False),
                                 (39, "Ascensión del Señor", True),
                                 (60, "Corpus Christi", True),
                                 (68, "Sagrado Corazón", True)]:
        d = p + dt.timedelta(days=delta)
        f[_lunes_siguiente(d) if mover else d] = nombre
    for s in config.get("festivos_excluidos", []):
        f.pop(fecha(s), None)
    for s in config.get("festivos_adicionales", []):
        d = fecha(s)
        if d and d.year == anio:
            f[d] = "Festivo adicional (configuración)"
    return dict(sorted(f.items()))


def en_vacancia(d, config=None):
    """Vacancia judicial colectiva por defecto: 20 de diciembre a 10 de enero y lunes a
    miércoles santos (jueves y viernes santos ya son festivos). Configurable."""
    config = config or {}
    if not config.get("vacancia", True):
        return False
    if (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 10):
        return True
    p = pascua(d.year)
    return p - dt.timedelta(days=6) <= d <= p - dt.timedelta(days=4)


_cache_festivos = {}


def es_habil(d, config=None):
    config = config or {}
    if d.weekday() >= 5:
        return False
    clave = (d.year, json.dumps(config, sort_keys=True, default=str))
    if clave not in _cache_festivos:
        _cache_festivos[clave] = festivos(d.year, config)
    if d in _cache_festivos[clave]:
        return False
    if en_vacancia(d, config):
        return False
    cierres = {fecha(x) for x in config.get("cierres_extra", [])}
    return d not in cierres


def sumar_habiles(d, n, config=None):
    """Día hábil número n contado desde el día siguiente a d."""
    actual, cuenta = d, 0
    while cuenta < n:
        actual += dt.timedelta(days=1)
        if es_habil(actual, config):
            cuenta += 1
    return actual


def contar_habiles(desde, hasta, config=None):
    """Días hábiles en el intervalo (desde, hasta] — negativo si hasta < desde."""
    if hasta < desde:
        return -contar_habiles(hasta, desde, config)
    total, actual = 0, desde
    while actual < hasta:
        actual += dt.timedelta(days=1)
        if es_habil(actual, config):
            total += 1
    return total


def sumar_meses(d, meses):
    mes0 = d.month - 1 + meses
    anio, mes = d.year + mes0 // 12, mes0 % 12 + 1
    ultimo = (dt.date(anio + (mes // 12), mes % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(anio, mes, min(d.day, ultimo))


def calcular_vencimiento(notificacion, dias=None, meses=None, mas_dos=False, config=None):
    """Calcula el vencimiento de un término.

    - Términos de días: corren desde el día siguiente a la notificación y solo cuentan
      días hábiles (CGP art. 118).
    - mas_dos: la notificación por mensaje de datos se entiende realizada dos días hábiles
      después del envío (Ley 2213 de 2022 art. 8; CPACA arts. 199 y 205). El usuario debe
      verificar la regla exacta aplicable (acuse de recibo, jurisdicción).
    - Términos de meses: vencen el mismo día del mes correspondiente; si es inhábil, se
      extienden al primer día hábil siguiente (CGP art. 118).
    """
    pasos = []
    base = notificacion
    if mas_dos:
        base = sumar_habiles(notificacion, 2, config)
        pasos.append(f"Envío del mensaje: {notificacion}. Notificación surtida (2 días "
                     f"hábiles después): {base}.")
    if dias is not None:
        venc = sumar_habiles(base, dias, config)
        inicio = sumar_habiles(base, 1, config)
        pasos.append(f"Término de {dias} día(s) hábil(es): corre desde {inicio} y vence "
                     f"el {venc}.")
    elif meses is not None:
        venc = sumar_meses(base, meses)
        while not es_habil(venc, config):
            venc += dt.timedelta(days=1)
        pasos.append(f"Término de {meses} mes(es) desde {base}: vence el {venc} "
                     "(ajustado al primer día hábil si cae en inhábil).")
    else:
        raise ValueError("Indique --dias o --meses.")
    return {"notificacion": str(notificacion), "base_computo": str(base),
            "vencimiento": str(venc), "dia_semana": NOMBRES_DIA[venc.weekday()],
            "pasos": pasos,
            "advertencia": ("Cálculo orientativo. Verifique en la providencia el término "
                            "concedido, la forma de notificación, suspensiones, cierres "
                            "del despacho y si el expediente estuvo al despacho.")}


NOMBRES_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# --------------------------------------------------------------------------- #
# Clasificación de actuaciones
# --------------------------------------------------------------------------- #

# (patrón regex sobre texto sin tildes, prioridad, sugerencia)
REGLAS = [
    (r"desistimiento", "ALTA", "Desistimiento: revisar de inmediato la providencia y su notificación."),
    (r"sentencia|fallo", "ALTA", "Sentencia/fallo: leer la decisión y verificar término para recurso o impugnación."),
    (r"inadmi", "ALTA", "Inadmisión: verificar término para subsanar."),
    (r"rechaz", "ALTA", "Rechazo: evaluar recursos procedentes y su término."),
    (r"requiere|requerimiento|requerir", "ALTA", "Requerimiento: identificar la carga ordenada y su plazo."),
    (r"traslado", "ALTA", "Traslado: verificar si corre término para pronunciarse."),
    (r"fija fecha|senala fecha|fijar fecha|reprograma|aplaza", "ALTA", "Fecha de audiencia/diligencia: agendar y confirmar enlace."),
    (r"audiencia|diligencia", "ALTA", "Audiencia o diligencia: confirmar fecha, hora y modalidad."),
    (r"mandamiento", "ALTA", "Mandamiento de pago: verificar notificación y términos del ejecutado."),
    (r"(?<!in)admite|admision|admitida", "ALTA", "Admisión: verificar notificación al demandado y términos de traslado."),
    (r"liquidacion|costas|agencias en derecho", "ALTA", "Liquidación/costas: verificar término para objetar."),
    (r"medida|embargo|secuestro|remate|avaluo", "ALTA", "Medidas cautelares/remate: revisar alcance y diligencias pendientes."),
    (r"apelacion|reposicion|recurso|concede|queja|suplica|casacion|impugna", "ALTA", "Recurso: verificar decisión, efecto y términos."),
    (r"desacato|incidente|nulidad|excepcion", "ALTA", "Incidente/excepciones/nulidad: revisar traslado y pruebas."),
    (r"pruebas|alegatos|alegar", "ALTA", "Etapa probatoria o de alegatos: verificar términos."),
    (r"terminacion|termina el proceso|archiv", "ALTA", "Terminación/archivo: verificar causa y efectos (desglose, levantamiento de medidas)."),
    (r"notifica|emplaza|aviso|citatorio", "MEDIA", "Notificación: verificar fecha en que se surtió para el cómputo de términos."),
    (r"\bauto\b|estado", "MEDIA", "Auto notificado por estado: leer la providencia."),
    (r"al despacho|ingreso al despacho|pasa al despacho", "INFO", "Expediente al despacho: mientras esté al despacho no corren términos (CGP art. 118), salvo excepciones."),
    (r"memorial|oficio|constancia|informe secretarial|recepcion|correo", "INFO", "Trámite secretarial."),
]
ORDEN_PRIORIDAD = {"ALTA": 0, "MEDIA": 1, "INFO": 2}


def clasificar(actuacion):
    texto = sin_tildes(f"{actuacion.get('actuacion', '')} {actuacion.get('anotacion', '')}")
    prioridad, sugerencias = "INFO", []
    for patron, prio, sugerencia in REGLAS:
        if re.search(patron, texto):
            if ORDEN_PRIORIDAD[prio] < ORDEN_PRIORIDAD[prioridad]:
                prioridad = prio
            if sugerencia not in sugerencias:
                sugerencias.append(sugerencia)
    return prioridad, sugerencias[:3]


# --------------------------------------------------------------------------- #
# Registro de procesos y estado
# --------------------------------------------------------------------------- #


def leer_config(ruta):
    if ruta and os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def leer_registro(ruta):
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe el registro {ruta}. Use `agregar` o copie la "
                                "plantilla assets/plantilla_procesos.csv.")
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        encabezado = fh.readline()
        fh.seek(0)
        # El separador se deduce del encabezado (Excel en español suele guardar con ';').
        delimitador = max([",", ";", "\t"], key=encabezado.count)
        filas = []
        for fila in csv.DictReader(fh, delimiter=delimitador):
            fila = {(k or "").strip().lower(): (v if isinstance(v, str) else "").strip()
                    for k, v in fila.items() if k is not None}
            if fila.get("radicado"):
                filas.append(fila)
    return filas


def es_cpnu(fila):
    return sin_tildes(fila.get("plataforma", "")) in ("", "cpnu")


def agregar_a_registro(ruta, datos):
    if es_cpnu(datos):
        radicado = desglosar_radicado(datos["radicado"])["radicado"]
    else:  # otras plataformas (SAMAI, TYBA, Procuraduría...) usan otros identificadores
        radicado = datos["radicado"].strip()
    existentes = leer_registro(ruta) if os.path.exists(ruta) else []
    if any(f["radicado"].strip() == radicado or
           (es_cpnu(datos) and normalizar_radicado(f["radicado"]) == radicado)
           for f in existentes):
        return False
    nuevo = not os.path.exists(ruta)
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS_REGISTRO)
        if nuevo:
            w.writeheader()
        fila = {c: datos.get(c, "") for c in COLUMNAS_REGISTRO}
        fila["radicado"] = radicado
        fila["estado_interno"] = fila["estado_interno"] or "activo"
        fila["plataforma"] = fila["plataforma"] or "CPNU"
        w.writerow(fila)
    return True


def ruta_estado(dir_estado, radicado):
    return os.path.join(dir_estado, f"{radicado}.json")


def cargar_estado(dir_estado, radicado):
    r = ruta_estado(dir_estado, radicado)
    if os.path.exists(r):
        with open(r, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def guardar_estado(dir_estado, radicado, consulta):
    os.makedirs(dir_estado, exist_ok=True)
    with open(ruta_estado(dir_estado, radicado), "w", encoding="utf-8") as fh:
        json.dump(consulta, fh, ensure_ascii=False, indent=1, default=str)


def _id_act(a):
    return str(a.get("idRegActuacion") or f"{a.get('consActuacion')}|{a.get('fechaActuacion')}|"
                                          f"{a.get('actuacion')}")


# --------------------------------------------------------------------------- #
# Revisión
# --------------------------------------------------------------------------- #


def analizar(fila, consulta, previo, config, desde=None, umbral_inactividad=300):
    """Compara la consulta actual con la anterior y produce hallazgos del proceso."""
    hoy_ = hoy()
    res = {"radicado": consulta["radicado"], "proceso": fila.get("proceso", ""),
           "cliente": fila.get("cliente", ""),
           "calidad": fila.get("calidad", ""), "tipo_proceso": fila.get("tipo_proceso", ""),
           "pendiente": fila.get("pendiente", ""),
           "notas": fila.get("notas", ""), "instancias": [], "alertas": [],
           "novedades": 0, "prioridad": "INFO", "primera_revision": previo is None}
    if not consulta["instancias"]:
        res["alertas"].append(
            "La CPNU no devolvió el proceso. Verifique el número; si es de la jurisdicción "
            "contencioso administrativa consulte SAMAI; si el despacho usa Justicia XXI Web, "
            "consulte TYBA (ver references/fuentes.md).")
        res["prioridad"] = "MEDIA"
        return res
    previas = set()
    if previo:
        for inst in previo.get("instancias", []):
            previas.update(_id_act(a) for a in inst.get("actuaciones") or [])
    ultima_global = None
    for inst in consulta["instancias"]:
        resumen, det = inst.get("resumen", {}), inst.get("detalle") or {}
        info = {"id_proceso": resumen.get("idProceso"),
                "despacho": det.get("despacho") or resumen.get("despacho"),
                "departamento": resumen.get("departamento"),
                "ponente": det.get("ponente"),
                "clase": " / ".join(x for x in [det.get("tipoProceso"), det.get("claseProceso"),
                                                det.get("subclaseProceso")] if x),
                "recurso": det.get("recurso"), "ubicacion": det.get("ubicacion"),
                "sujetos": resumen.get("sujetosProcesales"),
                "fecha_radicacion": str(fecha(resumen.get("fechaProceso")) or ""),
                "ultima_actuacion": str(fecha(resumen.get("fechaUltimaActuacion")) or ""),
                "privado": inst.get("privado"), "novedades": [], "terminos": [],
                "recientes": []}
        if inst.get("privado"):
            res["alertas"].append("Proceso con reserva/privado en la CPNU: solo se ve el "
                                  "resumen. Revise en el despacho o con usuario autorizado.")
        acts = inst.get("actuaciones") or []
        for a in acts:
            fa = fecha(a.get("fechaActuacion"))
            if fa and (ultima_global is None or fa > ultima_global):
                ultima_global = fa
            es_nueva = (fa and desde and fa >= desde) if desde else (
                previo is not None and _id_act(a) not in previas)
            prioridad, sugerencias = clasificar(a)
            item = {"fecha": str(fa or ""), "actuacion": a.get("actuacion", ""),
                    "anotacion": (a.get("anotacion") or "").strip(),
                    "registro": str(fecha(a.get("fechaRegistro")) or ""),
                    "con_documentos": bool(a.get("conDocumentos")),
                    "prioridad": prioridad, "sugerencias": sugerencias}
            if es_nueva:
                info["novedades"].append(item)
                if ORDEN_PRIORIDAD[prioridad] < ORDEN_PRIORIDAD[res["prioridad"]]:
                    res["prioridad"] = prioridad
            ffin = fecha(a.get("fechaFinal"))
            if ffin and ffin >= hoy_:
                restantes = contar_habiles(hoy_, ffin, config) + (1 if es_habil(hoy_, config) else 0)
                info["terminos"].append({
                    "actuacion": a.get("actuacion", ""), "anotacion": item["anotacion"],
                    "inicia": str(fecha(a.get("fechaInicial")) or ""), "vence": str(ffin),
                    "habiles_restantes_incluido_hoy": restantes})
                res["prioridad"] = "ALTA"
        ordenadas = sorted(acts, key=lambda a: (str(a.get("fechaActuacion") or ""),
                                                 a.get("consActuacion") or 0), reverse=True)
        if previo is None and not desde:
            for a in ordenadas[:5]:
                p, s = clasificar(a)
                info["recientes"].append({"fecha": str(fecha(a.get("fechaActuacion")) or ""),
                                          "actuacion": a.get("actuacion", ""),
                                          "anotacion": (a.get("anotacion") or "").strip(),
                                          "prioridad": p, "sugerencias": s})
        info["novedades"].sort(key=lambda x: x["fecha"], reverse=True)
        res["novedades"] += len(info["novedades"])
        res["instancias"].append(info)
    if ultima_global:
        dias = (hoy_ - ultima_global).days
        res["dias_sin_actuacion"] = dias
        if dias >= umbral_inactividad:
            res["alertas"].append(
                f"{dias} días calendario sin actuaciones registradas (última: {ultima_global}). "
                "En procesos regidos por el CGP, evalúe el riesgo de desistimiento tácito "
                "(art. 317 num. 2: un año de inactividad en primera o única instancia; dos años "
                "si hay sentencia ejecutoriada a favor del demandante o auto que ordena seguir "
                "adelante la ejecución) e impulse el proceso si corresponde.")
            if res["prioridad"] == "INFO":
                res["prioridad"] = "MEDIA"
    if res["primera_revision"] and not desde:
        res["alertas"].append("Primera revisión: se guardó la línea base; desde la próxima "
                              "revisión se mostrarán solo las actuaciones nuevas.")
    return res


def _celda(texto, largo=160):
    texto = re.sub(r"\s+", " ", str(texto or "")).replace("|", "/").strip()
    return texto if len(texto) <= largo else texto[:largo - 1] + "…"


def _titulo(r):
    nombre = " · ".join(x for x in [r.get("proceso"), r.get("cliente")] if x)
    return nombre


def informe_markdown(resultados, errores, meta, manuales=None):
    manuales = manuales or []
    L = []
    L.append("# Revisión de procesos — Rama Judicial")
    L.append("")
    L.append(f"- **Fecha de revisión:** {meta['fecha']}")
    if meta.get("abogado"):
        L.append(f"- **Abogado:** {meta['abogado']}")
    L.append(f"- **Fuente:** Consulta de Procesos Nacional Unificada (CPNU) — {PORTAL}")
    L.append(f"- **Procesos revisados:** {len(resultados)} · **con novedades:** "
             f"{sum(1 for r in resultados if r['novedades'])} · **con error de consulta:** "
             f"{len(errores)}")
    if meta.get("desde"):
        L.append(f"- **Criterio de novedad:** actuaciones con fecha desde {meta['desde']}")
    else:
        L.append("- **Criterio de novedad:** actuaciones no vistas en la revisión anterior")
    L.append("")
    orden = sorted(resultados, key=lambda r: (ORDEN_PRIORIDAD[r["prioridad"]], -r["novedades"]))
    L.append("## Resumen")
    L.append("")
    L.append("| Prioridad | Radicado | Proceso | Pendiente | Despacho | Última actuación | Novedades | Términos en curso | Alertas |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in orden:
        inst = r["instancias"][0] if r["instancias"] else {}
        terminos = sum(len(i["terminos"]) for i in r["instancias"])
        ultima = max((i.get("ultima_actuacion") or "" for i in r["instancias"]), default="")
        L.append(f"| {r['prioridad']} | {desglosar_radicado(r['radicado'])['formateado']} | "
                 f"{_celda(_titulo(r), 50)} | {_celda(r.get('pendiente'), 50)} | "
                 f"{_celda(inst.get('despacho'), 60)} | {ultima} | "
                 f"{r['novedades']} | {terminos} | {len(r['alertas'])} |")
    for e in errores:
        L.append(f"| ERROR | {e['radicado']} | {_celda(_titulo(e), 50)} | "
                 f"{_celda(e.get('pendiente'), 50)} | — | — | — | — | {_celda(e['error'], 80)} |")
    L.append("")
    L.append("## Detalle por proceso")
    for r in orden:
        L.append("")
        titulo = desglosar_radicado(r["radicado"])["formateado"]
        L.append(f"### {titulo}" + (f" — {_titulo(r)}" if _titulo(r) else ""))
        extra = [x for x in [r.get("calidad"), r.get("tipo_proceso")] if x]
        if extra:
            L.append(f"*{' · '.join(extra)}*")
        if r.get("pendiente"):
            L.append("")
            L.append(f"- **Pendiente registrado:** {r['pendiente']}")
        for inst in r["instancias"]:
            L.append("")
            L.append(f"- **Despacho:** {inst.get('despacho') or '—'} ({inst.get('departamento') or '—'})")
            if inst.get("ponente"):
                L.append(f"- **Ponente/Juez:** {inst['ponente']}")
            if inst.get("clase"):
                L.append(f"- **Clase:** {inst['clase']}")
            if inst.get("sujetos"):
                L.append(f"- **Sujetos:** {_celda(inst['sujetos'], 300)}")
            if inst.get("ubicacion"):
                L.append(f"- **Ubicación del expediente:** {inst['ubicacion']}")
            L.append(f"- **Radicación:** {inst.get('fecha_radicacion') or '—'} · "
                     f"**Última actuación:** {inst.get('ultima_actuacion') or '—'}")
            if inst["terminos"]:
                L.append("")
                L.append("**Términos registrados por el despacho en la CPNU (vigentes):**")
                L.append("")
                L.append("| Actuación | Inicia | Vence | Días hábiles restantes (incl. hoy) |")
                L.append("|---|---|---|---|")
                for t in inst["terminos"]:
                    L.append(f"| {_celda(t['actuacion'] + ' — ' + t['anotacion'], 120)} | "
                             f"{t['inicia']} | **{t['vence']}** | {t['habiles_restantes_incluido_hoy']} |")
            filas = inst["novedades"] or inst["recientes"]
            if filas:
                L.append("")
                L.append("**Novedades:**" if inst["novedades"] else
                         "**Últimas actuaciones (línea base):**")
                L.append("")
                L.append("| Fecha | Actuación | Anotación | Prioridad | Qué revisar |")
                L.append("|---|---|---|---|---|")
                for a in filas:
                    L.append(f"| {a['fecha']} | {_celda(a['actuacion'], 60)} | "
                             f"{_celda(a['anotacion'], 220)} | {a['prioridad']} | "
                             f"{_celda(' '.join(a['sugerencias']), 200)} |")
            elif not inst.get("privado"):
                L.append("")
                L.append("Sin novedades desde la revisión anterior.")
        if r["alertas"]:
            L.append("")
            L.append("**Alertas:**")
            for a in r["alertas"]:
                L.append(f"- {a}")
        if r.get("notas"):
            L.append("")
            L.append(f"**Notas internas:** {r['notas']}")
    if manuales:
        L.append("")
        L.append("## Consultar en otra plataforma")
        L.append("")
        L.append("| Identificador | Proceso | Plataforma | Pendiente | Enlace |")
        L.append("|---|---|---|---|---|")
        for m in manuales:
            L.append(f"| {m['radicado']} | {_celda(_titulo(m), 50)} | {m.get('plataforma')} | "
                     f"{_celda(m.get('pendiente'), 60)} | {m.get('enlace') or '—'} |")
    if errores:
        L.append("")
        L.append("## Errores de consulta")
        for e in errores:
            L.append(f"- {e['radicado']}: {e['error']}")
    L.append("")
    L.append("---")
    L.append("*Informe orientativo generado a partir de la CPNU. Los términos corren desde la "
             "notificación de cada providencia (CGP art. 118); verifique siempre la providencia, "
             "el estado o la notificación electrónica y el expediente antes de actuar. Las "
             "prioridades y sugerencias se asignan por palabras clave y no sustituyen el "
             "análisis del abogado.*")
    return "\n".join(L) + "\n"


def cmd_revisar(args):
    config = leer_config(args.config)
    filas = leer_registro(args.registro)
    activos = [f for f in filas if sin_tildes(f.get("estado_interno", "activo")) not in ESTADOS_INACTIVOS]
    if args.solo:
        objetivo = {normalizar_radicado(x) for x in args.solo}
        activos = [f for f in activos if normalizar_radicado(f["radicado"]) in objetivo]
    if not activos:
        print("No hay procesos activos en el registro.", file=sys.stderr)
        return 1
    desde = fecha(args.desde) if args.desde else None
    capturadas = {}
    if args.entrada:  # consultas capturadas en el navegador (assets/consulta_navegador.js)
        with open(args.entrada, encoding="utf-8") as fh:
            datos = json.load(fh)
        for c in (datos.get("consultas") if isinstance(datos, dict) else datos) or []:
            capturadas[normalizar_radicado(c.get("radicado"))] = c
    resultados, errores, manuales = [], [], []
    for k, fila in enumerate(activos, 1):
        base = {"radicado": fila["radicado"], "proceso": fila.get("proceso"),
                "cliente": fila.get("cliente"), "pendiente": fila.get("pendiente")}
        if not es_cpnu(fila):
            plataforma = fila.get("plataforma", "")
            manuales.append(dict(base, plataforma=plataforma,
                                 enlace=PLATAFORMAS_MANUALES.get(sin_tildes(plataforma), "")))
            continue
        rad = normalizar_radicado(fila["radicado"])
        print(f"[{k}/{len(activos)}] {rad} {fila.get('proceso', '')}", file=sys.stderr)
        try:
            desglosar_radicado(rad)
        except ValueError as e:
            errores.append(dict(base, error=str(e)))
            continue
        if args.entrada:
            consulta = capturadas.get(rad)
            if consulta is None:
                errores.append(dict(base, error="No viene en el archivo de entrada."))
                continue
            if consulta.get("error"):
                errores.append(dict(base, error=f"Error en navegador: {consulta['error']}"))
                continue
        else:
            try:
                consulta = consultar(rad, con_sujetos=False)
            except CPNUNoDisponible as e:
                print(str(e), file=sys.stderr)
                return 3
            except CPNUError as e:
                errores.append(dict(base, error=str(e)))
                continue
        previo = cargar_estado(args.estado, rad)
        resultados.append(analizar(fila, consulta, previo, config, desde,
                                   config.get("umbral_inactividad_dias", 300)))
        if not args.no_guardar:
            guardar_estado(args.estado, rad, consulta)
    meta = {"fecha": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "abogado": config.get("abogado", ""), "desde": str(desde) if desde else None}
    md = informe_markdown(resultados, errores, meta, manuales)
    os.makedirs(args.salida, exist_ok=True)
    sello = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    nombre, k = f"revision_{sello}", 2
    while os.path.exists(os.path.join(args.salida, nombre + ".md")):
        nombre, k = f"revision_{sello}_{k}", k + 1
    ruta_md = os.path.join(args.salida, nombre + ".md")
    ruta_json = os.path.join(args.salida, nombre + ".json")
    with open(ruta_md, "w", encoding="utf-8") as fh:
        fh.write(md)
    with open(ruta_json, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "resultados": resultados, "errores": errores,
                   "manuales": manuales}, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({"informe_md": ruta_md, "informe_json": ruta_json,
                      "revisados": len(resultados), "errores": len(errores),
                      "otra_plataforma": len(manuales),
                      "con_novedades": sum(1 for r in resultados if r["novedades"]),
                      "prioridad_alta": sum(1 for r in resultados if r["prioridad"] == "ALTA")},
                     ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv=None):
    base = os.environ.get("PROCESOS_DIR", "procesos")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("validar", help="Valida y desglosa un radicado")
    s.add_argument("radicado")
    s.add_argument("--decodificar", action="store_true",
                   help="Traduce códigos a nombres con las listas oficiales (requiere acceso a la API)")

    s = sub.add_parser("consultar", help="Consulta un radicado en la CPNU")
    s.add_argument("radicado")
    s.add_argument("--sin-sujetos", action="store_true")
    s.add_argument("--guardar", metavar="ARCHIVO", help="Guarda la respuesta completa en JSON")

    s = sub.add_parser("buscar-nombre", help="Busca procesos por nombre o razón social")
    s.add_argument("nombre")
    s.add_argument("--tipo", choices=["nat", "jur"], default="nat",
                   help="nat = persona natural, jur = persona jurídica")
    s.add_argument("--recientes", action="store_true",
                   help="Solo procesos con actuaciones en los últimos 30 días")
    s.add_argument("--despacho", default="", help="Código de despacho para filtrar (opcional)")

    s = sub.add_parser("agregar", help="Agrega un proceso al registro")
    s.add_argument("radicado")
    for c in COLUMNAS_REGISTRO[1:]:
        s.add_argument(f"--{c.replace('_', '-')}", dest=c, default="")
    s.add_argument("--registro", default=os.path.join(base, "procesos.csv"))

    s = sub.add_parser("lista-radicados", help="Imprime los radicados CPNU activos del registro (JSON)")
    s.add_argument("--registro", default=os.path.join(base, "procesos.csv"))

    s = sub.add_parser("revisar", help="Revisa los procesos del registro y genera informe")
    s.add_argument("--registro", default=os.path.join(base, "procesos.csv"))
    s.add_argument("--estado", default=os.path.join(base, "estado"))
    s.add_argument("--salida", default=os.path.join(base, "informes"))
    s.add_argument("--config", default=os.path.join(base, "config.json"))
    s.add_argument("--desde", help="Tratar como novedad toda actuación desde esta fecha (AAAA-MM-DD)")
    s.add_argument("--solo", nargs="+", help="Revisar solo estos radicados")
    s.add_argument("--entrada", metavar="JSON",
                   help="Usar consultas capturadas en el navegador en lugar de llamar a la API")
    s.add_argument("--no-guardar", action="store_true", help="No actualizar la línea base")

    s = sub.add_parser("habiles", help="Calcula vencimientos en días hábiles")
    s.add_argument("--desde", required=True,
                   help="Fecha de notificación (o de envío del mensaje si usa --mas-dos)")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--dias", type=int)
    g.add_argument("--meses", type=int)
    s.add_argument("--mas-dos", action="store_true",
                   help="Notificación por mensaje de datos: se surte 2 días hábiles después del envío")
    s.add_argument("--sin-vacancia", action="store_true",
                   help="No descontar vacancia judicial (despachos con vacaciones individuales)")
    s.add_argument("--config", default=os.path.join(base, "config.json"))

    s = sub.add_parser("festivos", help="Lista festivos y vacancia de un año")
    s.add_argument("anio", type=int)
    s.add_argument("--config", default=os.path.join(base, "config.json"))

    args = ap.parse_args(argv)
    try:
        if args.cmd == "validar":
            imprimir_json(decodificar_radicado(args.radicado) if args.decodificar
                          else desglosar_radicado(args.radicado))
        elif args.cmd == "consultar":
            desglosar_radicado(args.radicado)
            r = consultar(args.radicado, con_sujetos=not args.sin_sujetos)
            if args.guardar:
                with open(args.guardar, "w", encoding="utf-8") as fh:
                    json.dump(r, fh, ensure_ascii=False, indent=1, default=str)
            imprimir_json(r)
        elif args.cmd == "buscar-nombre":
            procesos = buscar_por_nombre(args.nombre, args.tipo, args.recientes, args.despacho)
            imprimir_json({"nombre": args.nombre, "total": len(procesos), "procesos": [
                {"radicado": p.get("llaveProceso"), "despacho": p.get("despacho"),
                 "departamento": p.get("departamento"),
                 "fecha_radicacion": str(fecha(p.get("fechaProceso")) or ""),
                 "ultima_actuacion": str(fecha(p.get("fechaUltimaActuacion")) or ""),
                 "sujetos": p.get("sujetosProcesales"), "privado": p.get("esPrivado")}
                for p in procesos]})
        elif args.cmd == "agregar":
            datos = {c: getattr(args, c, "") for c in COLUMNAS_REGISTRO}
            datos["radicado"] = args.radicado
            ok = agregar_a_registro(args.registro, datos)
            ident = (desglosar_radicado(args.radicado)["formateado"] if es_cpnu(datos)
                     else args.radicado)
            print(("Agregado" if ok else "Ya estaba en el registro") + f": {ident} → {args.registro}")
        elif args.cmd == "lista-radicados":
            filas = leer_registro(args.registro)
            print(json.dumps([normalizar_radicado(f["radicado"]) for f in filas
                              if es_cpnu(f) and sin_tildes(f.get("estado_interno", ""))
                              not in ESTADOS_INACTIVOS]))
        elif args.cmd == "revisar":
            return cmd_revisar(args)
        elif args.cmd == "habiles":
            config = leer_config(args.config)
            if args.sin_vacancia:
                config["vacancia"] = False
            d = fecha(args.desde)
            if not d:
                raise ValueError("Fecha inválida; use AAAA-MM-DD.")
            imprimir_json(calcular_vencimiento(d, args.dias, args.meses, args.mas_dos, config))
        elif args.cmd == "festivos":
            config = leer_config(args.config)
            p = pascua(args.anio)
            imprimir_json({
                "anio": args.anio,
                "festivos": {str(k): v for k, v in festivos(args.anio, config).items()},
                "vacancia_por_defecto": [f"{args.anio}-01-01 a {args.anio}-01-10",
                                         f"{p - dt.timedelta(days=6)} a {p - dt.timedelta(days=4)} (lunes a miércoles santos)",
                                         f"{args.anio}-12-20 a {args.anio}-12-31"]})
    except CPNUNoDisponible as e:
        print(str(e), file=sys.stderr)
        return 3
    except (CPNUError, ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
