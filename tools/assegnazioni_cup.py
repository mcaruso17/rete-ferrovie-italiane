"""Le assegnazioni dell'ultimo aggiornamento Investimenti, una riga per CUP.

Per ogni intervento delle Tabelle A e B: costo, movimenti dell'anno
(riduzioni, rimodulazioni, incrementi), risorse assegnate per fonte (MEF, FSC,
MIT, PNRR, altro) e fabbisogno per priorita', con tipologia di programma e
classe tipologica dell'alberatura.

L'unita' e' il CUP, ma il contratto non divide gli importi per CUP: li stampa
per intervento. Un intervento con piu' CUP ha quindi una riga per CUP con gli
importi dell'intervento ripetuti, e solo la prima ha riga_intervento = 1: le
somme si fanno su quelle, altrimenti l'intervento conta tante volte quanti
sono i suoi CUP. Un intervento senza CUP ha una riga sola con il CUP vuoto.

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
    "riga_intervento", "stato_attuativo",
    "costo_totale_mln", "finanziato_precedente_mln", "riduzioni_mln",
    "rimodulazioni_mln", "incrementi_mln", "risorse_assegnate_mln",
    "mef_mln", "fsc_pac_mln", "mit_mln", "pnrr_mln", "altro_mln",
    "fabbisogno_totale_mln", "fabbisogno_priorita1_mln", "fabbisogno_priorita2_mln",
    "fabbisogno_completamento_mln", "speso_mln", "controllo",
]


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
            "costo_totale_mln": r2(s.get("costo")),
            "finanziato_precedente_mln": r2(s.get("finanziato_precedente")),
            "riduzioni_mln": r2(s.get("riduzioni")),
            "rimodulazioni_mln": r2(s.get("rimodulazioni")),
            "incrementi_mln": r2(s.get("incrementi")),
            "risorse_assegnate_mln": r2(s.get("finanziato")),
            "mef_mln": r2(fonti.get("f_mef")), "fsc_pac_mln": r2(fonti.get("f_fsc_pac")),
            "mit_mln": r2(fonti.get("f_mit")), "pnrr_mln": r2(fonti.get("f_pnrr")),
            "altro_mln": r2(fonti.get("f_altro")),
            "fabbisogno_totale_mln": r2(s.get("da_finanziare")),
            "fabbisogno_priorita1_mln": r2(fab.get("fab_priorita1")),
            "fabbisogno_priorita2_mln": r2(fab.get("fab_priorita2")),
            "fabbisogno_completamento_mln": r2(fab.get("fab_completamento")),
            "speso_mln": r2(s.get("avanzamento")),
            "controllo": controllo(s),
        }
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
    nko = sum(1 for r in righe if r["riga_intervento"] and r["controllo"] != "ok")
    print("  interventi con controllo non ok: %d" % nko)


if __name__ == "__main__":
    main()
