"""Le variazioni di costo dell'Appendice 4 nell'applicazione, e il CSV.

Scrive app["delta_costi"]: il riepilogo per programma e tabella, le righe per
intervento (le nove colonne, nuovo inserimento, motivazione, pagina), i dossier
ex ante con le loro pagine e i file per il rimando ai PDF. Il CSV
variazioni-costo-<doc>.csv ha una riga per intervento.

Uso:
  python3 variazioni_costo.py app-in.json app-out.json ../data/appendice4-agg2025.json ../data
"""
import csv
import json
import os
import sys


def main():
    app_in, app_out, a4, cartella = sys.argv[1:5]
    A = json.load(open(app_in, encoding="utf-8"))
    T = json.load(open(a4, encoding="utf-8"))
    doc, VOCI = T["doc"], T["voci"]
    dossier_di = {}
    for d in T["dossier"]:
        for c in d["c"]:
            dossier_di[c] = d
    righe = {}
    for r in T["righe"]:
        righe[r["c"]] = {"v": [r[v] for v in VOCI], "nuovo": r["nuovo"], "mot": r["mot"], "p": r["p"],
                         "tab": r["tab"], "prog": r["prog"], "n": r["n"]}
    A["delta_costi"] = {
        "doc": doc, "id": "app4-" + doc, "file": "cdpi-%s/%s" % (doc, T["documento"]),
        "id_dossier": "app4d-" + doc, "file_dossier": "cdpi-%s/%s" % (doc, T["dossier_documento"]),
        "voci": VOCI, "riepilogo": T["riepilogo"], "righe": righe, "dossier": T["dossier"],
    }
    dest = os.path.join(cartella, "variazioni-costo-%s.csv" % doc)
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["codice", "descrizione", "tabella", "programma", "nuovo_inserimento"] +
                   [v + "_mln" for v in VOCI] + ["motivazione", "dossier_pagina", "pagina"])
        for r in T["righe"]:
            d = dossier_di.get(r["c"])
            w.writerow([r["c"], r["n"], r["tab"], r["prog"] or "", r["nuovo"]] + [r[v] for v in VOCI] +
                       [r["mot"], d["p"] if d else "", r["p"]])
    json.dump(A, open(app_out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    cresc = sum(1 for r in T["righe"] if r["variazioni_nette"] > 0.005)
    calo = sum(1 for r in T["righe"] if r["variazioni_nette"] < -0.005)
    print("variazioni di costo %s: %d interventi, %d con aumento netto, %d con riduzione netta, %d dossier"
          % (doc, len(righe), cresc, calo, len(T["dossier"])))


if __name__ == "__main__":
    main()
