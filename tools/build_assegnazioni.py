"""I dati della pagina "Assegnazioni per CUP" (piattaforma/assegnazioni.html).

Legge il CSV delle assegnazioni (assegnazioni_cup.py) e la Tavola 2 dal
dataset, e li scrive dentro la pagina fra i marcatori /*DATI*/ e /*FINE*/:
la pagina e' un file unico, come la piattaforma, cosi' funziona anche aperta
dal disco.

Gli importi sono per intervento (il contratto non li divide per CUP): qui si
tiene un record per intervento con la lista dei suoi CUP, e la pagina conta i
CUP ma somma gli interventi.

Uso:
  python3 build_assegnazioni.py ../data/assegnazioni-cup-agg2025.csv \
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
    D = json.load(open(sys.argv[2]))
    pagina = sys.argv[3]

    interventi, per_cod = [], {}
    for r in righe:
        cod = r["codice_intervento"]
        if cod not in per_cod:
            it = {
                "c": cod, "d": r["descrizione_intervento"],
                # la tipologia come la stampa il PDF di questo aggiornamento: dal
                # 2024 "Interventi in programma" ha la lettera d (normalize.py la
                # chiama e per confrontare i contratti; qui si legge un contratto solo)
                "t": r["tabella"][:1],
                "tp": (r["lettera_nel_pdf"] + r["tipologia_programma"][1:]) if r["lettera_nel_pdf"] else r["tipologia_programma"],
                "pr": r["programma"], "ct": r["classe_tipologica"],
                "st": r["stato_attuativo"], "p": int(r["pagina_pdf"]),
                "costo": num(r["costo_totale_intervento_mln"]), "prec": num(r["finanziato_precedente_intervento_mln"]),
                "rid": num(r["riduzioni_intervento_mln"]), "rim": num(r["rimodulazioni_intervento_mln"]),
                "inc": num(r["incrementi_intervento_mln"]), "ass": num(r["risorse_assegnate_intervento_mln"]),
                "f": [num(r[k]) for k in ("mef_intervento_mln", "fsc_pac_intervento_mln", "mit_intervento_mln", "pnrr_intervento_mln", "altro_intervento_mln")],
                "fab": num(r["fabbisogno_totale_intervento_mln"]),
                "fp": [num(r[k]) for k in ("fabbisogno_priorita1_intervento_mln", "fabbisogno_priorita2_intervento_mln",
                                           "fabbisogno_completamento_intervento_mln")],
                "sp": num(r["speso_intervento_mln"]), "cups": [],
            }
            per_cod[cod] = it
            interventi.append(it)
        if r["cup"]:
            # origine: T = scritto in tabella, A = Appendice 2 (programmi)
            per_cod[cod]["cups"].append([r["cup"], "A" if r["origine_cup"] == "Appendice 2" else "T",
                                         r["oggetto_cup"]])

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
    print("%s: %d interventi, %d CUP, Tavola 2 %s-%s (%d KB)" % (
        pagina, len(interventi), sum(len(i["cups"]) for i in interventi), anni[0], anni[-1], len(s) // 1024))


if __name__ == "__main__":
    main()
