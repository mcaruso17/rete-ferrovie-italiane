"""Appendice 12 alla Relazione Informativa dell'aggiornamento 2025: "Dettaglio
riallocazione 2025 dei finanziamenti gia' contrattualizzati nel CdP-I
2022-2026 vigente" (le rimodulazioni del paragrafo 3.4 della Relazione).
Una riga per intervento e tipologia di rimodulazione: codice, descrizione,
totale, beneficiari (risorse ricevute) e cedenti (risorse cedute).

La tipologia ("Clausole di flessibilita' ex art. 1 commi 5 e 6", "Riutilizzo
risorse liberate da finanziamenti UE e A22 su fabbisogni prioritari"...) e'
scritta a sinistra, centrata sul suo blocco e spezzata su piu' righe: si
prende dalla riga "<tipologia> Totale" che chiude il blocco. Uno stesso
intervento puo' stare in piu' tipologie e piu' volte nella stessa (0292A).

Controlli: le righe di ogni blocco sommano al suo totale e il totale generale
e' zero (le rimodulazioni spostano risorse, non ne aggiungono).

Uso:
  python3 extract_appendice12.py ../documenti/cdpi-agg2025/appendice_12_rimodulazioni.pdf \\
          ../data/appendice12-agg2025.json
"""
import json
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import to_float

RE_NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
NUMERI = ["totale", "beneficiari", "cedenti"]


def main():
    pdf, out = sys.argv[1], sys.argv[2]
    doc = PDF(pdf)
    righe, blocco, totali, problemi = [], [], [], []
    attesa, gruppo, etichetta = None, [], ""
    for n, pg in enumerate(doc.pages(), 1):
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            w = parole(it)
            nums = [t for x, t, _ in w if x > 400 and RE_NUM.match(t)]
            sx = " ".join(t for x, t, _ in w if x < 140)
            if attesa is not None and sx.endswith("Totale") and not nums:
                # "Riutilizzo risorse liberate ... su / fabbisogni prioritari Totale":
                # la scritta sta sotto i numeri ed e' spezzata su due righe
                tip = sx[:-len("Totale")].strip()
                if tip[:1].islower():
                    tip = etichetta + " " + tip
                for r in attesa:
                    r["tipologia"] = tip
                attesa = None
                continue
            if sx and not nums:
                etichetta = sx
            if len(nums) != 3:
                continue
            v = dict(zip(NUMERI, map(to_float, nums)))
            if sx.endswith("Totale") or not any(140 <= x < 400 for x, _, _ in w):
                if not blocco:
                    # "Totale Rimodulazioni verso progetti caratterizzati da una
                    # maggiore maturita' e rilevanza": somma dei blocchi precedenti
                    for k in NUMERI:
                        s = round(sum(g[k] for g in gruppo), 2)
                        if abs(s - v[k]) > 0.05:
                            problemi.append("totale di gruppo, %s: blocchi %.2f, stampato %.2f" % (k, s, v[k]))
                    gruppo = []
                    continue
                totali.append(v)
                gruppo.append(v)
                for k in NUMERI:
                    s = round(sum(r[k] for r in blocco), 2)
                    if abs(s - v[k]) > 0.05:
                        problemi.append("blocco, %s: righe %.2f, totale %.2f" % (k, s, v[k]))
                if sx.endswith("Totale"):
                    for r in blocco:
                        r["tipologia"] = sx[:-len("Totale")].strip()
                else:
                    attesa = blocco
                righe += blocco
                blocco = []
            else:
                blocco.append({"codice": next(t for x, t, _ in w if 140 <= x < 172),
                               "descrizione": " ".join(t for x, t, _ in w if 172 <= x < 400),
                               "pagina": n, "tipologia": "", **v})
    if any(not r["tipologia"] for r in righe):
        problemi.append("righe senza tipologia")
    if blocco:
        problemi.append("%d righe dopo l'ultimo totale" % len(blocco))
    if abs(sum(t["totale"] for t in totali)) > 0.05:
        problemi.append("il totale generale non e' zero")
    json.dump({"doc": "agg2025", "fonte": pdf.split("/")[-1], "righe": righe}, open(out, "w"),
              ensure_ascii=False, indent=1)
    print("%s: %d righe, %d interventi, %d tipologie; controlli %s" % (
        out, len(righe), len({r["codice"] for r in righe}), len({r["tipologia"] for r in righe}),
        "ok" if not problemi else "DIVERSI"))
    for p in problemi:
        print("  attenzione:", p)
    if problemi:
        sys.exit(1)


if __name__ == "__main__":
    main()
