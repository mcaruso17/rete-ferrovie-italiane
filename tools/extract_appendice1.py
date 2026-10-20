"""Appendice 1 alla Relazione Informativa dell'aggiornamento 2025: "Dettaglio
delibere CIPESS per progetto". Una riga per delibera: CUP, NPP (numero
progetto), riga del CdP-I, titolo del progetto, numero e data della delibera,
titolo della delibera, tipologia (approvazione progettuale, assegnazione
risorse, vincolo preordinato all'esproprio o rinnovo, raccomandazioni) e note
("5/2013 (ricusata dalla CC)").

La riga di una delibera si riconosce dalla data (colonna a x ~203); titoli e
righe del CdP-I vanno a capo sopra e sotto, centrati sulla riga, e si
attaccano alla data piu' vicina in altezza. Una delibera puo' valere per due
righe del CdP-I (0332_A e 0332_B, Nodo di Bari).

Uso:
  python3 extract_appendice1.py ../documenti/cdpi-agg2025/appendice_1_delibere_cipess_per_progetto.pdf \
          ../data/appendice1-agg2025.json
"""
import json
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines

RE_CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
RE_DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
CAMPI = [("cup", 0, 84), ("npp", 84, 99), ("riga_cdp", 99, 133), ("titolo_progetto", 133, 185),
         ("numero", 185, 200), ("data", 200, 219), ("titolo_delibera", 219, 342), ("note", 488, 999)]
TIPI = [("approvazione_progettuale", 342, 374), ("assegnazione_risorse", 374, 406),
        ("vincolo_esproprio_rinnovo", 406, 448), ("raccomandazioni", 448, 488)]


def main():
    pdf, out = sys.argv[1], sys.argv[2]
    doc = PDF(pdf)
    delibere = []
    for n, pg in enumerate(doc.pages(), 1):
        linee = []
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            linee.append((it[0].y, parole(it)))
        ancore = [(y, w) for y, w in linee if any(RE_DATA.match(t) and 195 <= x < 220 for x, t, _ in w)]
        if not ancore:
            continue
        gruppi = {y: [] for y, _ in ancore}
        y_tab = max(y for y, _ in ancore) + 12
        for y, w in linee:
            if y > y_tab or (w and w[0][1] == "Pagina"):
                continue
            ya = min(gruppi, key=lambda a: abs(a - y))
            if abs(ya - y) < 12:
                gruppi[ya].append((y, w))
        for ya, righe in sorted(gruppi.items(), reverse=True):
            righe.sort(key=lambda r: -r[0])
            d = {k: " ".join(t for _, w in righe for x, t, _ in w if a <= x < b).strip() for k, a, b in CAMPI}
            for k, a, b in TIPI:
                d[k] = any(t == "X" and a <= x < b for _, w in righe for x, t, _ in w)
            cups = [t for _, w in righe for x, t, _ in w if RE_CUP.match(t)]
            d["cup"] = cups[0] if cups else ""
            d["riga_cdp"] = "|".join(d["riga_cdp"].split())
            d["pagina"] = n
            delibere.append(d)
    json.dump({"doc": "agg2025", "fonte": pdf.split("/")[-1], "delibere": delibere}, open(out, "w"),
              ensure_ascii=False, indent=1)
    senza = [d for d in delibere if not d["cup"]]
    print("%s: %d delibere, %d CUP distinti, %d progetti (riga CdP-I); delibere senza CUP: %d" % (
        out, len(delibere), len({d["cup"] for d in delibere if d["cup"]}),
        len({d["riga_cdp"] for d in delibere}), len(senza)))
    if senza:
        sys.exit("delibere senza CUP: " + ", ".join(d["numero"] + "/" + d["data"] for d in senza))


if __name__ == "__main__":
    main()
