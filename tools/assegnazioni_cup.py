"""Le assegnazioni dell'ultimo aggiornamento Investimenti, una riga per CUP.

Per ogni intervento delle Tabelle A e B: costo, movimenti dell'anno
(riduzioni, rimodulazioni, incrementi), risorse assegnate per fonte (MEF, FSC,
MIT, PNRR, altro) e fabbisogno per priorita', con tipologia di programma e
classe tipologica dell'alberatura.

L'unita' e' il CUP, ma il contratto non divide gli importi per CUP: li stampa
per intervento. Ogni riga ha quindi due serie di importi:
- *_intervento_mln: quelli scritti nel contratto, dell'intervento intero,
  ripetuti su ogni suo CUP; si sommano solo sulle righe con riga_intervento = 1;
- *_per_cup_mln: l'importo dell'intervento diviso in parti uguali fra i suoi
  CUP. E' una convenzione di questo file, non un dato del contratto (le
  schede dell'Appendice 3 mostrano CUP dello stesso programma con importi
  molto diversi: in NA026 da 0,2 a 1.129 mln). Serve a sommare su tutte le
  righe senza contare piu' volte un intervento.
cup_multipli dice se l'intervento ha piu' di un CUP. Un intervento senza CUP
ha una riga sola con il CUP vuoto e la quota uguale all'intervento.

I CUP vengono da due posti: quelli scritti sotto l'intervento in tabella e,
per i programmi pluriennali, quelli dell'Appendice 2 alla Relazione
Informativa (un CUP per oggetto, senza importi).

Uso:
  python3 assegnazioni_cup.py ../data/cdp-rfi-dataset.json ../data/appendice-cup-agg2025.json \
          ../data/assegnazioni-cup-agg2025.csv
"""
import csv
import json
import sys

from schema import ALB_CLASSI_TIP, ALB_TABELLE, CLASSI

COLONNE = [
    "documento", "pagina_pdf", "tabella", "tipologia_programma", "lettera_nel_pdf",
    "programma", "classe_tipologica", "codice_intervento", "descrizione_intervento",
    "cup", "origine_cup", "oggetto_cup", "pagina_appendice_2", "n_cup_intervento",
    "riga_intervento", "cup_multipli", "ripartizione_per_cup", "stato_attuativo",
    "costo_totale_intervento_mln", "finanziato_precedente_intervento_mln", "riduzioni_intervento_mln",
    "rimodulazioni_intervento_mln", "incrementi_intervento_mln", "risorse_assegnate_intervento_mln",
    "mef_intervento_mln", "fsc_pac_intervento_mln", "mit_intervento_mln", "pnrr_intervento_mln",
    "altro_intervento_mln", "fabbisogno_totale_intervento_mln", "fabbisogno_priorita1_intervento_mln",
    "fabbisogno_priorita2_intervento_mln", "fabbisogno_completamento_intervento_mln",
    "speso_intervento_mln",
] + ["%s_per_cup_mln" % k for k in (
    "costo_totale", "risorse_assegnate", "mef", "fsc_pac", "mit", "pnrr", "altro",
    "fabbisogno_totale", "speso")] + ["controllo"]

# gli importi che si dividono fra i CUP (i movimenti dell'anno restano solo per intervento)
PER_CUP = ["costo_totale", "risorse_assegnate", "mef", "fsc_pac", "mit", "pnrr", "altro",
           "fabbisogno_totale", "speso"]


def r2(x):
    return "" if x is None else round(x, 2)


def controllo(s):
    """Le due identita' della riga di Tabella A, come le verifica validate.py:
    fonti = risorse assegnate, costo = risorse assegnate + fabbisogno."""
    if not s.get("fonti"):
        # Tabella B dei contratti che non stampano gli zeri: le colonne vuote
        # spostano fonti e fabbisogni e normalize.py non li legge
        return "fonti e fabbisogno per priorita' non leggibili"
    fin, cos = s.get("finanziato"), s.get("costo")
    fonti = s.get("fonti") or {}
    fab = s.get("fabbisogni") or {}
    note = []
    if fin is None or abs(fin - sum(v or 0 for v in fonti.values())) >= 0.1:
        note.append("fonti diverse dalle risorse assegnate")
    if cos is None or fin is None or abs(cos - fin - sum(v or 0 for v in fab.values())) >= 0.1:
        # succede per gli interventi la cui stima si ferma all'arco di Piano
        note.append("costo diverso da risorse + fabbisogno")
    return "; ".join(note) or "ok"


def main():
    D = json.load(open(sys.argv[1]))
    app2 = json.load(open(sys.argv[2]))
    out = sys.argv[3]
    ultimo = max(D["documenti"], key=lambda d: D["documenti"][d]["ordine"])
    if app2.get("doc") not in (None, ultimo):
        sys.exit("l'Appendice 2 e' di %s, l'ultimo aggiornamento e' %s" % (app2.get("doc"), ultimo))

    per_cod = {}
    for r in app2["righe"]:
        per_cod.setdefault(r["codice"], []).append(r)

    righe, tot = [], {"costo": 0.0, "fin": 0.0, "fonti": 0.0, "fab": 0.0, "n": 0}
    for p in D["progetti"]:
        s = next((s for s in p["storico"] if s["doc"] == ultimo), None)
        if s is None:
            continue
        cod = p["codice"]
        cups = [(c, "Tabella " + s["tabella"], "", "") for c in (s.get("cups") or [])]
        visti = {c for c, *_ in cups}
        for a in per_cod.get(cod, []):
            if a["cup"] not in visti:
                visti.add(a["cup"])
                cups.append((a["cup"], "Appendice 2", a.get("descr") or "", a.get("p") or ""))
        if not cups:
            cups = [("", "nessun CUP nel contratto", "", "")]

        t, cl, pn = s["tabella"], s.get("classe"), p.get("programma_num")
        prog, ct = ALB_CLASSI_TIP.get(pn or "", ("", ""))
        fonti = s.get("fonti") or {}
        fab = s.get("fabbisogni") or {}
        base = {
            "documento": ultimo, "pagina_pdf": s["pagina"],
            "tabella": t + " - " + ALB_TABELLE.get(t, ""),
            "tipologia_programma": (cl + " - " + CLASSI[cl]) if t == "A" and cl in CLASSI
            else ("Lotti costruttivi" if t == "B" else ""),
            "lettera_nel_pdf": s.get("classe_doc") or "",
            "programma": prog, "classe_tipologica": (pn + " - " + ct) if pn and ct else "",
            "codice_intervento": cod, "descrizione_intervento": p["descrizione"],
            "n_cup_intervento": len([c for c, *_ in cups if c]),
            "stato_attuativo": "|".join(s.get("stato") or []),
            "costo_totale_intervento_mln": r2(s.get("costo")),
            "finanziato_precedente_intervento_mln": r2(s.get("finanziato_precedente")),
            "riduzioni_intervento_mln": r2(s.get("riduzioni")),
            "rimodulazioni_intervento_mln": r2(s.get("rimodulazioni")),
            "incrementi_intervento_mln": r2(s.get("incrementi")),
            "risorse_assegnate_intervento_mln": r2(s.get("finanziato")),
            "mef_intervento_mln": r2(fonti.get("f_mef")), "fsc_pac_intervento_mln": r2(fonti.get("f_fsc_pac")),
            "mit_intervento_mln": r2(fonti.get("f_mit")), "pnrr_intervento_mln": r2(fonti.get("f_pnrr")),
            "altro_intervento_mln": r2(fonti.get("f_altro")),
            "fabbisogno_totale_intervento_mln": r2(s.get("da_finanziare")),
            "fabbisogno_priorita1_intervento_mln": r2(fab.get("fab_priorita1")),
            "fabbisogno_priorita2_intervento_mln": r2(fab.get("fab_priorita2")),
            "fabbisogno_completamento_intervento_mln": r2(fab.get("fab_completamento")),
            "speso_intervento_mln": r2(s.get("avanzamento")),
            "controllo": controllo(s),
        }
        n = max(1, base["n_cup_intervento"])
        base["cup_multipli"] = "si" if n > 1 else "no"
        base["ripartizione_per_cup"] = (
            "divisione in parti uguali fra %d CUP (convenzione, non nel contratto)" % n if n > 1
            else "un solo CUP: coincide con l'intervento" if base["n_cup_intervento"] == 1
            else "nessun CUP: importi dell'intervento")
        for k in PER_CUP:
            v = base[k + "_intervento_mln"]
            base[k + "_per_cup_mln"] = "" if v == "" else round(v / n, 4)
        for i, (cup, orig, ogg, pag) in enumerate(cups):
            righe.append({**base, "cup": cup, "origine_cup": orig, "oggetto_cup": ogg,
                          "pagina_appendice_2": pag, "riga_intervento": 1 if i == 0 else 0})
        if t == "A":
            tot["n"] += 1
            tot["costo"] += s.get("costo") or 0
            tot["fin"] += s.get("finanziato") or 0
            tot["fonti"] += sum(v or 0 for v in fonti.values())
            tot["fab"] += s.get("da_finanziare") or 0

    righe.sort(key=lambda r: (r["tabella"], r["classe_tipologica"], r["codice_intervento"], -r["riga_intervento"], r["cup"]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNE)
        w.writeheader()
        w.writerows(righe)

    # le somme sulle righe_intervento devono tornare con gli aggregati del
    # dataset, che validate.py confronta con i totali stampati
    agg = D["aggregati"][ultimo]
    print("%s: %d righe, %d interventi, %d CUP, %d senza CUP" % (
        out, len(righe), sum(r["riga_intervento"] for r in righe),
        sum(1 for r in righe if r["cup"]), sum(1 for r in righe if not r["cup"])))
    print("  Tabella A: costo %.2f (aggregati %.2f), assegnate %.2f (aggregati %.2f), "
          "somma fonti %.2f, fabbisogno %.2f (aggregati %.2f)" % (
              tot["costo"], agg["costo"], tot["fin"], agg["finanziato"], tot["fonti"],
              tot["fab"], agg["da_finanziare"]))
    # le quote per CUP, sommate su tutte le righe, devono ridare il totale degli interventi
    for k in PER_CUP:
        a = sum(r[k + "_per_cup_mln"] or 0 for r in righe)
        b = sum(r[k + "_intervento_mln"] or 0 for r in righe if r["riga_intervento"])
        if abs(a - b) > 0.5:
            sys.exit("quote per CUP di %s: %.2f contro %.2f degli interventi" % (k, a, b))
    print("  quote per CUP: sommate su tutte le righe tornano con gli interventi; %d interventi con piu' CUP" %
          sum(1 for r in righe if r["riga_intervento"] and r["cup_multipli"] == "si"))
    nko = sum(1 for r in righe if r["riga_intervento"] and r["controllo"] != "ok")
    print("  interventi con controllo non ok: %d" % nko)


if __name__ == "__main__":
    main()
