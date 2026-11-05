#!/usr/bin/env python3
"""Descarga los autos que fijan fecha de remate y extrae sus datos.

Uso:
  python3 -I analizar_autos.py --out DIR [--hoy 2026-11-05]

Lee DIR/publicaciones.json (de buscar_remates.js), descarga cada auto a DIR/autos/,
extrae el texto y escribe:
  DIR/autos.json    todos los autos con los datos extraídos
  DIR/remates.csv   una fila por auto
  DIR/vigentes.md   tabla de remates con fecha igual o posterior a --hoy, tomando
                    el auto más reciente de cada radicado
Los datos extraídos son una ayuda: verifique siempre contra el PDF.
"""
import argparse, csv, datetime as dt, json, os, re, subprocess, sys, unicodedata, urllib.parse

try:
    import pypdfium2 as pdfium
except ImportError:
    sys.exit('Falta pypdfium2: ejecute scripts/setup.sh')

MESES = {m: i + 1 for i, m in enumerate(
    'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split())}
MESES['setiembre'] = 9
DIAS = r'(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)'


def sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def texto_pdf(ruta):
    try:
        doc = pdfium.PdfDocument(ruta)
        t = '\n'.join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
        return re.sub(r'\s+', ' ', t), len(doc)
    except Exception as e:  # PDF dañado o escaneado
        return '', -1


# Fecha escrita: "martes seis (06) de octubre de dos mil veintiseis (2026)", "29 de septiembre de 2026"
RE_FECHA = re.compile(
    r'(' + DIAS + r'[\s,]*)?(?:[a-z]+\s*)?\(?(\d{1,2})[°ºo]?\)?\s*(?:\(\s*\d{1,2}[°ºo]?\s*\))?\s+de\s+(' + '|'.join(MESES) +
    r')\s+(?:de|del)\s+(?:[a-z ]+\()?\s*(\d{4})\)?')
RE_NUM = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')
RE_HORA = re.compile(r'(\d{1,2})[:.](\d{2})\s*([ap])\.?\s*m', re.I)


def fechas(t):
    out = []
    for m in RE_FECHA.finditer(t):
        try:
            f = dt.date(int(m.group(4)), MESES[m.group(3)], int(m.group(2)))
        except ValueError:
            continue
        out.append((m.start(), f, bool(m.group(1))))
    return out


def extraer(t):
    tl = sin_tildes(t.lower())
    r = {}
    fs = fechas(tl)
    # Fecha del auto: primera fecha del encabezado sin día de la semana.
    cab = [f for p, f, wd in fs if p < 1500 and not wd]
    r['fecha_auto'] = cab[0].isoformat() if cab else None
    # Fecha del remate, por orden de confianza:
    # 1) "fija fecha de remate ... dd/mm/aaaa" en el asunto;
    # 2) la primera fecha precedida de "se fija / señala / para el día / nueva fecha..." en contexto de remate;
    # 3) la primera fecha con día de la semana (que no sea la fecha de envío de un correo);
    # 4) la primera fecha después de "fija fecha de remate".
    fr, pos = None, None
    m = re.search(r'fija(?:r)? fecha(?: de)? remate[^.]{0,60}?(\d{1,2})/(\d{1,2})/(\d{4})', tl)
    if m:
        try:
            fr, pos = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))), m.end()
        except ValueError:
            pass
    correo = lambda p_: re.search(r'(enviado|fecha|recibido|sent|date)\s*:?\s*$', tl[max(0, p_ - 25):p_])
    if not fr:
        fuerte = r'(nueva fecha|se fija|fija(?:r)? como|fijar? para|para el dia|senala(?:r)?(?: como| para| el)|se cita|se llevara a cabo|tendra lugar)'
        debil = r'(fij\w*|senal\w*|realizara|llevara a cabo)'
        ctx = lambda p_: re.search(r'remate|licitacion|almoneda|subasta|diligencia|audiencia', tl[max(0, p_ - 700):p_])
        for trig, ventana in ((fuerte, 120), (debil, 220)):
            for p_, f, w in fs:
                if re.search(trig, tl[max(0, p_ - ventana):p_]) and ctx(p_) and not correo(p_):
                    fr, pos = f, p_
                    break
            if fr:
                break
    if not fr:
        wd = [(p_, f) for p_, f, w in fs if w and not correo(p_)]
        if wd:
            pos, fr = wd[0][0], wd[0][1]
    if not fr:
        m = re.search(r'fija(?:r)? fecha(?: de)? remate', tl)
        if m:
            later = [(p_, f) for p_, f, w in fs if p_ > m.start()]
            if later:
                pos, fr = later[0]
    r['fecha_remate'] = fr.isoformat() if fr else None
    if pos is not None:
        h = RE_HORA.search(tl, pos, pos + 200)
        r['hora'] = f"{int(h.group(1))}:{h.group(2)} {h.group(3)}.m." if h else None
    else:
        r['hora'] = None
    # Radicado de 23 dígitos.
    rad = None
    for m in re.finditer(r'(?:radicad[oa]|rad\.?|rdo\.?)\s*(?:no\.?|n°|nro\.?)?\s*:?\s*([\d][\d \-]{18,40}\d)', tl):
        dig = re.sub(r'\D', '', m.group(1))
        if len(dig) >= 23:
            rad = dig[:23]
            break
    r['radicado'] = rad
    # Partes (datos personales: no usar en publicidad).
    m = re.search(r'demandante\(?s?\)?\s*:?\s*(.{3,160}?)\s+(?:cesionari|demandad|ddo)', tl)
    r['demandante'] = t[m.start(1):m.end(1)].strip() if m else None
    m = re.search(r'demandad[oa]\(?s?\)?\s*:?\s*(.{3,200}?)\s+(?:asunto|nuevo demandado|auto|ref|providencia)', tl)
    r['demandado'] = t[m.start(1):m.end(1)].strip() if m else None
    # Avalúos.
    av = []
    for m in re.finditer(r'avalua\w*[^$]{0,220}\$\s?([\d.,´\']{5,})', tl):
        dig = re.sub(r'[^\d,]', '', m.group(1)).split(',')[0]
        if dig.isdigit() and int(dig) > 1_000_000:
            av.append(int(dig))
    r['avaluos'] = sorted(set(av), key=av.index)
    # Bienes.
    mats = set()
    for m in re.finditer(r'matricula|folio', tl):
        for x in re.findall(r'\b(\d{3}|\d{2}[a-z])\s?-\s?(\d{3,8})\b', tl[m.end(): m.end() + 120]):
            mats.add((x[0] + '-' + x[1]).upper())
    r['matriculas'] = sorted(mats)
    r['placas'] = sorted(set(re.sub(r'[\s-]', '', x).upper() for x in re.findall(
        r'placas?\s*(?:no\.?|n°)?\s*([a-z]{3}\s?-?\s?\d{2,3}[a-z]?)\b', tl)))
    m = re.search(r'respecto (?:del?|de los|al)\s', tl)
    r['bien'] = t[m.start(): m.start() + 320].strip() if m else None
    r['virtual'] = 'teams' in tl or 'virtual' in tl
    ini = tl[:1500]
    if re.search(r'acta de (la )?(audiencia|diligencia) de remate|diligencia de remate dentro del proceso|da apertura a la diligencia', ini):
        r['tipo_doc'] = 'acta'
        r['resultado'] = 'desierta' if 'desiert' in tl else ('adjudicado' if re.search(r'adjudic|mejor postor', tl) else None)
    elif re.search(r'constancia secretarial', ini):
        r['tipo_doc'] = 'constancia'
    elif re.search(r'memorial|outlook|me permito allegar|aporta(r)? (la )?publicacion', ini[:400]):
        r['tipo_doc'] = 'memorial'
    else:
        r['tipo_doc'] = 'auto'
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--hoy', default=dt.date.today().isoformat())
    a = ap.parse_args()
    pubs = json.load(open(os.path.join(a.out, 'publicaciones.json'), encoding='utf-8'))
    os.makedirs(os.path.join(a.out, 'autos'), exist_ok=True)
    autos, vistos = [], set()
    for p in pubs:
        docs = [d for d in (p.get('docs') or []) if not d.get('protocolo')]
        base = {
            'ciudad': p.get('ciudad'), 'despacho': p.get('despacho'), 'despacho_nombre': p.get('despacho_nombre'),
            'publicacion': p.get('titulo'), 'fecha_publicacion': p.get('fecha_publicacion'),
            'pagina_publicacion': p.get('href'), 'resumen': p.get('resumen'),
            'expediente': p.get('sharepoint') or next((x['url'] for x in p.get('enlaces') or [] if x['tipo'] != 'audiencia'), None),
            'audiencia': next((x['url'] for x in p.get('enlaces') or [] if x['tipo'] == 'audiencia'), None),
        }
        rad_pub = re.sub(r'\D', '', p.get('radicado_publicacion') or '')
        if not docs:  # Publicación sin PDF: se usa el resumen.
            x = {}
            if p.get('resumen'):
                rl = sin_tildes(p['resumen'].lower())
                fr_ = fechas(rl)
                if fr_:
                    h = RE_HORA.search(rl, fr_[0][0])
                    x = {'fecha_remate': fr_[0][1].isoformat(), 'hora': f"{int(h.group(1))}:{h.group(2)} {h.group(3)}.m." if h else None,
                         'fuente_fecha': 'resumen de la publicación'}
            autos.append({**base, 'auto_url': p.get('href'), 'archivo': None, 'paginas_pdf': 0, 'sin_texto': True, **x,
                          'radicado': x.get('radicado') or (rad_pub[:23] if len(rad_pub) >= 23 else None)})
            continue
        for d in docs:
            url = d['url'] if 'get_file' in d['url'] else d['url'].split('?')[0]
            if url in vistos:
                continue
            vistos.add(url)
            if 'get_file' in url:
                nombre = (d.get('texto') or 'documento') + '_' + re.search(r'uuid=([\w-]{8})', url).group(1)
            else:
                nombre = urllib.parse.unquote(url.rstrip('/').split('/')[-2] if url.count('/') > 6 else url.split('/')[-1])
            nombre = re.sub(r'[^A-Za-z0-9._-]', '_', nombre)[:150]
            if not nombre.lower().endswith('.pdf'):
                nombre += '.pdf'
            ruta = os.path.join(a.out, 'autos', nombre)
            if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
                subprocess.run(['curl', '-sS', '-L', '-m', '120', '-o', ruta, d['url']], check=False)
            t, pags = texto_pdf(ruta)
            x = extraer(t) if t else {}
            # Si el PDF no dice la fecha (escaneado), se intenta con el resumen de la publicación.
            if p.get('resumen') and (not x.get('fecha_remate') or x.get('tipo_doc') == 'memorial'):
                # En el resumen, la fecha que aparece es la del remate.
                rl = sin_tildes(p['resumen'].lower())
                fr_ = fechas(rl)
                if fr_:
                    h = RE_HORA.search(rl, fr_[0][0])
                    x['fecha_remate'] = fr_[0][1].isoformat()
                    x['hora'] = f"{int(h.group(1))}:{h.group(2)} {h.group(3)}.m." if h else None
                    x['fuente_fecha'] = 'resumen de la publicación'
            if x.get('tipo_doc') == 'memorial' and not x.get('fuente_fecha'):
                x['fuente_fecha'] = 'memorial de parte: confirmar con el auto'
            if not x.get('radicado') and len(rad_pub) >= 23:
                x['radicado'] = rad_pub[:23]
            autos.append({**base, 'documento': d.get('texto'), 'auto_url': url, 'archivo': ruta, 'paginas_pdf': pags,
                          'sin_texto': not t, **x})
            print(f"{p.get('fecha_publicacion')} | {nombre[:60]} | remate {x.get('fecha_remate')} {x.get('hora')}", file=sys.stderr)
    json.dump(autos, open(os.path.join(a.out, 'autos.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    campos = ['ciudad', 'despacho', 'despacho_nombre', 'radicado', 'fecha_auto', 'fecha_publicacion', 'fecha_remate', 'hora',
              'avaluos', 'matriculas', 'placas', 'bien', 'demandante', 'demandado', 'expediente', 'audiencia', 'resumen',
              'documento', 'tipo_doc', 'resultado', 'fuente_fecha', 'auto_url', 'archivo', 'sin_texto']
    with open(os.path.join(a.out, 'remates.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        for x in autos:
            w.writerow({k: (', '.join(map(str, x[k])) if isinstance(x.get(k), list) else x.get(k)) for k in campos})
    # Vigentes: el auto más reciente por radicado (o por archivo si no hay radicado) con fecha >= hoy.
    ult = {}
    for x in autos:
        clave = x.get('radicado') or x['auto_url']
        orden = (x.get('fecha_publicacion') or '', x.get('fecha_auto') or '', x.get('fecha_remate') or '')
        if clave not in ult or orden >= ult[clave][0]:
            ult[clave] = (orden, x)
    vig = sorted([x for _, x in ult.values() if x.get('fecha_remate') and x['fecha_remate'] >= a.hoy and x.get('tipo_doc') != 'acta'],
                 key=lambda x: (x['fecha_remate'], x.get('hora') or ''))
    revisar = [x for x in autos if not x.get('fecha_remate') and x.get('tipo_doc') != 'acta']
    actas = [x for x in autos if x.get('tipo_doc') == 'acta']
    with open(os.path.join(a.out, 'vigentes.md'), 'w', encoding='utf-8') as f:
        f.write(f'# Remates vigentes al {a.hoy}\n\n{len(vig)} remates pendientes de {len(autos)} autos revisados.\n\n')
        f.write('| Fecha | Hora | Ciudad | Despacho | Radicado | Bien | Avalúo | Auto | Expediente | Nota |\n|---|---|---|---|---|---|---|---|---|---|\n')
        for x in vig:
            bien = ', '.join(x.get('matriculas') or []) or ', '.join(x.get('placas') or []) or (x.get('bien') or '')[:80]
            av = ', '.join(f"${v:,.0f}".replace(',', '.') for v in (x.get('avaluos') or [])[:3])
            f.write(f"| {x['fecha_remate']} | {x.get('hora') or ''} | {x.get('ciudad') or ''} | {x.get('despacho_nombre') or x.get('despacho')} | "
                    f"{x.get('radicado') or ''} | {bien} | {av} | [{'PDF' if x.get('archivo') else 'Publicación'}]({x['auto_url']}) | "
                    f"{'[Ver](' + x['expediente'] + ')' if x.get('expediente') else ''} | {x.get('fuente_fecha') or ''} |\n")
        if actas:
            f.write(f'\n## Actas de remate publicadas ({len(actas)})\n\n')
            for x in actas:
                f.write(f"- {x.get('fecha_publicacion')} — {x.get('despacho_nombre')} — {x.get('radicado') or ''} — "
                        f"resultado: {x.get('resultado') or 'ver acta'} — [PDF]({x['auto_url']})\n")
        if revisar:
            f.write(f'\n## Autos sin fecha detectada ({len(revisar)}): revisar a mano\n\n')
            for x in revisar:
                exp = f" — [expediente]({x['expediente']})" if x.get('expediente') else ''
                f.write(f"- {x.get('fecha_publicacion')} — {x.get('despacho_nombre')} — {x.get('publicacion')} — [{'PDF' if x.get('archivo') else 'publicación'}]({x['auto_url']}){exp}"
                        f"{' (escaneado o sin PDF)' if x.get('sin_texto') else ''}\n")
    print(json.dumps({'autos': len(autos), 'vigentes': len(vig), 'sin_fecha': len(revisar),
                      'tabla': os.path.join(a.out, 'vigentes.md')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
