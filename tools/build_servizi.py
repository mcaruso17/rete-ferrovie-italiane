"""Porta nella piattaforma le tabelle finanziarie della parte Servizi.

Legge data/servizi/fin-<edizione>.json (prodotti da extract_servizi_fin.py) e
scrive app["servizi"], la base di tutte le viste Servizi del sito.

Che cosa c'e' e che cosa no. La parte Servizi finanzia la gestione della rete e
la manutenzione, non opere: non ha un portafoglio di interventi con costo e
copertura come la Tabella A. Ha quattro cose, ed e' su queste che il sito
costruisce le sue viste:

- le fonti per cassa per legge e capitolo (4b), in ogni edizione leggibile;
- gli impieghi per competenza (4a), solo nel contratto base;
- le assegnazioni dai fondi straordinari per CUP (4c), l'unico dettaglio per
  progetto: una frazione piccola del totale, e va detto;
- le opere PNRR attribuite al CdP-S (Allegato 12), con la regione nel nome.

Regione dal nome. Le righe PNRR dicono "ambito regione Sicilia": la regione e'
scritta dal documento, non dedotta. Quando il nome ne elenca piu' d'una
("Basilicata / Campania / Calabria") il documento non dice le quote, e la
ripartizione in parti uguali e' una scelta del sito: la riga lo dichiara.

Uso:
  python3 build_servizi.py DIR_SERVIZI app.json [app-out.json]
"""
import json
import os
import re
import sys

DIR, APP = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else APP

EDIZIONI = [
    ("cdps2022", 2022, "CdP-S 2022-2026 (contratto base)", "CdP_Servizi_2022-2026.pdf"),
    ("srv2023", 2023, "CdP-S 2022-2026 - primo atto integrativo (agg. 2023)",
     "CdP_Servizi_2022-2026_AI1_Agg2023.pdf"),
    ("srv2024", 2024, "CdP-S 2022-2026 - secondo atto integrativo (agg. 2024)",
     "CdP_Servizi_2022-2026_AI2_Agg2024.pdf"),
    ("srv2025", 2025, "CdP-S 2022-2026 - terzo atto integrativo (agg. 2025)",
     "CdP_Servizi_2022-2026_AI3_Agg2025.pdf"),
    ("srv2026", 2026, "CdP-S 2022-2026 - quarto atto integrativo (agg. 2026)",
     "CdP_Servizi_2022-2026_AI4_Agg2026.pdf"),
]
ANNI = ["2022", "2023", "2024", "2025", "2026"]

# i nomi delle regioni come li scrive l'Allegato 12, sui codici ISTAT del sito
REGIONI = {"piemonte": "01", "valle d'aosta": "02", "lombardia": "03",
           "trentino": "04", "veneto": "05", "friuli": "06", "liguria": "07",
           "emilia": "08", "toscana": "09", "umbria": "10", "marche": "11",
           "lazio": "12", "abruzzo": "13", "molise": "14", "campania": "15",
           "puglia": "16", "basilicata": "17", "calabria": "18",
           "sicilia": "19", "sardegna": "20"}

# le Direzioni Operative Infrastrutture Territoriali hanno sede in una citta':
# e' la sede, non il territorio servito, e la pagina lo dice
DOIT = ["Torino", "Milano", "Genova", "Venezia", "Verona", "Trieste", "Bologna",
        "Firenze", "Ancona", "Roma", "Napoli", "Bari", "Reggio Calabria",
        "Palermo", "Cagliari"]


def sezione(rigo):
    return {"1": "esercizio", "2": "impianti", "3": "totale",
            "4": "spesa_residuo", "5": "residuo"}[rigo[0]]


def riga_fonte(r):
    v = r["valori"]
    return {"r": r["rigo"], "v": re.sub(r"\s+", " ", r["voce"]).strip(),
            "c": r["capitolo"] if r["capitolo"] not in (None, "n.a.") else "",
            "s": sezione(r["rigo"]), "a": [v.get(a) for a in ANNI],
            "t": v.get("tot"), "o": v.get("oltre"), "pm": v.get("pm"),
            "k": v.get("compl"), "p": r["pagina"]}


def sede(descr):
    for d in sorted(DOIT, key=len, reverse=True):
        if re.search(r"\b(?:DOIT|Linee)\s+" + re.escape(d) + r"\b", descr):
            return d
    return ""


def main():
    app = json.load(open(APP, encoding="utf-8"))
    ed, fonti, impieghi, controlli = [], {}, {}, {}
    ultimo = {}
    for doc, anno, titolo, pdf in EDIZIONI:
        f = os.path.join(DIR, "fin-%s.json" % doc)
        dati = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
        leggibile = bool(dati.get("fonti"))
        ed.append({"id": doc, "anno": anno, "titolo": titolo, "file": pdf,
                   "leggibile": leggibile,
                   "pagine": dati.get("pagine", {}),
                   "scansioni": dati.get("pagine_senza_testo", 0)})
        controlli[doc] = dati.get("controlli", {"fatti": 0, "tornano": 0})
        if leggibile:
            fonti[doc] = [riga_fonte(r) for r in dati["fonti"]]
        if dati.get("impieghi"):
            impieghi[doc] = [riga_fonte(r) for r in dati["impieghi"]]
        for k in ("assegnazioni", "pnrr"):
            if dati.get(k):
                ultimo[k] = (doc, dati[k])

    # Le assegnazioni: si usa l'ultima edizione che le elenca. Il 4c dell'atto
    # 2026 ripubblica per intero quelle degli atti precedenti, ciascuna con il
    # suo atto integrativo, quindi non si somma nulla fra edizioni.
    ass = []
    doc_a, righe_a = ultimo.get("assegnazioni", ("", []))
    for r in righe_a:
        ass.append({"cup": r["cup"], "d": r["descrizione"], "f": r["fonte"],
                    "atto": r["atto"], "rif": r["riferimento"],
                    "prec": r["prec"], "corr": r["corr"], "t": r["totale"],
                    "sede": sede(r["descrizione"]), "doc": doc_a, "p": r["pagina"]})

    pnrr = []
    doc_p, righe_p = ultimo.get("pnrr", ("", []))
    for r in righe_p:
        im = r["importi"]
        regs = [c for n, c in REGIONI.items() if re.search(r"\b" + n, r["intervento"].lower())]
        pnrr.append({"cup": r["cup"], "m": r["misura"], "n": r["intervento"],
                     "pnrr": im[0], "altri": round(im[3] + im[4], 2), "t": im[-1],
                     "reg": regs, "doc": doc_p, "p": r["pagina"]})

    app["servizi"] = {"edizioni": ed, "fonti": fonti, "impieghi": impieghi,
                      "assegnazioni": ass, "pnrr": pnrr, "controlli": controlli}
    json.dump(app, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))

    lg = [e["id"] for e in ed if e["leggibile"]]
    print("servizi: %d edizioni, leggibili %s" % (len(ed), ", ".join(lg)))
    for e in ed:
        if not e["leggibile"]:
            print("   %s: nessun prospetto leggibile (%d pagine in scansione)"
                  % (e["id"], e["scansioni"]))
    if lg:
        t = next(r for r in fonti[lg[-1]] if r["r"] == "3")
        print("   ultima edizione: fonti 2022-2026 %.2f, complessivo %.2f mln"
              % (t["t"], t["k"]))
    print("   assegnazioni per CUP: %d (%.2f mln), da %s" %
          (len(ass), sum(a["t"] or 0 for a in ass), doc_a))
    print("   PNRR attribuito al CdP-S: %d CUP (%.2f mln), da %s" %
          (len(pnrr), sum(p["pnrr"] for p in pnrr), doc_p))
    senza = [p["cup"] for p in pnrr if not p["reg"]]
    if senza:
        print("   ATTENZIONE: PNRR senza regione nel nome: %s" % senza)


if __name__ == "__main__":
    main()
