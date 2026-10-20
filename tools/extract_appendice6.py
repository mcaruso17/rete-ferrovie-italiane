"""Appendice 6 alla Relazione Informativa dell'aggiornamento 2025:
"Aggiornamento relazione interventi DL 43/2013". La tabella a p. 4 elenca gli
interventi finanziati dal DL 43/2013 con CUP, riga del CdP-I, costo totale,
risorse (di cui Stato DL 43/2013 e altro) e il piano delle contabilizzazioni
(al 2023, 2024, 2025 e oltre).

Due righe hanno due CUP sulla stessa riga di importi (Velocizzazione
Venezia-Trieste, J37E13000300001 e J37E13000330001; Sempione,
J47I05000020001 e J37I05000020001): gli importi sono della riga, e si
ripetono sui due CUP con l'avvertenza. Controllo: le righe sommano al Totale.

Uso:
  python3 extract_appendice6.py ../documenti/cdpi-agg2025/appendice_6_agg_relazione_interventi_dl_43_2013.pdf \\
          ../data/appendice6-agg2025.json
"""
import json
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import to_float

RE_CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
RE_NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
NUMERI = ["costo_totale", "risorse", "risorse_stato_dl43_2013", "risorse_altro",
          "contabilizzato_al_2023", "contabilizzazioni_2024", "contabilizzazioni_2025_e_oltre"]


def main():
    pdf, out = sys.argv[1], sys.argv[2]
    doc = PDF(pdf)
    righe, totale = [], None
    for n, pg in enumerate(doc.pages(), 1):
        linee = []
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            linee.append((it[0].y, parole(it)))
        ancore = {}
        for y, w in linee:
            nums = [t for x, t, _ in w if x > 300 and RE_NUM.match(t)]
            if len(nums) == len(NUMERI):
                if w[0][1] == "Totale":
                    totale = dict(zip(NUMERI, map(to_float, nums)))
                else:
                    ancore[y] = {"cup": [], "riga_cdp": [], "intervento": [], "pagina": n,
                                 **dict(zip(NUMERI, map(to_float, nums)))}
        if not ancore:
            continue
        alto = max(ancore) + 12
        fondo = totale and min(y for y, w in linee if w and w[0][1] == "Totale")
        for y, w in linee:
            if y > alto or (fondo and y <= fondo):
                continue
            ya = min(ancore, key=lambda a: abs(a - y))
            if abs(ya - y) > 12:
                continue
            r = ancore[ya]
            r["cup"] += [t for x, t, _ in w if x < 105 and RE_CUP.match(t)]
            r["riga_cdp"] += [t for x, t, _ in w if 105 <= x < 140]
            s = " ".join(t for x, t, _ in w if 140 <= x < 310)
            if s:
                r["intervento"].append((y, s))
        for ya, r in sorted(ancore.items(), reverse=True):
            r["intervento"] = " ".join(s for _, s in sorted(r["intervento"], key=lambda p: -p[0]))
            r["riga_cdp"] = "|".join(r["riga_cdp"])
            r["cup"] = sorted(set(r["cup"]))
            righe.append(r)
    problemi = []
    if not totale:
        problemi.append("riga Totale non trovata")
    else:
        for k in NUMERI:
            s = round(sum(r[k] for r in righe), 2)
            if abs(s - totale[k]) > 0.05:
                problemi.append("%s: righe %.2f, totale %.2f" % (k, s, totale[k]))
    json.dump({"doc": "agg2025", "fonte": pdf.split("/")[-1], "righe": righe, "totale": totale},
              open(out, "w"), ensure_ascii=False, indent=1)
    print("%s: %d righe, %d CUP; totale %s" % (out, len(righe), sum(len(r["cup"]) for r in righe),
                                              "ok" if not problemi else "DIVERSO"))
    for p in problemi:
        print("  attenzione:", p)
    if problemi:
        sys.exit(1)


if __name__ == "__main__":
    main()
