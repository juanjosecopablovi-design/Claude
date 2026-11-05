/*
 * Consulta por lotes en la CPNU desde el navegador.
 *
 * Uso: abrir https://consultaprocesos.ramajudicial.gov.co/Procesos/Index en un equipo
 * con conexión desde Colombia, pegar este archivo completo en la consola del navegador
 * (o ejecutarlo con la herramienta de JavaScript de Claude en Chrome) y luego llamar:
 *
 *   await consultarCPNU(["11001310300120240000100", "05001400300120250000200"]);
 *
 * Usa los mismos servicios que el portal (API v2 en el puerto 448). Descarga un archivo
 * consultas_cpnu_AAAA-MM-DD.json con el mismo formato que `rama.py consultar`, para
 * procesarlo con:  python3 scripts/rama.py revisar --entrada consultas_cpnu_AAAA-MM-DD.json
 *
 * Devuelve un resumen corto; el detalle completo va en el archivo descargado.
 */
async function consultarCPNU(radicados, opciones = {}) {
  const API = opciones.api || "https://consultaprocesos.ramajudicial.gov.co:448/api/v2";
  const pausaMs = opciones.pausaMs ?? 800;           // pausa entre llamadas: no saturar el servicio
  const descargar = opciones.descargar ?? (typeof document !== "undefined");
  const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

  async function get(ruta) {
    let ultimo;
    for (let intento = 0; intento < 3; intento++) {
      try {
        const r = await fetch(API + ruta, { headers: { Accept: "application/json" } });
        if (r.ok) {
          const t = await r.text();
          return t ? JSON.parse(t) : null;
        }
        ultimo = new Error("HTTP " + r.status);
        if (![429, 500, 502, 503, 504].includes(r.status)) throw ultimo;
      } catch (e) {
        ultimo = e;
        if (String(e).startsWith("Error: HTTP 4")) throw e;
      }
      await esperar(2000 * (intento + 1));
    }
    throw ultimo;
  }

  async function paginar(ruta, clave) {
    const sep = ruta.includes("?") ? "&" : "?";
    let salida = [];
    for (let pagina = 1; pagina <= 60; pagina++) {
      const datos = (await get(`${ruta}${sep}pagina=${pagina}`)) || {};
      salida = salida.concat(datos[clave] || []);
      const total = (datos.paginacion && datos.paginacion.cantidadPaginas) || 1;
      if (pagina >= total) break;
      await esperar(pausaMs);
    }
    return salida;
  }

  const consultas = [];
  for (const rad of radicados) {
    const numero = String(rad).replace(/\D/g, "");
    const c = {
      radicado: numero,
      consultado_en: new Date().toISOString(),
      fuente: API + " (navegador)",
      instancias: [],
    };
    try {
      if (numero.length !== 23) throw new Error("El radicado no tiene 23 dígitos");
      const procesos = await paginar(
        `/Procesos/Consulta/NumeroRadicacion?numero=${numero}&SoloActivos=false`, "procesos");
      for (const p of procesos) {
        const inst = { resumen: p, privado: !!p.esPrivado };
        if (p.idProceso && !inst.privado) {
          await esperar(pausaMs);
          inst.detalle = (await get(`/Proceso/Detalle/${p.idProceso}`)) || {};
          await esperar(pausaMs);
          inst.actuaciones = await paginar(`/Proceso/Actuaciones/${p.idProceso}`, "actuaciones");
        }
        c.instancias.push(inst);
      }
    } catch (e) {
      c.error = String(e);
    }
    consultas.push(c);
    console.log(`${consultas.length}/${radicados.length} ${numero}: ` +
      (c.error ? "ERROR " + c.error : `${c.instancias.length} registro(s)`));
    await esperar(pausaMs);
  }

  const salida = { generado: new Date().toISOString(), consultas };
  const nombre = `consultas_cpnu_${new Date().toISOString().slice(0, 10)}.json`;
  if (descargar) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(salida)], { type: "application/json" }));
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  if (typeof window !== "undefined") window.__consultasCPNU = salida;  // por si falla la descarga
  return {
    archivo: descargar ? nombre : null,
    total: consultas.length,
    con_error: consultas.filter((c) => c.error).map((c) => `${c.radicado}: ${c.error}`),
    no_encontrados: consultas.filter((c) => !c.error && c.instancias.length === 0).map((c) => c.radicado),
    ultimas_actuaciones: consultas.filter((c) => !c.error).map((c) => ({
      radicado: c.radicado,
      ultima: c.instancias.map((i) => (i.resumen.fechaUltimaActuacion || "").slice(0, 10)).join(", "),
    })),
  };
}
if (typeof module !== "undefined") module.exports = { consultarCPNU };
