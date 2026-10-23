"""Due file semplici sulle risorse dell'aggiornamento 2025, chiesti dal
dirigente: uno per intervento, uno per CUP, con poche colonne e tutte scritte
nei documenti. Gli altri file (assegnazioni, cup-completo, alberatura) restano
per chi cerca il dettaglio; questi servono a rispondere a "quanto e' stato
assegnato, e da quale fonte".

data/base-interventi-agg2025.csv: una riga per intervento delle Tabelle A e B
(223). Importi come li stampa la riga della tabella: costo a vita intera,
assegnate al precedente aggiornamento e movimenti 2025 (incrementi, riduzioni,
rimodulazioni), che sommati danno le assegnate; assegnate per fonte, fabbisogno
e speso. Lo script controlla le due identita' (precedente + movimenti =
assegnate = somma delle fonti) e i totali stampati nella tabella di sintesi.

data/base-cup-agg2025.csv: una riga per CUP. Perimetro: i CUP stampati nelle
Tabelle A e B, quelli dei programmi dell'Appendice 2, il CUP del Brennero
(altri documenti dell'aggiornamento) e i 6 che stanno solo nelle schede
dell'Appendice 3; la colonna perimetro li distingue, cosi' si contano 173, 990
o 996 secondo la domanda. Gli importi del CUP vengono da una sola fonte,
indicata in fonte_importi, in quest'ordine:
- il CUP e' l'unico del suo intervento e l'intervento ha solo quel CUP: gli
  importi dell'intervento, comprese le fonti (MEF, MIT...);
- programmi: costo, risorse e contabilizzato del sottoprogetto (Appendice 3,
  avanzamento programma);
- progetti: costo, risorse e fabbisogno delle opere del CUP (Appendice 3,
  piano della spesa), se tutte le opere hanno la riga;
- altrimenti nessun importo: nessun documento ne scrive uno per quel CUP.
Le fonti ci sono solo nel primo caso: l'Appendice 3 non ripartisce per fonte.
Non c'e' nessuna quota calcolata (come *_per_cup_mln nel file delle
assegnazioni): qui stanno solo numeri stampati.

Uso:
  python3 dataset_base.py ../data
"""
import csv
import json
import os
import sys

from appendici_cup import riga_spesa

FONTI = ["mef", "fsc_pac", "mit", "pnrr", "altro"]
COL_INT = ["codice_intervento", "macro_intervento", "descrizione_intervento", "tabella", "tipologia_programma",
           "programma", "classe_tipologica", "n_cup", "costo_vita_intera_mln",
           "assegnate_aggiornamento_precedente_mln", "incrementi_2025_mln", "riduzioni_2025_mln",
           "rimodulazioni_2025_mln", "risorse_assegnate_mln"] + ["%s_mln" % f for f in FONTI] + \
          ["fabbisogno_mln", "speso_mln", "pagina_pdf"]
COL_CUP = ["cup", "perimetro", "codice_intervento", "n_interventi", "n_cup_intervento", "oggetto_cup",
           "tabella", "tipologia_programma", "programma", "classe_tipologica", "stato_attuativo",
           "fonte_importi", "costo_mln", "risorse_assegnate_mln"] + ["%s_mln" % f for f in FONTI] + \
          ["fabbisogno_mln", "speso_mln", "pagina"]
# tabella di sintesi del CdP-I 2025 (risorse assegnate): il controllo dei totali
SINTESI = {"a": 35218.74, "b": 46493.93, "c": 25768.27, "d": 622.49, "B": 18010.63}


def leggi(d, f):
    return list(csv.DictReader(open(os.path.join(d, f), encoding="utf-8")))


def num(x):
    return float(x) if x not in ("", None) else None


def scrivi(d, f, col, righe):
    with open(os.path.join(d, f), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=col, extrasaction="ignore")
        w.writeheader()
        w.writerows(righe)


def main():
    d = sys.argv[1]
    interv = leggi(d, "assegnazioni-interventi-agg2025.csv")
    cups = [r for r in leggi(d, "assegnazioni-cup-agg2025.csv") if r["cup"]]
    altri = [r for r in leggi(d, "cup-altri-agg2025.csv") if r["scheda_appendice_3"]]
    alb = leggi(d, "alberatura-cup-agg2025.csv")
    a3 = json.load(open(os.path.join(d, "appendice3-agg2025.json")))["schede"]
    macro = {r["intervento"]: r["macro_intervento"] for r in alb}
    per_int = {r["codice_intervento"]: r for r in interv}

    righe_int, problemi = [], []
    for it in interv:
        r = {k: it.get(k, "") for k in COL_INT}
        r.update({"macro_intervento": macro.get(it["codice_intervento"], ""),
                  "costo_vita_intera_mln": it["costo_totale_mln"],
                  "assegnate_aggiornamento_precedente_mln": it["finanziato_precedente_mln"],
                  "incrementi_2025_mln": it["incrementi_mln"], "riduzioni_2025_mln": it["riduzioni_mln"],
                  "rimodulazioni_2025_mln": it["rimodulazioni_mln"], "fabbisogno_mln": it["fabbisogno_totale_mln"]})
        mov = sum(num(r[k]) for k in ("assegnate_aggiornamento_precedente_mln", "incrementi_2025_mln",
                                      "riduzioni_2025_mln", "rimodulazioni_2025_mln"))
        fonti = sum(num(r["%s_mln" % f]) for f in FONTI)
        if abs(mov - num(r["risorse_assegnate_mln"])) > 0.05 or abs(fonti - num(r["risorse_assegnate_mln"])) > 0.05:
            problemi.append("%s: precedente + movimenti %.2f, fonti %.2f, assegnate %s" % (
                it["codice_intervento"], mov, fonti, r["risorse_assegnate_mln"]))
        righe_int.append(r)
    for k, v in SINTESI.items():
        s = sum(num(r["risorse_assegnate_mln"]) for r in righe_int
                if (r["tabella"][:1] == "B" if k == "B" else
                    r["tabella"][:1] == "A" and r["tipologia_programma"][:1] == k))
        # la sintesi somma i dati pieni, il file valori di riga arrotondati
        if abs(s - v) > 0.1:
            problemi.append("sintesi %s: file %.2f, stampato %.2f" % (k, s, v))

    def importi_intervento(cod):
        it = per_int[cod]
        out = {"costo_mln": it["costo_totale_mln"], "risorse_assegnate_mln": it["risorse_assegnate_mln"],
               "fabbisogno_mln": it["fabbisogno_totale_mln"], "speso_mln": it["speso_mln"]}
        out.update({"%s_mln" % f: it["%s_mln" % f] for f in FONTI})
        return out

    righe_cup = []
    for c in cups:
        codici = [c["intervento_%d" % k] for k in (1, 2, 3) if c.get("intervento_%d" % k)]
        origini = {c["origine_cup_intervento_%d" % k] for k in (1, 2, 3) if c.get("intervento_%d" % k)}
        r = {"cup": c["cup"],
             "perimetro": ("Tabelle A e B" if origini & {"Tabella A", "Tabella B"} else
                           "Appendice 2" if "Appendice 2" in origini else "Altri documenti dell'aggiornamento"),
             "codice_intervento": "|".join(codici), "n_interventi": len(codici),
             "n_cup_intervento": "|".join(c["n_cup_intervento_%d" % k] for k in range(1, len(codici) + 1)),
             "oggetto_cup": c["oggetto_cup"] or c["opere_cup"],
             "tabella": c["tabella"], "tipologia_programma": c["tipologia_programma"], "programma": c["programma"],
             "classe_tipologica": c["classe_tipologica"],
             "stato_attuativo": c["stato_attuativo_cup_testo"] or c["stato_attuativo_cup"],
             "pagina": ("App. 3 p. %s" % c["pagina_appendice_3"] if c["pagina_appendice_3"] else
                        "App. 2 p. %s" % c["pagina_appendice_2"] if c["pagina_appendice_2"] else
                        "p. %s" % c["pagina_pdf_intervento_1"])}
        if len(codici) == 1 and c["n_cup_intervento_1"] == "1":
            r["fonte_importi"] = "Intervento con un solo CUP (Tabella %s)" % c["tabella"][:1]
            r.update(importi_intervento(codici[0]))
        elif c["costo_cup_appendice3_mln"]:
            r.update({"fonte_importi": "Appendice 3, avanzamento programma",
                      "costo_mln": c["costo_cup_appendice3_mln"], "risorse_assegnate_mln": c["risorse_cup_appendice3_mln"],
                      "speso_mln": c["contabilizzato_cup_appendice3_mln"]})
        elif c["spesa_opere_cup_costo_mln"]:
            r.update({"fonte_importi": "Appendice 3, piano della spesa delle opere",
                      "costo_mln": c["spesa_opere_cup_costo_mln"], "risorse_assegnate_mln": c["spesa_opere_cup_risorse_mln"],
                      "fabbisogno_mln": c["spesa_opere_cup_fabbisogno_mln"]})
        else:
            r["fonte_importi"] = "Nessun importo proprio nei documenti"
        righe_cup.append(r)

    # i CUP che stanno solo nelle schede: intervento e importi dalla scheda
    for c in altri:
        cod = c["scheda_appendice_3"]
        sc = a3.get(cod, {})
        it = per_int.get(cod, {})
        r = {"cup": c["cup"], "perimetro": "Solo Appendice 3", "codice_intervento": cod, "n_interventi": 1,
             "oggetto_cup": c["opera_appendice_3"] or c["descrizione"], "tabella": it.get("tabella", ""),
             "tipologia_programma": it.get("tipologia_programma", ""), "programma": it.get("programma", ""),
             "classe_tipologica": it.get("classe_tipologica", ""), "stato_attuativo": c["stato_attuativo_appendice_3"],
             "pagina": "App. 3 p. %s" % c["pagina_appendice_3"]}
        av = [x for x in sc.get("avanzamento", []) if x["cup"] == c["cup"]]
        ops = [o for o in sc.get("opere", []) if o["cup"] == c["cup"]]
        sp = [riga_spesa(o["opera"], sc.get("spesa", []), sc) for o in ops]
        if av:
            r.update({"fonte_importi": "Appendice 3, avanzamento programma",
                      "costo_mln": round(sum(x["costo"] for x in av), 2),
                      "risorse_assegnate_mln": round(sum(x["risorse"] for x in av), 2),
                      "speso_mln": round(sum(x["contabilizzato"] for x in av), 2)})
        elif sp and None not in sp:
            r.update({"fonte_importi": "Appendice 3, piano della spesa delle opere",
                      **{k + "_mln": round(sum(x[k] for x in sp), 2) for k in ("costo", "fabbisogno")},
                      "risorse_assegnate_mln": round(sum(x["risorse"] for x in sp), 2)})
        else:
            r["fonte_importi"] = "Nessun importo proprio nei documenti"
        righe_cup.append(r)

    if len({r["cup"] for r in righe_cup}) != len(righe_cup):
        problemi.append("CUP ripetuti")
    if sum(1 for r in righe_cup if r["perimetro"] != "Solo Appendice 3") != 990:
        problemi.append("i CUP del portafoglio non sono 990")
    scrivi(d, "base-interventi-agg2025.csv", COL_INT, righe_int)
    scrivi(d, "base-cup-agg2025.csv", COL_CUP, righe_cup)
    conta = lambda k: ", ".join("%s %d" % (v, sum(1 for r in righe_cup if r[k] == v))
                                for v in dict.fromkeys(r[k] for r in righe_cup))
    print("base-interventi-agg2025.csv: %d interventi, assegnate %.2f; base-cup-agg2025.csv: %d CUP (%s); "
          "importi: %s; controlli %s" % (
              len(righe_int), sum(num(r["risorse_assegnate_mln"]) for r in righe_int), len(righe_cup),
              conta("perimetro"), conta("fonte_importi"), "ok" if not problemi else "DIVERSI"))
    for p in problemi:
        print("  attenzione:", p)
    if problemi:
        sys.exit(1)


if __name__ == "__main__":
    main()
