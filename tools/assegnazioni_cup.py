"""Le assegnazioni dell'ultimo aggiornamento Investimenti: un file per CUP e
uno per intervento.

assegnazioni-interventi-agg2025.csv, una riga per intervento delle Tabelle A
e B: tipologia, classe tipologica, costo, movimenti dell'anno (finanziato
precedente, riduzioni, rimodulazioni, incrementi), assegnate per fonte,
fabbisogno per priorita', speso, numero e lista dei CUP. Sono gli importi
scritti nel contratto.

assegnazioni-cup-agg2025.csv, una riga per CUP (piu' una per ciascuno dei
cinque interventi senza CUP). Un CUP puo' stare sotto piu' interventi: le fasi
di uno stesso progetto (0049A e 0049B), un'opera che e' anche in un programma
(P111 e P194), due programmi (P221 e P222). Fino a tre interventi per CUP,
nelle colonne intervento_1..3 con i loro importi (importi dell'intervento
intero, come nel contratto). Le colonne *_per_cup_mln sono la quota del CUP:
per ogni suo intervento, l'importo diviso per il numero di CUP di
quell'intervento, sommato sugli interventi. E' una convenzione chiesta
dall'utente, non un dato del contratto (le schede dell'Appendice 3 mostrano
CUP dello stesso programma con importi molto diversi: in NA026 da 0,2 a 1.129
mln). Sommate su tutte le righe, le quote ridanno i totali degli interventi.

I CUP vengono dalle tabelle e, per i programmi, dall'Appendice 2 alla
Relazione Informativa (un CUP per oggetto, senza importi).

Uso:
  python3 assegnazioni_cup.py ../data/cdp-rfi-dataset.json ../data/appendice-cup-agg2025.json \
          ../data/assegnazioni-cup-agg2025.csv ../data/assegnazioni-interventi-agg2025.csv
"""
import csv
import json
import re
import sys

from schema import ALB_CLASSI_TIP, ALB_TABELLE, CLASSI

MAX_INT = 3
# gli importi che seguono il CUP; i movimenti dell'anno e le priorita' del
# fabbisogno restano nel file degli interventi, altrimenti per tre interventi
# il file dei CUP passerebbe le ottanta colonne
IMPORTI = ["costo_totale", "risorse_assegnate", "mef", "fsc_pac", "mit", "pnrr", "altro",
           "fabbisogno_totale", "speso"]

COL_INT = [
    "documento", "codice_intervento", "descrizione_intervento", "pagina_pdf", "tabella",
    "tipologia_programma", "lettera_nel_pdf", "programma", "classe_tipologica",
    "stato_attuativo", "n_cup", "cup", "cup_condivisi_con_altri_interventi",
    "costo_totale_mln", "finanziato_precedente_mln", "riduzioni_mln", "rimodulazioni_mln",
    "incrementi_mln", "risorse_assegnate_mln", "mef_mln", "fsc_pac_mln", "mit_mln",
    "pnrr_mln", "altro_mln", "fabbisogno_totale_mln", "fabbisogno_priorita1_mln",
    "fabbisogno_priorita2_mln", "fabbisogno_completamento_mln", "speso_mln", "controllo",
]
COL_CUP = (
    ["documento", "cup", "oggetto_cup", "pagina_appendice_2", "n_interventi",
     "cup_su_piu_interventi", "tipo_condivisione", "tabella", "tipologia_programma",
     "programma", "classe_tipologica", "classificazione_uguale_fra_interventi"]
    + [c % k for k in range(1, MAX_INT + 1) for c in (
        "intervento_%d", "descrizione_intervento_%d", "origine_cup_intervento_%d",
        "pagina_pdf_intervento_%d", "n_cup_intervento_%d")]
    + ["%s_intervento_%d_mln" % (n, k) for k in range(1, MAX_INT + 1) for n in IMPORTI]
    + ["ripartizione_per_cup"] + ["%s_per_cup_mln" % n for n in IMPORTI]
)


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


def base_codice(c):
    # 0049A e 0049B, P238A e P238B: fasi o lotti dello stesso intervento
    return re.sub(r"[A-Z]$", "", c)


def main():
    D = json.load(open(sys.argv[1]))
    app2 = json.load(open(sys.argv[2]))
    out_cup, out_int = sys.argv[3], sys.argv[4]
    ultimo = max(D["documenti"], key=lambda d: D["documenti"][d]["ordine"])
    if app2.get("doc") not in (None, ultimo):
        sys.exit("l'Appendice 2 e' di %s, l'ultimo aggiornamento e' %s" % (app2.get("doc"), ultimo))
    per_cod = {}
    for r in app2["righe"]:
        per_cod.setdefault(r["codice"], []).append(r)

    interventi, tot = [], {"costo": 0.0, "fin": 0.0, "fab": 0.0}
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
        t, cl, pn = s["tabella"], s.get("classe"), p.get("programma_num")
        prog, ct = ALB_CLASSI_TIP.get(pn or "", ("", ""))
        fonti = s.get("fonti") or {}
        fab = s.get("fabbisogni") or {}
        tp = (cl + " - " + CLASSI[cl]) if t == "A" and cl in CLASSI else ("Lotti costruttivi" if t == "B" else "")
        if s.get("classe_doc") and t == "A":
            # la tipologia come la stampa il PDF di questo aggiornamento: dal 2024
            # "Interventi in programma" ha la lettera d (normalize.py la chiama e
            # per confrontare i contratti; qui si legge un contratto solo)
            tp = s["classe_doc"] + tp[1:]
        interventi.append({
            "documento": ultimo, "codice_intervento": cod, "descrizione_intervento": p["descrizione"],
            "pagina_pdf": s["pagina"], "tabella": t + " - " + ALB_TABELLE.get(t, ""),
            "tipologia_programma": tp, "lettera_nel_pdf": s.get("classe_doc") or "",
            "programma": prog, "classe_tipologica": (pn + " - " + ct) if pn and ct else "",
            "stato_attuativo": "|".join(s.get("stato") or []),
            "n_cup": len(cups), "_cups": cups,
            "costo_totale_mln": r2(s.get("costo")),
            "finanziato_precedente_mln": r2(s.get("finanziato_precedente")),
            "riduzioni_mln": r2(s.get("riduzioni")), "rimodulazioni_mln": r2(s.get("rimodulazioni")),
            "incrementi_mln": r2(s.get("incrementi")), "risorse_assegnate_mln": r2(s.get("finanziato")),
            "mef_mln": r2(fonti.get("f_mef")), "fsc_pac_mln": r2(fonti.get("f_fsc_pac")),
            "mit_mln": r2(fonti.get("f_mit")), "pnrr_mln": r2(fonti.get("f_pnrr")),
            "altro_mln": r2(fonti.get("f_altro")),
            "fabbisogno_totale_mln": r2(s.get("da_finanziare")),
            "fabbisogno_priorita1_mln": r2(fab.get("fab_priorita1")),
            "fabbisogno_priorita2_mln": r2(fab.get("fab_priorita2")),
            "fabbisogno_completamento_mln": r2(fab.get("fab_completamento")),
            "speso_mln": r2(s.get("avanzamento")), "controllo": controllo(s),
        })
        if t == "A":
            tot["costo"] += s.get("costo") or 0
            tot["fin"] += s.get("finanziato") or 0
            tot["fab"] += s.get("da_finanziare") or 0

    # dal CUP agli interventi: le tabelle prima dell'Appendice 2, poi per codice
    per_cup = {}
    for it in interventi:
        for c, orig, ogg, pag in it["_cups"]:
            per_cup.setdefault(c, []).append((it, orig, ogg, pag))
    for c in per_cup:
        per_cup[c].sort(key=lambda x: (x[1] == "Appendice 2", x[0]["codice_intervento"]))
        if len(per_cup[c]) > MAX_INT:
            sys.exit("il CUP %s e' sotto %d interventi: il file ne prevede %d" % (c, len(per_cup[c]), MAX_INT))
    for it in interventi:
        it["cup"] = "|".join(c for c, *_ in it["_cups"])
        it["cup_condivisi_con_altri_interventi"] = "|".join(
            c + " (" + ",".join(x[0]["codice_intervento"] for x in per_cup[c] if x[0] is not it) + ")"
            for c, *_ in it["_cups"] if len(per_cup[c]) > 1)

    def riga(cup, voci):
        """voci: [(intervento, origine, oggetto, pagina)], una per intervento."""
        r = {k: "" for k in COL_CUP}
        it0 = voci[0][0]
        r.update({"documento": ultimo, "cup": cup, "n_interventi": len(voci),
                  "cup_su_piu_interventi": "si" if len(voci) > 1 else "no",
                  "oggetto_cup": next((o for _, _, o, _ in voci if o), ""),
                  "pagina_appendice_2": next((p for _, _, _, p in voci if p), ""),
                  "tabella": it0["tabella"], "tipologia_programma": it0["tipologia_programma"],
                  "programma": it0["programma"], "classe_tipologica": it0["classe_tipologica"]})
        if len(voci) > 1:
            cod = [v[0]["codice_intervento"] for v in voci]
            orig = [v[1] for v in voci]
            r["tipo_condivisione"] = (
                "fasi o lotti dello stesso intervento" if len({base_codice(x) for x in cod}) == 1
                else "in piu' programmi (Appendice 2)" if all(o == "Appendice 2" for o in orig)
                else "opera in tabella e anche in un programma (Appendice 2)" if "Appendice 2" in orig
                else "interventi diversi in tabella")
            r["classificazione_uguale_fra_interventi"] = "si" if len(
                {(v[0]["tipologia_programma"], v[0]["classe_tipologica"]) for v in voci}) == 1 else "no"
        quota = {n: 0.0 for n in IMPORTI}
        parti = []
        for k, (it, orig, _, _) in enumerate(voci, 1):
            n = max(1, it["n_cup"])
            r.update({"intervento_%d" % k: it["codice_intervento"],
                      "descrizione_intervento_%d" % k: it["descrizione_intervento"],
                      "origine_cup_intervento_%d" % k: orig, "pagina_pdf_intervento_%d" % k: it["pagina_pdf"],
                      "n_cup_intervento_%d" % k: it["n_cup"]})
            for nome in IMPORTI:
                v = it[nome + "_mln"]
                r["%s_intervento_%d_mln" % (nome, k)] = v
                quota[nome] += (v or 0) / n
            parti.append("%s / %d CUP" % (it["codice_intervento"], n) if n > 1 else
                         "%s intero" % it["codice_intervento"])
        for nome in IMPORTI:
            r[nome + "_per_cup_mln"] = round(quota[nome], 4)
        unico = len(voci) == 1 and voci[0][0]["n_cup"] <= 1
        r["ripartizione_per_cup"] = ("nessun CUP: importi dell'intervento" if not cup else
                                     "coincide con l'intervento (un solo CUP)" if unico else
                                     " + ".join(parti) + " (convenzione, non nel contratto)")
        return r

    righe = [riga(c, voci) for c, voci in per_cup.items()]
    righe += [riga("", [(it, "nessun CUP nel contratto", "", "")]) for it in interventi if not it["_cups"]]
    righe.sort(key=lambda r: (r["tabella"], r["classe_tipologica"], r["intervento_1"], r["cup"]))

    with open(out_cup, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COL_CUP)
        w.writeheader()
        w.writerows(righe)
    with open(out_int, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COL_INT, extrasaction="ignore")
        w.writeheader()
        w.writerows(interventi)

    # controlli: gli interventi tornano con gli aggregati della Tabella A, e le
    # quote per CUP sommate su tutte le righe ridanno i totali degli interventi
    agg = D["aggregati"][ultimo]
    for a, b, n in ((tot["costo"], agg["costo"], "costo"), (tot["fin"], agg["finanziato"], "assegnate"),
                    (tot["fab"], agg["da_finanziare"], "fabbisogno")):
        if abs(a - b) > 0.5:
            sys.exit("Tabella A, %s: %.2f contro %.2f degli aggregati" % (n, a, b))
    for nome in IMPORTI:
        a = sum(r[nome + "_per_cup_mln"] for r in righe)
        b = sum(it[nome + "_mln"] or 0 for it in interventi)
        if abs(a - b) > 0.5:
            sys.exit("quote per CUP di %s: %.2f contro %.2f degli interventi" % (nome, a, b))
    cond = [r for r in righe if r["cup_su_piu_interventi"] == "si"]
    print("%s: %d righe, %d CUP distinti, %d su piu' interventi, %d interventi senza CUP" % (
        out_cup, len(righe), sum(1 for r in righe if r["cup"]), len(cond),
        sum(1 for r in righe if not r["cup"])))
    print("  tipi di condivisione: " + ", ".join("%s %d" % (t, sum(1 for r in cond if r["tipo_condivisione"] == t))
                                                   for t in sorted({r["tipo_condivisione"] for r in cond})))
    print("%s: %d interventi; Tabella A costo %.2f, assegnate %.2f, fabbisogno %.2f, uguali agli aggregati; "
          "quote per CUP ok" % (out_int, len(interventi), tot["costo"], tot["fin"], tot["fab"]))


if __name__ == "__main__":
    main()
