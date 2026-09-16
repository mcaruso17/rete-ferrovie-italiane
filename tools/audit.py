"""Cerca pagine che contengono dati tabellari ma non sono state riconosciute.

Una tabella si riconosce dall'intestazione, e le intestazioni nei Contratti non
sono uniformi: alcune pagine proseguono senza ripetere il titolo, altre lo
scrivono con i due punti invece del trattino. Questo controllo non si fida del
titolo: conta quante righe di ogni pagina hanno almeno tre celle numeriche, e
segnala quelle che ne hanno parecchie pur risultando senza tabella.

Uso:  python3 audit.py <file.pdf> <id_documento> <uscita.json>
"""
import sys, os, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import raw_cells, is_num
from extract import table_kind, head_text, norm
path, doc_id, out = sys.argv[1], sys.argv[2], sys.argv[3]
d=PDF(path); pgs=d.pages()
res=[]
for i,p in enumerate(pgs):
    try: lines=group_lines(extract_page(d,p))
    except Exception: lines=[]
    k=table_kind(head_text(lines))
    nrighe_dati=0; ncelle_num=0; prima=""
    for l in lines:
        cs=raw_cells(l)
        n=sum(1 for c in cs if is_num(c[2]))
        ncelle_num+=n
        if n>=3: nrighe_dati+=1
    for l in lines[:4]:
        t=norm("".join(x.text for x in l))
        if len(t)>10: prima=t[:70]; break
    res.append({"pag":i+1,"kind":k,"righe_dati":nrighe_dati,
                "celle_num":ncelle_num,"titolo":prima})
json.dump({"doc":doc_id,"pagine":res}, open(out,'w'), ensure_ascii=False)
print("%-9s %3d pagine analizzate"%(doc_id,len(res)))
