// Utilidades compartidas para consultar Publicaciones Procesales (Rama Judicial).
// Requiere playwright-core instalado por setup.sh en $REMATES_WORK.
const fs = require('fs');
const path = require('path');
const os = require('os');

const WORK = process.env.REMATES_WORK || path.join(os.homedir(), '.cache', 'buscar-remates');
const { chromium } = require(path.join(WORK, 'node_modules', 'playwright-core'));

const PORTAL = 'https://publicacionesprocesales.ramajudicial.gov.co/web/publicaciones-procesales/inicio';
const PID = 'co_com_avanti_efectosProcesales_PublicacionesEfectosProcesalesPortletV2_INSTANCE_BIyXQFHVaYaq';
const N = '_' + PID + '_';

function chromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  for (const p of ['/opt/pw-browsers/chromium']) if (fs.existsSync(p)) return p;
  return undefined; // deja que playwright use su navegador por defecto
}

async function launch() {
  const opts = { args: ['--no-sandbox', '--disable-http2', '--disable-background-networking'] };
  const exe = chromePath();
  if (exe) opts.executablePath = exe;
  if (process.env.HTTPS_PROXY) opts.proxy = { server: process.env.HTTPS_PROXY };
  const browser = await chromium.launch(opts);
  const page = await browser.newPage({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 1800 } });
  return { browser, page };
}

async function go(page, url, waitMs = 6000) {
  for (let i = 0; i < 6; i++) {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });
      await page.waitForTimeout(waitMs);
      return;
    } catch (e) {
      await page.waitForTimeout(4000 * (i + 1));
    }
  }
  throw new Error('No se pudo abrir ' + url);
}

// URL de consulta filtrada. idStructure (categoría) es opcional.
function filtroUrl({ depto, desde, hasta, despacho, idStructure, idDeptoIdCategory, cur }) {
  let u = `${PORTAL}?p_p_id=${PID}&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view`
    + `&${N}action=filterStructures&${N}fechaInicio=${desde}&${N}fechaFin=${hasta}&${N}verTotales=true`;
  if (depto) u += `&${N}idDepto=${depto}`;
  if (despacho) u += `&${N}idDespacho=${despacho}`;
  if (idStructure) u += `&${N}idStructure=${idStructure}`;
  if (idDeptoIdCategory) u += `&${N}idDeptoIdCategory=${idDeptoIdCategory}`;
  if (cur) u += `&${N}cur=${cur}`;
  return u;
}

// Id de la categoría "Remates" (idStructure). Sirve para cualquier departamento.
const REMATES_ID = 6098997;

// Total de resultados de la página actual ("Mostrando el intervalo 1 - 10 de 36 resultados").
async function total(page) {
  const t = (await page.innerText('body')).replace(/\s+/g, ' ');
  const m = t.match(/de\s+([\d.]+)\s+resultados?/i);
  if (m) return +m[1].replace(/\./g, '');
  return /VER DETALLE/i.test(t) ? null : 0; // null: hay resultados pero no se sabe cuántos
}

// URL base de la consulta (sin página) y total de resultados.
// nombre = 'Remates' filtra la categoría de remates; null trae todas las publicaciones.
async function urlCategoria(page, filtro, nombre) {
  const base = filtroUrl({ ...filtro, idStructure: nombre === 'Remates' ? REMATES_ID : filtro.idStructure });
  await go(page, `${base}&${N}cur=1`, 15000);
  const n = await total(page);
  return { total: n, base: n === 0 ? null : base };
}

// Tarjetas de resultados de la página actual.
async function tarjetas(page) {
  return page.$$eval('a', as => as.filter(a => /VER DETALLE/i.test(a.innerText)).map(a => {
    let x = a;
    for (let k = 0; k < 8 && x && !/Fecha de Publicaci/.test(x.innerText); k++) x = x.parentElement;
    const txt = (x ? x.innerText : '').replace(/\s+/g, ' ').trim();
    const g = re => { const m = txt.match(re); return m ? m[1].trim() : null; };
    return {
      titulo: txt.split(' Categorías')[0],
      despacho: g(/Despacho:\s*(\d{12})/),
      despacho_nombre: g(/Despacho:\s*\d{12}\s*-\s*(.*?)\s*Fecha de Publicaci/),
      municipio: g(/Municipio:\s*(.*?)\s*Entidad:/),
      tipo_publicacion: g(/Tipo de publicación:\s*(.*?)\s*Departamento:/),
      fecha_publicacion: g(/Fecha de Publicación:\s*(\d{4}-\d{2}-\d{2})/),
      href: a.href,
    };
  }));
}

// Recorre todas las páginas de una categoría. Guarda en `salida` después de cada página
// y se detiene a los `maxMin` minutos; al volver a ejecutar continúa donde quedó.
async function recorrerCategoria(page, base, total, salida, maxMin = 8) {
  const t0 = Date.now();
  let estado = fs.existsSync(salida) ? JSON.parse(fs.readFileSync(salida, 'utf8')) : { pagina: 0, items: [] };
  const vistos = new Set(estado.items.map(x => x.href));
  // Si no se conoce el total, avanza hasta una página sin tarjetas nuevas (máximo 500).
  const paginas = total ? Math.ceil(total / 10) : 500;
  for (let cur = estado.pagina + 1; cur <= paginas; cur++) {
    if ((Date.now() - t0) / 60000 > maxMin) {
      console.error(`Pausa por tiempo en la página ${cur}/${paginas}; vuelva a ejecutar para continuar.`);
      return { completo: false, estado };
    }
    await go(page, `${base}&${N}cur=${cur}`, 12000);
    const cs = await tarjetas(page);
    let nuevas = 0;
    for (const c of cs) if (!vistos.has(c.href)) { vistos.add(c.href); estado.items.push(c); nuevas++; }
    if (!total && !nuevas) break;
    estado.pagina = cur;
    fs.writeFileSync(salida, JSON.stringify(estado, null, 1));
    console.error(`página ${cur}/${total ? paginas : '?'}: ${cs.length} tarjetas, acumuladas ${estado.items.length}`);
  }
  estado.completo = true;
  fs.writeFileSync(salida, JSON.stringify(estado, null, 1));
  return { completo: true, estado };
}

// Abre el detalle de una publicación y devuelve sus documentos, el resumen, el radicado
// y los enlaces externos (expediente en SharePoint/OneDrive o acortador, audiencia en Teams).
async function detalle(page, href) {
  await go(page, href, 6000);
  const links = await page.$$eval('a', as => as.map(a => ({ t: a.innerText.trim().replace(/\s+/g, ' '), h: a.href })));
  const body = (await page.innerText('body')).replace(/\s+/g, ' ');
  const corta = (re) => { const m = body.match(re); return m ? m[1].trim() : null; };
  const docs = [];
  const enlaces = [];
  let sharepoint = null;
  for (const l of links) {
    if (/sharepoint|onedrive|1drv\.ms/i.test(l.h)) { sharepoint = sharepoint || l.h; enlaces.push({ tipo: 'expediente', url: l.h }); continue; }
    if (/teams\.microsoft|teams\.live|lifesize|zoom\.us|meet\.google/i.test(l.h)) { enlaces.push({ tipo: 'audiencia', url: l.h }); continue; }
    if (/acortar\.link|bit\.ly|tinyurl|cutt\.ly|shorturl/i.test(l.h)) { enlaces.push({ tipo: 'enlace_corto', url: l.h }); continue; }
    const esDoc = /\/documents\/|document_library\/get_file/.test(l.h);
    if (esDoc && !/infografia|ABC_Ciudadano|\/documents\/20135\//i.test(l.h)) {
      docs.push({ texto: l.t, url: l.h, protocolo: /PROTOCOLO/i.test(l.h + ' ' + l.t), expediente_previo: sharepoint });
    }
  }
  return {
    docs, sharepoint, enlaces,
    resumen: corta(/Resumen de la publicación\s*(.*?)\s*Documentos de la publicación/),
    radicado_publicacion: corta(/Número de Radicación\s*([\d \-]{9,40}\d)/),
  };
}

function args(argv) {
  const o = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); const v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true; o[k] = v; }
  }
  return o;
}

module.exports = { WORK, PORTAL, N, REMATES_ID, launch, go, filtroUrl, total, urlCategoria, tarjetas, recorrerCategoria, detalle, args };
