#!/usr/bin/env python3
"""Busca un proceso dentro de los documentos de un despacho.

Uso:
  python3 -I grep_radicado.py --out DIR --radicado 50573318900220180003700 [--palabras "Lelio,Revancha"]

Lee DIR/publicaciones.json (de buscar_proceso.js o micrositio.py), descarga los PDF a DIR/docs/
y busca el radicado en sus formas habituales (23 dígitos con o sin espacios, "2018-00037",
"2018 00037", "201800037") y las palabras adicionales. Escribe DIR/hallazgos.md.
Reanudable: los PDF ya descargados no se vuelven a bajar.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.parse

try:
    import pypdfium2 as pdfium
except ImportError:
    sys.exit('Falta pypdfium2: ejecute scripts/setup.sh')


def patrones(rad, palabras):
    d = re.sub(r'\D', '', rad)
    pats = []
    if len(d) == 23:
        anio, num = d[12:16], d[16:21]
        sep = r'[\s\-_.+]*'
        pats.append(sep.join(d))  # 23 dígitos con cualquier separador
        pats.append(anio + sep + r'0*' + str(int(num)) + r'(?!\d)')  # 2018-00037 / 2018 37
        pats.append(anio + num)
    else:
        pats.append(re.escape(rad))
    pats += [re.escape(p.strip()) for p in palabras if p.strip()]
    return re.compile('|'.join(pats), re.I)


def texto(ruta):
    try:
        doc = pdfium.PdfDocument(ruta)
        return re.sub(r'\s+', ' ', '\n'.join(doc[i].get_textpage().get_text_range() for i in range(len(doc))))
    except Exception:
        return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--radicado', required=True)
    ap.add_argument('--palabras', default='')
    ap.add_argument('--max-min', type=float, default=8)
    a = ap.parse_args()
    t0 = time.time()
    pat = patrones(a.radicado, a.palabras.split(','))
    pubs = json.load(open(os.path.join(a.out, 'publicaciones.json'), encoding='utf-8'))
    os.makedirs(os.path.join(a.out, 'docs'), exist_ok=True)
    hall, vistos, pend = [], set(), 0
    for p in pubs:
        for d in p.get('docs') or []:
            url = d['url'] if d['url'].startswith('http') else 'https://www.ramajudicial.gov.co' + d['url']
            if url in vistos:
                continue
            vistos.add(url)
            if 'get_file' in url:
                uid = re.search(r'uuid=([\w-]{8})', url)
                bruto = (d.get('texto') or 'documento') + '_' + (uid.group(1) if uid else str(len(vistos)))
            else:
                bruto = urllib.parse.unquote(url.split('/documents/')[-1].split('?')[0])
            nombre = re.sub(r'[^A-Za-z0-9._-]', '_', bruto)[-160:]
            if not nombre.lower().endswith('.pdf'):
                nombre += '.pdf'
            ruta = os.path.join(a.out, 'docs', nombre)
            # El nombre del archivo a veces ya identifica el proceso.
            en_nombre = bool(pat.search(urllib.parse.unquote(url)) or pat.search(d.get('texto', '')))
            if not os.path.exists(ruta):
                if (time.time() - t0) / 60 > a.max_min:
                    pend += 1
                    continue
                subprocess.run(['curl', '-sS', '-L', '-m', '120', '-A', 'Mozilla/5.0', '-o', ruta, url], check=False)
            t = texto(ruta)
            ms = list(pat.finditer(t))
            if ms or en_nombre:
                ctx = [t[max(0, m.start() - 250): m.start() + 450] for m in ms[:2]]
                hall.append({'publicacion': p.get('titulo'), 'fecha': p.get('fecha_publicacion'), 'categoria': p.get('categoria'),
                             'url': url, 'archivo': ruta, 'sin_texto': not t, 'contexto': ctx})
                print(f"HALLAZGO {p.get('fecha_publicacion')} | {p.get('titulo')} | {nombre[:70]}", file=sys.stderr)
    hall.sort(key=lambda h: h.get('fecha') or '')
    with open(os.path.join(a.out, 'hallazgos.md'), 'w', encoding='utf-8') as f:
        f.write(f'# Proceso {a.radicado}: {len(hall)} documentos encontrados\n\n')
        for h in hall:
            f.write(f"## {h.get('fecha') or ''} — {h.get('publicacion') or ''}\n\n[{h['archivo'].split('/')[-1]}]({h['url']})"
                    f"{' (escaneado, sin texto: revisar a mano)' if h['sin_texto'] else ''}\n\n")
            for c in h['contexto']:
                f.write(f'> …{c}…\n\n')
    print(json.dumps({'documentos_revisados': len(vistos) - pend, 'pendientes': pend, 'hallazgos': len(hall),
                      'informe': os.path.join(a.out, 'hallazgos.md')}, ensure_ascii=False))
    if pend:
        print('INCOMPLETO: vuelva a ejecutar el mismo comando para continuar.', file=sys.stderr)


if __name__ == '__main__':
    main()
