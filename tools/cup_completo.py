"""Un file solo, una riga per CUP, con tutto quello che i documenti dicono di
quel CUP: data/cup-completo.csv. E a parte gli interventi dell'ultimo
aggiornamento a cui non si puo' associare un CUP: data/interventi-senza-cup-agg2025.csv.

Le righe sono i CUP di tutte le fonti a disposizione:
- il registro dei CUP (registro_cup.py): Tabelle A, B e C di tutti i contratti
  Investimenti dal 2017, Appendice 2, Allegati 4c e 12 dei contratti Servizi;
- i CUP scritti solo in un'appendice dell'aggiornamento 2025 (cup-altri);
- i CUP della lista ricevuta da RFI (solo CUP e stato BDAP, confronto_rfi.py),
  compresi quelli che non stanno in nessun documento: fonte_riga lo dice.

Le colonne, nell'ordine:
- identita' e stato dal registro, con la pagina e l'alberatura;
- dove il CUP e' scritto, in tutti i PDF (cup-nel-testo.json), e l'esito del
  confronto con la lista RFI;
- per i 990 CUP in corso, tutte le colonne di assegnazioni-cup-agg2025.csv
  (interventi, importi, quota per CUP, stato, appendici);
- per gli altri CUP dell'aggiornamento, le colonne delle appendici di
  cup-altri-agg2025.csv;
- per ogni intervento del CUP (_intervento_1.._3) il resto della riga di
  assegnazioni-interventi-agg2025.csv: movimenti dell'anno, fabbisogno per
  priorita', stato delle opere, regioni, variazioni di costo e di risorse per
  fonte, rimodulazioni, PNRR.

Attenzione: gli importi _intervento_k sono dell'intervento intero e si
ripetono su tutti i suoi CUP (un programma con cento CUP li ripete cento
volte). Per sommare per CUP si usano le colonne *_per_cup_mln o quelle
dell'Appendice 3; per sommare per intervento, il file degli interventi.

Uso:
  python3 cup_completo.py ../data
"""
import csv
import json
import os
import sys

from appendici_cup import nome_doc

MAX_INT = 3


def leggi(cartella, nome):
    return list(csv.DictReader(open(os.path.join(cartella, nome), encoding="utf-8")))


def intestazione(cartella, nome):
    return next(csv.reader(open(os.path.join(cartella, nome), encoding="utf-8")))


def main():
    d = sys.argv[1]
    reg = leggi(d, "cup-registro.csv")
    ass = leggi(d, "assegnazioni-cup-agg2025.csv")
    altri = leggi(d, "cup-altri-agg2025.csv")
    interv = leggi(d, "assegnazioni-interventi-agg2025.csv")
    cfr = {r["cup"]: r for r in leggi(d, "confronto-rfi.csv")}
    testo = json.load(open(os.path.join(d, "cup-nel-testo.json")))
    col_ass, col_altri, col_int = (intestazione(d, f) for f in (
        "assegnazioni-cup-agg2025.csv", "cup-altri-agg2025.csv", "assegnazioni-interventi-agg2025.csv"))
    col_reg = [c for c in intestazione(d, "cup-registro.csv") if c not in ("cup", "stato")]

    per_ass = {r["cup"]: r for r in ass if r["cup"]}
    per_altri = {r["cup"]: r for r in altri}
    per_reg = {r["cup"]: r for r in reg}
    per_int = {r["codice_intervento"]: r for r in interv}

    # colonne dell'intervento che il file dei CUP non ha gia' per k: non si
    # ripetono descrizione, pagina, numero di CUP, importi e colonne brevi
    gia = {c[:-len("_intervento_1")] for c in col_ass if c.endswith("_intervento_1")}
    gia |= {c.replace("_intervento_1_mln", "_mln") for c in col_ass if c.endswith("_intervento_1_mln")}
    # e non la lista dei CUP dell'intervento: un programma con cento CUP la
    # ripeterebbe intera su cento righe
    salta = {"documento", "codice_intervento", "descrizione_intervento", "pagina_pdf", "n_cup", "stato_sintesi", "cup"}
    extra_int = [c for c in col_int if c not in salta and c not in gia]

    col_ident = ["cup", "fonte_riga", "in_contratto_in_corso", "stato_registro"] + \
                ["registro_" + c for c in col_reg] + \
                ["citato_in_documenti", "esito_confronto_lista_rfi", "nella_lista_rfi", "stato_bdap_lista_rfi"]
    col_cup = [c for c in col_ass if c not in ("cup", "documento")]
    # di cup-altri non si ripete quello che il registro gia' da' (registro_*)
    doppie = {"cup", "documento", "stato_registro", "parte", "fonte_registro", "opere_ultimate_voce",
              "opere_ultimate_edizione", "data_messa_in_esercizio", "interventi_contratti_precedenti",
              "programma_appendice_2"}
    col_cup += [c for c in col_altri if c not in col_cup and c not in doppie]
    def nome_k(c, k):
        # come nel file dei CUP: costo_totale_intervento_1_mln
        return c[:-4] + "_intervento_%d_mln" % k if c.endswith("_mln") else c + "_intervento_%d" % k
    col_k = [nome_k(c, k) for k in range(1, MAX_INT + 1) for c in extra_int]
    colonne = col_ident + col_cup + col_k

    cups = list(per_reg) + [c for c in per_altri if c not in per_reg] + \
        [c for c in cfr if c not in per_reg and c not in per_altri]
    righe = []
    for c in cups:
        g = per_reg.get(c, {})
        a = per_ass.get(c)
        x = per_altri.get(c, {})
        f = cfr.get(c, {})
        r = {"cup": c, "stato_registro": g.get("stato", x.get("stato_registro", "")),
             "in_contratto_in_corso": "si" if a else "no",
             "fonte_riga": ("Tabelle A e B o Appendice 2 dell'aggiornamento 2025 (contratto in corso)" if a
                            else "registro dei CUP (contratti Investimenti e Servizi)" if g
                            else "solo in un'appendice dell'aggiornamento 2025" if x
                            else "solo nella lista RFI (BDAP), in nessun documento")}
        r.update({"registro_" + k: g.get(k, "") for k in col_reg})
        if not g and x:
            # il registro dei CUP nasce quando del 2025 si leggeva solo l'Appendice 2:
            # i CUP che stanno solo in un'altra appendice prendono qui la loro
            # fonte (5 nelle schede intervento, 3 nelle delibere CIPESS)
            r["registro_fonte_principale"] = (
                "Appendice 3 (schede intervento)" if x.get("scheda_appendice_3")
                else "Appendice 1 (delibere CIPESS)" if x.get("cipess_n_delibere")
                else "Appendice 9 (PNRR e PNC)" if x.get("pnrr_pnc_sezione")
                else "Appendice 8 (legge obiettivo)" if x.get("pis_descrizione")
                else "Appendice 6 (DL 43/2013)" if x.get("dl43_intervento") else "")
            r["registro_descrizione"] = x.get("descrizione", "")
        dove = {}
        for doc, p in testo.get(c, []):
            dove.setdefault(nome_doc(doc) if "cdpi-" in doc or "Agg_ 2025" in doc else doc.replace(".pdf", ""), []).append(p)
        r["citato_in_documenti"] = "; ".join("%s p. %s" % (k, ", ".join(map(str, sorted(set(v)))))
                                             for k, v in dove.items())
        r.update({"esito_confronto_lista_rfi": f.get("esito", ""), "nella_lista_rfi": f.get("nella_lista", ""),
                  "stato_bdap_lista_rfi": f.get("stato_bdap", "")})
        sorg = a or x
        r.update({k: sorg.get(k, "") for k in col_cup})
        if a:
            for k in range(1, MAX_INT + 1):
                it = per_int.get(a.get("intervento_%d" % k) or "")
                if it:
                    r.update({nome_k(col, k): it[col] for col in extra_int})
        righe.append(r)

    with open(os.path.join(d, "cup-completo.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=colonne)
        w.writeheader()
        w.writerows(righe)

    # gli interventi a cui non si puo' associare un CUP: nessun CUP in tabella,
    # nell'Appendice 2 o negli altri documenti dell'aggiornamento
    senza = [r for r in interv if r["n_cup"] == "0"]
    with open(os.path.join(d, "interventi-senza-cup-agg2025.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=col_int)
        w.writeheader()
        w.writerows(senza)

    if len(set(cups)) != len(cups):
        sys.exit("CUP ripetuti nel file completo")
    if sum(1 for r in righe if r["in_contratto_in_corso"] == "si") != len(per_ass):
        sys.exit("i CUP in corso non tornano con il file delle assegnazioni")
    print("cup-completo.csv: %d CUP, %d colonne (%s); interventi-senza-cup-agg2025.csv: %d interventi (%s)" % (
        len(righe), len(colonne), ", ".join("%s %d" % (k, sum(1 for r in righe if r["fonte_riga"] == k))
                                             for k in dict.fromkeys(r["fonte_riga"] for r in righe)),
        len(senza), ", ".join(r["codice_intervento"] for r in senza)))


if __name__ == "__main__":
    main()
