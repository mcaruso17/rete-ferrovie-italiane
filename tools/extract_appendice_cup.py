"""CUP dei programmi: Appendice 2 alla Relazione Informativa dell'aggiornamento
Investimenti ("Dettaglio CUP riferiti ai programmi inseriti nelle tabelle").

Le Tabelle A e B scrivono sotto ogni intervento uno o pochi CUP. I programmi
(sicurezza in galleria, tecnologie per la circolazione, stazioni...) ne hanno
molti di piu', uno per direzione territoriale e per anno, e il contratto li
elenca solo qui, con la descrizione dell'oggetto: "Adeguamento sicurezza
gallerie tratta AV/AC Torino-Milano" sotto il programma A1004A.

Una riga e' "tabella classe intervento CUP descrizione". Quando la descrizione
va a capo, il CUP resta su una riga sua, sopra o sotto la riga del codice: lo
si riattacca alla riga del codice piu' vicina che ne e' senza.

Uso:
  python3 extract_appendice_cup.py appendice_2_lista_cup.pdf agg2025 ../data/appendice-cup-agg2025.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF                        # noqa: E402
from pdftext import extract_page, group_lines  # noqa: E402
from tables import raw_cells                   # noqa: E402

CUP = re.compile(r"\b([A-Z]\d{2}[A-Z]\d{11})\b")
RIGA = re.compile(r"^([AB])\s+(\d+)\s+([A-Z]{0,2}\d{3,4}(?:_?[A-Z0-9])?)\s*(.*)$")
TESTA = re.compile(r"Dettaglio CUP|TABELLA CLASSE|CUP DESCRIZIONE|^CDP CDP|^\d+$")


def main():
    pdf, doc_id, dest = sys.argv[1:4]
    doc = PDF(pdf)
    righe, sciolti, altro = [], [], []
    for n, pg in enumerate(doc.pages(), 1):
        linee = [" ".join(t for _a, _b, t, _i in raw_cells(ln)).strip()
                 for ln in group_lines(extract_page(doc, pg))]
        pagina = []
        for i, l in enumerate(linee):
            if not l or TESTA.search(l):
                continue
            m = RIGA.match(l)
            if m:
                tab, cl, cod, resto = m.groups()
                c = CUP.search(resto)
                cup = c.group(1) if c else None
                descr = (resto[:c.start()] + resto[c.end():]).strip() if c else resto.strip()
                pagina.append({"i": i, "tab": tab, "classe": cl, "codice": cod, "cup": cup,
                               "descr": descr, "p": n})
            elif CUP.fullmatch(l):
                sciolti.append((n, i, l))
            elif pagina:
                altro.append((n, i, l))
        # i CUP rimasti su una riga loro: alla riga del codice piu' vicina senza CUP
        for (pn, i, c) in [s for s in sciolti if s[0] == n]:
            libere = [r for r in pagina if r["cup"] is None]
            if libere:
                r = min(libere, key=lambda r: abs(r["i"] - i))
                r["cup"] = c
        # le righe di sola descrizione completano quella del codice piu' vicina
        for (pn, i, t) in [a for a in altro if a[0] == n]:
            if pagina:
                r = min(pagina, key=lambda r: abs(r["i"] - i))
                r["descr"] = (r["descr"] + " " + t).strip() if r["i"] < i else (t + " " + r["descr"]).strip()
        righe.extend(pagina)
    senza = [r for r in righe if not r["cup"]]
    for r in righe:
        r.pop("i", None)
    out = {"documento": os.path.basename(pdf), "doc": doc_id, "righe": righe}
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    testo = " ".join(" ".join(t for _a, _b, t, _i in raw_cells(ln))
                     for pg in doc.pages() for ln in group_lines(extract_page(doc, pg)))
    nel_pdf = set(CUP.findall(testo))
    letti = {r["cup"] for r in righe if r["cup"]}
    print("appendice CUP %s: %d righe, %d CUP distinti, %d programmi; CUP nel testo %d, "
          "non attribuiti %d, righe senza CUP %d"
          % (doc_id, len(righe), len(letti), len({r["codice"] for r in righe}),
             len(nel_pdf), len(nel_pdf - letti), len(senza)))


if __name__ == "__main__":
    main()
