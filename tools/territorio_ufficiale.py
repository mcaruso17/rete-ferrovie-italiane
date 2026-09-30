"""La distribuzione territoriale ufficiale (Appendice 7) nell'applicazione, e il
confronto con la stima della piattaforma.

Scrive app["territorio_ufficiale"] (riepilogo per regione, regioni di ogni
intervento, programmi diffusi, file per il rimando al PDF) e due CSV:
- distribuzione-territoriale-<doc>.csv: il riepilogo per regione;
- interventi-regioni-<doc>.csv: per ogni intervento, le regioni ufficiali,
  quelle stimate dalla piattaforma e l'esito del confronto.

Uso:
  python3 territorio_ufficiale.py app-in.json app-out.json ../data/appendice7-agg2025.json ../data
"""
import csv
import json
import os
import sys


def main():
    app_in, app_out, a7, cartella = sys.argv[1:5]
    A = json.load(open(app_in, encoding="utf-8"))
    T = json.load(open(a7, encoding="utf-8"))
    doc = T["doc"]
    REG = A.get("regioni", {})
    ATT = A.get("attribuzione_regionale", {})
    regioni, pag = {}, {}
    for ist, v in T["per_regione"].items():
        for x in v:
            regioni.setdefault(x["c"], []).append(ist)
            pag.setdefault(x["c"], x["p"])
    for x in T["diffusi"]:
        pag.setdefault(x["c"], x["p"])
    diffusi = [x["c"] for x in T["diffusi"]]
    presenti = {p["c"] for p in A["progetti"] if doc in p["h"]}

    esiti = {}
    righe = []
    for p in sorted(A["progetti"], key=lambda p: p["c"]):
        c = p["c"]
        if doc not in p["h"] and c not in regioni and c not in diffusi:
            continue
        u, s = set(regioni.get(c, [])), set(ATT.get(c, []))
        if c in diffusi:
            esito = "programma diffuso"
        elif not u:
            esito = "non elencato nell'appendice"
        elif not s:
            esito = "stima assente"
        elif u == s:
            esito = "uguali"
        elif u & s:
            esito = "in parte"
        else:
            esito = "diverse"
        esiti[esito] = esiti.get(esito, 0) + 1
        righe.append([c, p.get("n") or "", "|".join(REG.get(r, r) for r in sorted(u)),
                      len(u) > 1, c in diffusi, "|".join(REG.get(r, r) for r in sorted(s)), esito])

    with open(os.path.join(cartella, "interventi-regioni-%s.csv" % doc), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["codice", "descrizione", "regioni_appendice_7", "pluriregionale", "programma_diffuso",
                    "regioni_stimate_dalla_piattaforma", "confronto"])
        w.writerows(righe)
    with open(os.path.join(cartella, "distribuzione-territoriale-%s.csv" % doc), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["regione", "istat", "valore_normalizzato_mln", "risorse_mln", "nuove_risorse_mln",
                    "definanziamenti_mln", "rimodulazioni_mln", "incidenza_nuove_risorse_pct"])
        for r in T["riepilogo"]:
            w.writerow([r["regione"], r["istat"], r["valore_normalizzato"], r["risorse"], r["nuove_risorse"],
                        r["definanziamenti"], r["rimodulazioni"], r["incidenza_nuove_pct"]])

    A["territorio_ufficiale"] = {
        "doc": doc, "id": "app7-" + doc, "file": "cdpi-%s/%s" % (doc, T["documento"]),
        "note": T["note"], "riepilogo": T["riepilogo"], "regioni": regioni, "diffusi": diffusi, "pag": pag,
        "pagine": T["pagine"], "pagine_diffusi": sorted({x["p"] for x in T["diffusi"]}),
        "confronto": esiti,
    }
    json.dump(A, open(app_out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("territorio ufficiale %s: %d interventi in regione, %d diffusi; confronto con la stima: %s; "
          "interventi del contratto non elencati: %s"
          % (doc, len(regioni), len(diffusi), ", ".join("%s %d" % kv for kv in sorted(esiti.items())),
             sorted(presenti - set(regioni) - set(diffusi))))


if __name__ == "__main__":
    main()
