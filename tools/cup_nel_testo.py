"""Tutti i CUP scritti nel testo di ogni PDF dei contratti e degli allegati,
con documento e pagina: serve a dire se un CUP "e' nei documenti" anche quando
nessuna tabella estratta lo riporta (righe di programma, note, schede).
Il testo si legge due volte: com'e' e senza spazi, per i CUP spezzati.

Lenta (qualche minuto): build_all.sh la rilancia solo se manca l'uscita.

Uso:
  python3 cup_nel_testo.py ../data/cup-nel-testo.json
"""
import glob
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import raw_cells
CUP = re.compile(r"\b([A-Z]\d{2}[A-Z]\d{11})\b")
out = {}
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
files = sorted(glob.glob(os.path.join(BASE, '*.pdf'))) + sorted(glob.glob(os.path.join(BASE, 'documenti/*/*.pdf')))
for f in files:
    try:
        d = PDF(f); P = d.pages()
    except Exception as e:
        print('ERR', f, e); continue
    n = 0
    for i, pg in enumerate(P, 1):
        try:
            t = " ".join(" ".join(x for _a,_b,x,_i in raw_cells(ln)) for ln in group_lines(extract_page(d, pg)))
        except Exception as e:
            continue
        t2 = re.sub(r"\s+", "", t)
        for c in set(CUP.findall(t)) | set(CUP.findall(t2)):
            out.setdefault(c, []).append([os.path.relpath(f, BASE), i]); n += 1
    print(os.path.basename(f), len(P), 'pagine', n, 'occorrenze', flush=True)
json.dump(out, open(sys.argv[1], 'w'))
print('CUP distinti nel testo:', len(out))
