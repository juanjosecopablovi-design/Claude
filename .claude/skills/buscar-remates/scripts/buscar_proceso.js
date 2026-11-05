#!/usr/bin/env node
// Lista todas las publicaciones de UN despacho en un rango de fechas (estados, autos,
// remates, avisos, traslados...) y abre cada una para obtener sus documentos.
// Después use grep_radicado.py para buscar el proceso en esos documentos.
//
// Uso:
//   node buscar_proceso.js --depto 50 --despacho 505733189002 --desde 2026-01-01 --hasta 2026-11-05 --out DIR
// Opciones: --categorias "Estados,Autos,Remates" (filtra por tipo de publicación)  --max-min 8
// Reanudable: si se detiene por tiempo, vuelva a ejecutar el mismo comando.
const fs = require('fs');
const path = require('path');
const P = require('./portal');

const a = P.args(process.argv);
for (const k of ['depto', 'despacho', 'desde', 'hasta', 'out']) if (!a[k]) { console.error('Falta --' + k); process.exit(2); }
const maxMin = +(a['max-min'] || 8);
fs.mkdirSync(a.out, { recursive: true });
const solo = a.categorias ? String(a.categorias).split(',').map(s => s.trim()) : null;

(async () => {
  const t0 = Date.now();
  const restante = () => maxMin - (Date.now() - t0) / 60000;
  const { browser, page } = await P.launch();
  const filtro = { depto: a.depto, despacho: a.despacho, desde: a.desde, hasta: a.hasta };
  const salida = path.join(a.out, 'listado.json');
  let estado = fs.existsSync(salida) ? JSON.parse(fs.readFileSync(salida, 'utf8')) : null;
  let completo = true;
  if (!estado || !estado.completo) {
    const { base, total } = await P.urlCategoria(page, filtro, null);
    console.error(`Despacho ${a.despacho}: ${total ?? 'varias'} publicaciones en el rango`);
    if (!base) estado = { completo: true, items: [] };
    else { const r = await P.recorrerCategoria(page, base, total, salida, Math.max(1, restante())); estado = r.estado; completo = r.completo; }
  }
  // Solo el despacho pedido (el portal a veces mezcla otros) y, si se pidió, ciertas categorías.
  const items = estado.items.filter(it => it.despacho === a.despacho
    && (!solo || solo.some(s => (it.tipo_publicacion || '').toLowerCase().includes(s.toLowerCase()))))
    .map(it => ({ ...it, categoria: it.tipo_publicacion }));
  const fDet = path.join(a.out, 'detalles.json');
  const det = fs.existsSync(fDet) ? JSON.parse(fs.readFileSync(fDet, 'utf8')) : {};
  for (const it of items) {
    if (det[it.href]) continue;
    if (restante() <= 0) { completo = false; break; }
    try { det[it.href] = await P.detalle(page, it.href); } catch (e) { console.error('detalle falló:', it.titulo); continue; }
    fs.writeFileSync(fDet, JSON.stringify(det, null, 1));
  }
  const final = items.map(it => ({ ...it, ...(det[it.href] || {}) }));
  fs.writeFileSync(path.join(a.out, 'publicaciones.json'), JSON.stringify(final, null, 1));
  await browser.close();
  console.log(JSON.stringify({ completo, publicaciones: final.length, con_detalle: final.filter(x => x.docs).length }));
  if (!completo) console.error('INCOMPLETO: vuelva a ejecutar el mismo comando para continuar.');
})().catch(e => { console.error(e); process.exit(1); });
