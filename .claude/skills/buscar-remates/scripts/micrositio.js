#!/usr/bin/env node
// Recorre el micrositio de un juzgado en ramajudicial.gov.co y lista sus documentos.
// Sirve para procesos o años que no están en Publicaciones Procesales (antes de mayo de 2024)
// o cuando el juzgado publica en su micrositio.
//
// Uso:
//   node micrositio.js --sitio juzgado-002-promiscuo-del-circuito-de-puerto-lopez --out DIR
//        [--filtro "2018|remate|estado"] [--profundidad 3] [--max-min 8]
// --filtro limita las páginas internas que se siguen (expresión regular sobre el texto o la URL del enlace).
// Escribe DIR/publicaciones.json (compatible con grep_radicado.py). Reanudable.
const fs = require('fs');
const path = require('path');
const P = require('./portal');

const a = P.args(process.argv);
if (!a.sitio || !a.out) { console.error('Faltan --sitio o --out'); process.exit(2); }
const base = `https://www.ramajudicial.gov.co/web/${a.sitio}`;
const prof = +(a.profundidad || 3);
const maxMin = +(a['max-min'] || 8);
const filtro = a.filtro ? new RegExp(a.filtro, 'i') : null;
fs.mkdirSync(a.out, { recursive: true });
const fEst = path.join(a.out, 'micrositio_estado.json');

(async () => {
  const t0 = Date.now();
  const st = fs.existsSync(fEst) ? JSON.parse(fs.readFileSync(fEst, 'utf8'))
    : { cola: [[base + '/inicio', 0]], vistas: [], paginas: [] };
  const vistas = new Set(st.vistas);
  const { browser, page } = await P.launch();
  let completo = true;
  while (st.cola.length) {
    if ((Date.now() - t0) / 60000 > maxMin) { completo = false; break; }
    const [url, d] = st.cola.shift();
    if (vistas.has(url)) continue;
    vistas.add(url);
    let ok = false;
    for (let i = 0; i < 3 && !ok; i++) {
      try { await P.go(page, url, 4000); } catch (e) { break; }
      const tt = await page.title();
      ok = !/service unavailable|forbidden|error/i.test(tt);
      if (!ok) await page.waitForTimeout(20000);
    }
    if (!ok) {  // Sitio caído o bloqueado: se deja en la cola para el siguiente intento.
      vistas.delete(url); st.cola.push([url, d]); completo = false;
      console.error('El micrositio no responde (', url, '). Intente más tarde.');
      break;
    }
    const links = await page.$$eval('a', as => as.map(x => ({ t: x.innerText.trim().replace(/\s+/g, ' '), h: x.href.split('#')[0] })));
    const docs = links.filter(l => /\/documents\//.test(l.h)).map(l => ({ texto: l.t, url: l.h }));
    const titulo = (await page.title()).replace(/\s*-\s*Rama Judicial.*$/i, '');
    st.paginas.push({ titulo, href: url, fecha_publicacion: null, categoria: 'micrositio', docs });
    console.error(`${titulo} | ${docs.length} documentos`);
    if (d < prof) for (const l of links) {
      if (!l.h.startsWith(base) || /\/documents\//.test(l.h) || vistas.has(l.h)) continue;
      if (filtro && d > 0 && !filtro.test(l.t + ' ' + l.h)) continue;
      st.cola.push([l.h, d + 1]);
    }
    st.vistas = [...vistas];
    fs.writeFileSync(fEst, JSON.stringify(st));
  }
  await browser.close();
  fs.writeFileSync(path.join(a.out, 'publicaciones.json'), JSON.stringify(st.paginas, null, 1));
  const n = st.paginas.reduce((s, p) => s + p.docs.length, 0);
  console.log(JSON.stringify({ completo, paginas: st.paginas.length, documentos: n, pendientes: st.cola.length }));
  if (!completo) console.error('INCOMPLETO: vuelva a ejecutar el mismo comando para continuar.');
})().catch(e => { console.error(e); process.exit(1); });
