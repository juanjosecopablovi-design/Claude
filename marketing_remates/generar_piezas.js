const { chromium } = require('playwright-core');
const fs=require('fs');
const OUT='piezas/';
const fmt=n=>'$'+Math.round(n).toLocaleString('es-CO');
const FIRMA='NOMBRE DE LA FIRMA', WA='WhatsApp 300 000 0000';
const ICON={
 casa:'<path d="M12 60 L60 18 L108 60 V108 H12 Z" /><rect x="48" y="72" width="24" height="36"/>',
 apto:'<rect x="24" y="12" width="72" height="96" rx="4"/><path d="M40 30h12M68 30h12M40 50h12M68 50h12M40 70h12M68 70h12"/><rect x="50" y="88" width="20" height="20"/>',
 local:'<path d="M12 44 L22 16 H98 L108 44 Z"/><rect x="18" y="44" width="84" height="64"/><rect x="34" y="62" width="24" height="46"/><rect x="66" y="62" width="26" height="22"/>',
 lote:'<path d="M10 96 L40 60 L62 80 L84 50 L110 96 Z"/><path d="M10 104 H110" /><circle cx="88" cy="26" r="10"/>',
 carro:'<path d="M14 76 L26 46 Q30 38 40 38 H80 Q90 38 94 46 L106 76 V94 H14 Z"/><circle cx="36" cy="94" r="10"/><circle cx="84" cy="94" r="10"/><path d="M30 60 H90"/>',
 edificio:'<rect x="16" y="30" width="40" height="78"/><rect x="60" y="10" width="44" height="98"/><path d="M26 46h8M40 46h8M26 64h8M40 64h8M70 26h10M86 26h10M70 44h10M86 44h10M70 62h10M86 62h10M70 80h10M86 80h10"/>'
};
const css=`*{box-sizing:border-box;margin:0;padding:0}body{width:1080px;height:1350px;font-family:'Montserrat',Arial,sans-serif;background:#0f1f3a;color:#f5efe2;overflow:hidden}
.w{position:relative;width:1080px;height:1350px;padding:80px 84px;display:flex;flex-direction:column}
.bar{height:6px;width:120px;background:#c9a24a;margin:28px 0}
.kick{font-size:28px;letter-spacing:6px;text-transform:uppercase;color:#c9a24a;font-weight:600}
h1{font-family:'Playfair Display',Georgia,serif;font-size:76px;line-height:1.06;font-weight:700}
h2{font-family:'Playfair Display',Georgia,serif;font-size:58px;line-height:1.1}
.sub{font-size:32px;line-height:1.45;color:#d9d2c3;margin-top:18px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:30px}
.cell{background:#162b4f;border:1px solid #2a4372;border-radius:18px;padding:26px 28px}
.lab{font-size:22px;letter-spacing:3px;text-transform:uppercase;color:#9fb0cc}
.val{font-size:44px;font-weight:700;margin-top:8px;color:#fff}
.val.g{color:#e3c27a}
.foot{position:absolute;left:84px;right:84px;bottom:64px;display:flex;justify-content:space-between;align-items:flex-end;border-top:1px solid #2a4372;padding-top:26px}
.firm{font-size:24px;font-weight:700;letter-spacing:3px;white-space:nowrap}
.firm small{display:block;white-space:nowrap;font-size:19px;font-weight:500;letter-spacing:2px;color:#9fb0cc;margin-top:6px}
.legal{font-size:18px;color:#8d9bb5;line-height:1.4;max-width:500px;text-align:right}
.icon{width:150px;height:150px}
.icon svg{width:150px;height:150px;fill:none;stroke:#c9a24a;stroke-width:4;stroke-linejoin:round;stroke-linecap:round}
.steps{margin-top:46px;display:flex;flex-direction:column;gap:26px}
.step{display:flex;gap:28px;align-items:flex-start}
.num{flex:0 0 76px;height:76px;border-radius:50%;background:#c9a24a;color:#0f1f3a;font-size:38px;font-weight:800;display:flex;align-items:center;justify-content:center}
.step p{font-size:32px;line-height:1.4}.step b{color:#e3c27a}
.row{display:flex;justify-content:space-between;align-items:center;padding:22px 0;border-bottom:1px solid #2a4372;font-size:30px}
.row b{font-size:40px;color:#e3c27a}
.date{display:inline-block;background:#c9a24a;color:#0f1f3a;font-weight:800;font-size:34px;padding:14px 26px;border-radius:12px;margin-top:30px}
.tag{font-size:24px;color:#9fb0cc;margin-top:18px}
.list .row{font-size:24px;padding:10px 0}.list .row span:last-child{color:#e3c27a;font-weight:700}
`;
const head=`<html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&family=Playfair+Display:wght@700&display=swap" rel="stylesheet"><style>${css}</style></head><body><div class="w">`;
const foot=(legal)=>`<div class="foot"><div class="firm">${FIRMA}<small>Abogados · Medellín · ${WA}</small></div><div class="legal">${legal}</div></div></div></body></html>`;
const LEG_REM='Información pública de la Rama Judicial (Publicaciones Procesales). No es oferta de venta. Verifique el expediente antes de consignar.';
const pieces=[];
// Servicio 1: institucional (art. 31 Ley 1123)
pieces.push(['S1_institucional',head+`<div class="kick">Abogados</div><div class="bar"></div><h1>Asesoría jurídica en remates judiciales</h1><p class="sub">Atendemos con preferencia la compra de inmuebles y vehículos en subastas judiciales: estudio del expediente, documentos de postura y trámite hasta la entrega.</p><div class="grid"><div class="cell"><div class="lab">Asuntos</div><div class="val" style="font-size:34px">Remates de inmuebles y vehículos</div></div><div class="cell"><div class="lab">Oficina</div><div class="val" style="font-size:34px">Medellín, Antioquia</div></div><div class="cell"><div class="lab">Equipo</div><div class="val" style="font-size:34px">Abogados titulados</div></div><div class="cell"><div class="lab">Contacto</div><div class="val" style="font-size:34px">${WA.replace('WhatsApp ','')}</div></div></div>`+foot('Tarjeta profesional N.° [número] · Dirección de la oficina [dirección]')]);
// Servicio 2: educativo pasos
pieces.push(['S2_como_funciona',head+`<div class="kick">Guía rápida</div><div class="bar"></div><h1>Cómo se compra en un remate judicial</h1><div class="steps">
<div class="step"><div class="num">1</div><p><b>Revise el auto</b> que fija la fecha: bien, avalúo, hora y juzgado.</p></div>
<div class="step"><div class="num">2</div><p><b>Estudie el expediente</b> y el certificado de tradición antes de ofertar.</p></div>
<div class="step"><div class="num">3</div><p><b>Consigne el 40 % del avalúo</b> y presente la oferta en sobre cerrado.</p></div>
<div class="step"><div class="num">4</div><p>Si gana, pague <b>el saldo y el 5 % de impuesto en 5 días</b>.</p></div></div>`+foot('Código General del Proceso, arts. 451 a 453; Ley 1743 de 2014, art. 12.')]);
// Servicio 3: costos
pieces.push(['S3_cuanto_cuesta',head+`<div class="kick">Antes de ofertar</div><div class="bar"></div><h1>Lo que paga además del precio</h1><p class="sub">Ejemplo: bien avaluado en $1.000 millones, adjudicado por la postura mínima.</p><div style="margin-top:34px">
<div class="row"><span>Depósito para ofertar (40 % del avalúo)</span><b>$400 M</b></div>
<div class="row"><span>Precio mínimo (70 % del avalúo)</span><b>$700 M</b></div>
<div class="row"><span>Impuesto de remate (5 % del precio)</span><b>$35 M</b></div>
<div class="row"><span>Registro (0,5 % a 1 % según ordenanza)</span><b>$3,5–7 M</b></div>
<div class="row" style="border:none"><span>Plazo para pagar saldo e impuesto</span><b>5 días</b></div></div>`+foot('Ley 1743 de 2014, art. 12; CGP arts. 451 y 453; Ley 223 de 1995, art. 230. Ejemplo ilustrativo.')]);
// Remates
const R=[
 ['2026-09-29','10:00 a.m.','3.º','013-2024-00112','casa','Casa con lote','Calle 12 # 43B-32, Medellín',1477239364],
 ['2026-10-01','9:00 a.m.','2.º','013-2023-00363','local','Local comercial','Int. 241, C.C. Obelisco, Cra. 74 # 48-37',295761648],
 ['2026-10-02','10:00 a.m.','1.º','003-2021-00014','apto','Apartamento + 2 parqueaderos','Arrayanes de La Calera, Calle 6A # 16-15',2053303500],
 ['2026-10-20','10:00 a.m.','4.º','017-2020-00146','casa','Inmueble','Calle 62 # 48-24, Medellín',1346047500],
 ['2026-10-27','10:00 a.m.','3.º','014-2015-00186','lote','Lote de 1.024 m²','Barrio Miraflores, Medellín',1837530000],
 ['2026-10-27','10:00 a.m.','4.º','004-2017-00358','carro','Toyota Hilux 2017','Placa INQ 791',105300000],
 ['2026-10-29','9:00 a.m.','2.º','011-2015-00500','apto','Dos inmuebles','Arboleda del Rodeo, Calle 9 Sur # 79C-115',430505250],
 ['2026-11-05','9:00 a.m.','2.º','001-2002-00335','edificio','Inmueble','Cra. 46 # 40-74, Medellín',1867369500],
 ['2026-11-10','9:00 a.m.','2.º','003-2023-00209','carro','BMW 125i 2022','Placa LCV852',168940000],
 ['2026-11-19','9:00 a.m.','2.º','013-2021-00018','carro','Audi Q5 2010','Placa RAS044',48670000],
 ['2026-11-24','9:00 a.m.','2.º','018-2023-00230','apto','Apto + parqueadero + útil','Poblado de San Diego, Calle 29 # 41-98',686094309.97],
];
const M=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
const dd=s=>{const [y,m,d]=s.split('-');return `${+d} ${M[+m-1]} ${y}`;};
R.forEach((r,i)=>{const [f,h,j,rad,ic,t,u,av]=r;
 pieces.push([`R${String(i+1).padStart(2,'0')}_${f}_${rad}`,head+`<div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div class="kick">Remate judicial</div><div class="bar"></div></div><div class="icon"><svg viewBox="0 0 120 120">${ICON[ic]}</svg></div></div><h1 style="font-size:62px">${t}</h1><p class="sub">${u}</p><div class="date">${dd(f)} · ${h}</div><div class="grid">
<div class="cell"><div class="lab">Avalúo</div><div class="val">${fmt(av)}</div></div>
<div class="cell"><div class="lab">Postura mínima 70 %</div><div class="val g">${fmt(av*0.7)}</div></div>
<div class="cell"><div class="lab">Depósito 40 %</div><div class="val">${fmt(av*0.4)}</div></div>
<div class="cell"><div class="lab">Despacho</div><div class="val" style="font-size:30px">Juzgado ${j} Civil del Circuito de Ejecución</div></div></div>
<p class="tag">Radicado 05001 31 03 ${rad.replace(/-/g,' ')} 00 · Diligencia virtual · Posturas presenciales, Edificio Edatel</p><div class="cell" style="margin-top:26px;padding:20px 26px;background:none;border-color:#c9a24a"><div class="lab" style="color:#c9a24a">Para participar</div><p style="font-size:24px;line-height:1.45;margin-top:8px">Consigne el 40 % del avalúo y entregue la oferta en sobre cerrado. Si gana, pague el saldo y el 5 % de impuesto de remate dentro de los 5 días siguientes.</p></div>`+foot(LEG_REM)]);
});
// Palmas
pieces.push(['R12_2026-10-06_009-2017-00393',head+`<div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div class="kick">Remate judicial</div><div class="bar"></div></div><div class="icon"><svg viewBox="0 0 120 120">${ICON.edificio}</svg></div></div><h1 style="font-size:56px">10 apartamentos y 12 parqueaderos de moto</h1><p class="sub">Edificio Palmas de San Judas, Cra. 69 # 97-131, Medellín</p><div class="date">6 y 13 oct 2026 · 10 a.m. y 2 p.m.</div><div class="grid">
<div class="cell"><div class="lab">Aptos, avalúo c/u</div><div class="val" style="font-size:36px">$160,5 a $179,5 M</div></div>
<div class="cell"><div class="lab">Postura mínima apto</div><div class="val g" style="font-size:36px">desde $112,4 M</div></div>
<div class="cell"><div class="lab">Parqueadero moto</div><div class="val" style="font-size:36px">$5.312.000</div></div>
<div class="cell"><div class="lab">Despacho</div><div class="val" style="font-size:30px">Juzgado 4.º Civil del Circuito de Ejecución</div></div></div>
<p class="tag">Radicado 05001 31 03 009 2017 00393 00 · Cuatro diligencias por lotes</p><div class="cell" style="margin-top:26px;padding:20px 26px;background:none;border-color:#c9a24a"><div class="lab" style="color:#c9a24a">Para participar</div><p style="font-size:24px;line-height:1.45;margin-top:8px">Consigne el 40 % del avalúo y entregue la oferta en sobre cerrado. Si gana, pague el saldo y el 5 % de impuesto de remate dentro de los 5 días siguientes.</p></div>`+foot(LEG_REM)]);
// Boletín
const rows=[...R.slice(0,3).map(r=>[r[0],r[5]]),['2026-10-06','10 aptos + 12 parq. moto (Palmas de San Judas)'],...R.slice(3).map(r=>[r[0],r[5]])];
pieces.push(['R00_boletin_semana',head+`<div class="kick">Boletín de remates · Medellín</div><div class="bar"></div><h2 style="font-size:52px">Remates judiciales con fecha fijada</h2><p class="sub" style="font-size:28px">Juzgados Civiles del Circuito de Ejecución de Sentencias · actualizado 26 sep 2026</p><div class="list" style="margin-top:26px">`+rows.map(r=>`<div class="row"><span>${dd(r[0])}</span><span style="flex:1;margin-left:26px">${r[1]}</span></div>`).join('')+`</div>`+foot(LEG_REM)]);
(async()=>{
 const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',args:['--no-sandbox','--disable-http2'],proxy:{server:process.env.HTTPS_PROXY}});
 const p=await b.newPage({viewport:{width:1080,height:1350},ignoreHTTPSErrors:true});
 for(const [n,html] of pieces){ fs.writeFileSync(OUT+n+'.html',html); await p.setContent(html,{waitUntil:'networkidle',timeout:60000}).catch(()=>{}); await p.waitForTimeout(800); const ov=await p.evaluate(()=>{const f=document.querySelector('.foot').getBoundingClientRect().top;let m=0;document.querySelectorAll('.w > *:not(.foot)').forEach(e=>{m=Math.max(m,e.getBoundingClientRect().bottom)});return Math.round(f-m)}); if(ov<10) console.log('OVERLAP',n,ov); await p.screenshot({path:OUT+n+'.png'}); console.log(n);}
 await b.close();})();
