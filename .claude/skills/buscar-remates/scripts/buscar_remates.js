#!/usr/bin/env node
// Busca publicaciones de la categoría Remates en Publicaciones Procesales para las ciudades
// configuradas y abre cada publicación para obtener los autos y la carpeta del expediente.
//
// Uso:
//   node buscar_remates.js --ciudades medellin,envigado --desde 2026-05-01 --hasta 2026-11-05 --out DIR
//   node buscar_remates.js --ciudades todas --desde ... --hasta ... --out DIR
//   node buscar_remates.js --despachos 050013403001,050013403002 --depto 05 --desde ... --hasta ... --out DIR
// Opciones: --tipos "Civil Municipal,Promiscuo Municipal"  --max-min 8
// Es reanudable: si se detiene por tiempo, vuelva a ejecutar el mismo comando.
const fs = require('fs');
const path = require('path');
const P = require('./portal');

const a = P.args(process.argv);
if (!a.desde || !a.hasta || !a.out) {
  console.error('Faltan --desde, --hasta o --out');
  process.exit(2);
}
const maxMin = +(a['max-min'] || 8);
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config', 'despachos.json'), 'utf8'));
fs.mkdirSync(a.out, { recursive: true });

// Despachos objetivo agrupados por departamento.
const objetivo = {}; // depto -> Map(codigo -> {nombre, tipo, ciudad})
function agrega(depto, d, ciudad) { (objetivo[depto] = objetivo[depto] || new Map()).set(d.codigo, { ...d, ciudad }); }
if (a.despachos) {
  if (!a.depto) { console.error('Con --despachos indique --depto (05 Antioquia, 15 Boyacá...)'); process.exit(2); }
  for (const c of String(a.despachos).split(',')) agrega(a.depto, { codigo: c.trim(), nombre: '', tipo: '' }, '');
} else {
  const lista = !a.ciudades || a.ciudades === 'todas' ? Object.keys(cfg.ciudades) : String(a.ciudades).split(',').map(s => s.trim());
  const tipos = a.tipos ? String(a.tipos).split(',').map(s => s.trim().toLowerCase()) : null;
  for (const k of lista) {
    const c = cfg.ciudades[k];
    if (!c) { console.error(`Ciudad desconocida: ${k}. Opciones: ${Object.keys(cfg.ciudades).join(', ')}`); process.exit(2); }
    for (const d of c.despachos) if (!tipos || tipos.includes(d.tipo.toLowerCase())) agrega(c.departamento, d, c.nombre);
  }
}

(async () => {
  const t0 = Date.now();
  const restante = () => maxMin - (Date.now() - t0) / 60000;
  const { browser, page } = await P.launch();
  let completo = true;
  const pubs = [];
  for (const [depto, mapa] of Object.entries(objetivo)) {
    const salida = path.join(a.out, `remates_${depto}_${a.desde}_${a.hasta}.json`);
    let estado = fs.existsSync(salida) ? JSON.parse(fs.readFileSync(salida, 'utf8')) : null;
    if (!estado || !estado.completo) {
      const filtro = { depto, desde: a.desde, hasta: a.hasta };
      const { total, base } = await P.urlCategoria(page, filtro, 'Remates');
      console.error(`Departamento ${depto}: ${total ?? 'varios'} remates publicados en el rango`);
      if (!base) { estado = { completo: true, items: [] }; fs.writeFileSync(salida, JSON.stringify(estado)); }
      else {
        const r = await P.recorrerCategoria(page, base, total, salida, Math.max(1, restante()));
        estado = r.estado; if (!r.completo) completo = false;
      }
    }
    for (const it of estado.items) if (mapa.has(it.despacho)) pubs.push({ ...it, ciudad: mapa.get(it.despacho).ciudad, tipo: mapa.get(it.despacho).tipo });
  }
  // Detalle de cada publicación objetivo (reanudable).
  const fDet = path.join(a.out, 'detalles.json');
  const det = fs.existsSync(fDet) ? JSON.parse(fs.readFileSync(fDet, 'utf8')) : {};
  for (const p of pubs) {
    if (det[p.href]) continue;
    if (restante() <= 0) { completo = false; break; }
    try { det[p.href] = await P.detalle(page, p.href); } catch (e) { console.error('detalle falló:', p.titulo, e.message); continue; }
    fs.writeFileSync(fDet, JSON.stringify(det, null, 1));
  }
  const final = pubs.map(p => ({ ...p, ...(det[p.href] || {}) }));
  fs.writeFileSync(path.join(a.out, 'publicaciones.json'), JSON.stringify(final, null, 1));
  await browser.close();
  console.log(JSON.stringify({ completo, publicaciones: final.length, con_detalle: final.filter(x => x.docs).length, salida: path.join(a.out, 'publicaciones.json') }));
  if (!completo) console.error('INCOMPLETO: vuelva a ejecutar el mismo comando para continuar.');
})().catch(e => { console.error(e); process.exit(1); });
