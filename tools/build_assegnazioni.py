"""I dati della pagina "Assegnazioni per CUP" (piattaforma/assegnazioni.html).

Legge i due CSV delle assegnazioni (assegnazioni_cup.py), quello degli
interventi per gli importi e quello dei CUP per i legami CUP-intervento, e la
Tavola 2 dal dataset, e li scrive dentro la pagina fra i marcatori /*DATI*/ e
/*FINE*/: la pagina e' un file unico, come la piattaforma, cosi' funziona
anche aperta dal disco.

Gli importi sono per intervento (il contratto non li divide per CUP): qui si
tiene un record per intervento con la lista dei suoi CUP. Un CUP puo' stare
sotto piu' interventi (24 nel 2025): la pagina conta i CUP distinti.

Le opere (stato attuativo e fase finanziata, una riga per lotto o fase) vengono
da stati-opere-agg2025.csv.

Uso:
  python3 build_assegnazioni.py ../data/assegnazioni-interventi-agg2025.csv \
          ../data/assegnazioni-cup-agg2025.csv ../data/stati-opere-agg2025.csv \
          ../data/cdp-rfi-dataset.json ../piattaforma/assegnazioni.html
"""
import csv
import json
import re
import sys


def num(x):
    return None if x in ("", None) else round(float(x), 2)


def main():
    righe = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
    cup = list(csv.DictReader(open(sys.argv[2], encoding="utf-8")))
    opere = list(csv.DictReader(open(sys.argv[3], encoding="utf-8")))
    D = json.load(open(sys.argv[4]))
    pagina = sys.argv[5]

    interventi, per_cod = [], {}
    for r in righe:
        it = {
            "c": r["codice_intervento"], "d": r["descrizione_intervento"],
            "t": r["tabella"][:1], "tp": r["tipologia_programma"],
            "pr": r["programma"], "ct": r["classe_tipologica"],
            "st": r["stati_attuativi_opere"], "p": int(r["pagina_pdf"]),
            "costo": num(r["costo_totale_mln"]), "prec": num(r["finanziato_precedente_mln"]),
            "rid": num(r["riduzioni_mln"]), "rim": num(r["rimodulazioni_mln"]),
            "inc": num(r["incrementi_mln"]), "ass": num(r["risorse_assegnate_mln"]),
            "f": [num(r[k]) for k in ("mef_mln", "fsc_pac_mln", "mit_mln", "pnrr_mln", "altro_mln")],
            "fab": num(r["fabbisogno_totale_mln"]),
            "fp": [num(r[k]) for k in ("fabbisogno_priorita1_mln", "fabbisogno_priorita2_mln",
                                       "fabbisogno_completamento_mln")],
            "sp": num(r["speso_mln"]), "cups": [], "ss": r["stato_sintesi"], "op": [],
        }
        per_cod[it["c"]] = it
        interventi.append(it)
    # i CUP di ogni intervento dal file dei CUP: origine T = scritto in tabella,
    # A = Appendice 2 (programmi); un CUP condiviso finisce in piu' interventi
    for r in cup:
        if not r["cup"]:
            continue
        for k in (1, 2, 3):
            cod = r.get("intervento_%d" % k)
            if cod:
                o = r["origine_cup_intervento_%d" % k]
                # D = CUP non stampato in tabella ma scritto negli altri documenti
                # dell'aggiornamento (A004 Brennero, assegnazioni_cup.py)
                per_cod[cod]["cups"].append([r["cup"], "A" if o == "Appendice 2" else "D" if o.startswith("Altri documenti") else "T",
                                             r["oggetto_cup"], r["tipo_condivisione"]])
    # opere: [descrizione, fase finanziata, stato attuativo, costo dell'opera o null]
    for o in opere:
        per_cod[o["codice_intervento"]]["op"].append(
            [o["descrizione_opera"], o["fase_finanziata"], o["stato_attuativo"], num(o["costo_totale_opera_mln"])])
    for it in interventi:
        it["cups"].sort(key=lambda c: (c[1], c[0]))
        if len(it["cups"]) != int(next(r for r in righe if r["codice_intervento"] == it["c"])["n_cup"]):
            sys.exit("CUP di %s: il file dei CUP non torna con quello degli interventi" % it["c"])

    doc = righe[0]["documento"]
    meta = D["documenti"][doc]
    # Tavola 2, cassa per anno: le fonti con i nomi del documento. MEF qui
    # comprende l'FSC (capitolo 8000 sotto il MEF), a differenza delle colonne
    # della Tabella A, che lo tengono a parte
    t2 = {r["riga"]: r for r in D["tavola2"] if r["doc"] == doc}
    righe_t2 = [("9", "Stato - MEF (con FSC)"), ("17", "Stato - MIT"),
                ("34", "UE e PNRR"), ("40", "Enti locali e altro")]
    anni = t2["43"]["anni"]
    cassa = {
        "anni": anni, "pagina": t2["43"]["page"],
        "fonti": [{"n": nome, "v": [v or 0 for v in t2[k]["valori"]]} for k, nome in righe_t2],
        "totale": t2["43"]["valori"],
        "impieghi": t2["5"]["valori"] if "5" in t2 else None,
    }
    for i, a in enumerate(anni):
        s = sum(f["v"][i] for f in cassa["fonti"])
        if abs(s - (cassa["totale"][i] or 0)) > 1:
            sys.exit("Tavola 2 %s: le fonti del %s fanno %.0f, il totale stampato %.0f" % (doc, a, s, cassa["totale"][i]))

    dati = {"doc": doc, "titolo": meta["titolo"], "file": meta["file"],
            "avanz_al": meta.get("avanz_al"), "interventi": interventi, "cassa": cassa}
    s = json.dumps(dati, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = open(pagina, encoding="utf-8").read()
    nuovo, n = re.subn(r"/\*DATI\*/.*?/\*FINE\*/", lambda m: "/*DATI*/" + s + "/*FINE*/", html, flags=re.S)
    if n != 1:
        sys.exit("marcatori /*DATI*/ ... /*FINE*/ non trovati in " + pagina)
    open(pagina, "w", encoding="utf-8").write(nuovo)
    print("%s: %d interventi, %d CUP distinti, Tavola 2 %s-%s (%d KB)" % (
        pagina, len(interventi), len({c[0] for i in interventi for c in i["cups"]}), anni[0], anni[-1], len(s) // 1024))


if __name__ == "__main__":
    main()
