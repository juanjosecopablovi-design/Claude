#!/usr/bin/env node
// Regenera config/despachos.json desde el selector de despachos de Publicaciones Procesales.
// Para agregar una ciudad, añádala a CIUDADES (código DANE de 5 dígitos) y ejecute:
//   node actualizar_despachos.js
const fs = require('fs');
const path = require('path');
const P = require('./portal');

const CIUDADES = {
  medellin: { nombre: 'Medellín', dane: '05001' },
  rionegro: { nombre: 'Rionegro', dane: '05615' },
  sabaneta: { nombre: 'Sabaneta', dane: '05631' },
  barbosa: { nombre: 'Barbosa', dane: '05079' },
  envigado: { nombre: 'Envigado', dane: '05266' },
  'la-estrella': { nombre: 'La Estrella', dane: '05380' },
  'puerto-boyaca': { nombre: 'Puerto Boyacá', dane: '15572' },
};
// Dígitos 6 a 9 del código del despacho: entidad y especialidad.
const TIPOS = {
  '3103': 'Civil del Circuito', '3112': 'Civil del Circuito', '3403': 'Civil del Circuito de Ejecución',
  '3189': 'Promiscuo del Circuito', '4003': 'Civil Municipal', '4303': 'Civil Municipal de Ejecución',
  '4189': 'Pequeñas Causas y Competencia Múltiple', '4089': 'Promiscuo Municipal',
  // Centros de servicios que publican por los juzgados civiles (Rionegro publica allí sus remates).
  '7172': 'Centro de Servicios', '7040': 'Centro de Servicios',
};

(async () => {
  const { browser, page } = await P.launch();
  await P.go(page, P.PORTAL, 5000);
  await page.waitForSelector('#despacho option:nth-child(100)', { state: 'attached', timeout: 90000 });
  const todos = await page.$$eval('#despacho option', os => os.map(o => [o.value.trim(), o.text.trim()]));
  await browser.close();
  const out = {
    _nota: 'Generado desde el selector de despachos de Publicaciones Procesales. Santa Elena es corregimiento de Medellín y la cubren los juzgados de Medellín. Regenerar con scripts/actualizar_despachos.js.',
    generado: new Date().toISOString().slice(0, 10), ciudades: {},
  };
  for (const [k, c] of Object.entries(CIUDADES)) {
    const despachos = todos.filter(([v]) => /^\d{12}$/.test(v) && v.startsWith(c.dane) && TIPOS[v.slice(5, 9)])
      .map(([v, t]) => ({ codigo: v, nombre: t.replace(/^\d{12}\s*-\s*/, ''), tipo: TIPOS[v.slice(5, 9)] }));
    out.ciudades[k] = { nombre: c.nombre, departamento: c.dane.slice(0, 2), dane: c.dane, despachos };
    console.error(`${c.nombre}: ${despachos.length} despachos`);
  }
  fs.writeFileSync(path.join(__dirname, '..', 'config', 'despachos.json'), JSON.stringify(out, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
