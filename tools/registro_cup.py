"""Registro unico dei CUP: parte Investimenti (in corso e opere concluse) e
parte Servizi, una riga per CUP, con lo stato e il documento da cui viene.

Le fonti, tutte lette dai PDF dei contratti:
- in corso: Tabelle A e B dell'ultimo aggiornamento Investimenti, i CUP che
  quel contratto scrive sotto ogni intervento (Tabella A nella vista per status
  attuativo: la vista per classe ripete gli stessi interventi);
- conclusi: il dettaglio delle opere ultimate (Tabella C) di ogni edizione.
  Ogni edizione elenca le opere entrate in esercizio nel suo periodo, quindi le
  edizioni si sommano: di un CUP si tiene l'ultima in cui compare. La
  descrizione e' quella della voce della tabella (E.1 manutenzione
  straordinaria, E.2 sviluppo infrastrutturale...), non il nome dell'opera;
- non piu' nel contratto: CUP di interventi delle Tabelle A e B dei contratti
  precedenti che l'ultimo aggiornamento non riporta piu' e che non sono fra le
  opere ultimate;
- Servizi: assegnazioni per CUP dell'Allegato 4c e opere PNRR dell'Allegato 12
  dell'ultima edizione Servizi. Il contratto Servizi non dice se l'opera e'
  conclusa;
- in corso, dai programmi: l'Appendice 2 alla Relazione Informativa
  dell'ultimo aggiornamento ("Dettaglio CUP riferiti ai programmi"), che per i
  programmi (sicurezza in galleria, tecnologie...) elenca i CUP che le tabelle
  non scrivono, uno per oggetto, con la descrizione. Facoltativa: quinto
  argomento, il JSON di extract_appendice_cup.py.

Uno stesso CUP puo' stare in piu' fonti (un intervento in corso con lotti gia'
ultimati): lo stato segue la fonte piu' "viva" (in corso, poi concluso), e le
altre restano segnate.

Uso:
  python3 registro_cup.py ../data/cdp-rfi-dataset.json app-in.json app-out.json ../data/cup-registro.csv \
          [../data/appendice-cup-agg2025.json]
"""
import csv
import json
import os
import sys

from schema import ALB_TABELLE, ALB_CLASSI_TIP, ALB_VOCI_C, CLASSI

ORDINE = {}


# quanto del portafoglio dell'ultimo aggiornamento sta sotto un CUP, per
# intervento: CUP scritto in tabella (opera singola); CUP solo nell'Appendice 2
# (i programmi pluriennali: i CUP sono dei sottoprogetti e non hanno importi,
# quindi non si sa quanta parte del programma coprano); CUP scritto solo nei
# contratti precedenti; nessun CUP in nessun documento
COPERTURA = [
    ("tabella", "CUP nella tabella", "opera singola, il CUP è scritto sotto l'intervento"),
    ("app2", "CUP dei sottoprogetti (Appendice 2)", "programma pluriennale: CUP senza importi, copertura del programma non nota"),
    ("prec", "CUP solo nei contratti precedenti", "non riportato nell'ultimo aggiornamento"),
    ("no", "Nessun CUP", "in nessun documento del contratto"),
]


def copertura(D, ultimo, cod_app2):
    out = []
    for p in D["progetti"]:
        s = next((s for s in p["storico"] if s["doc"] == ultimo), None)
        if s is None:
            continue
        if s.get("cups"):
            cat = "tabella"
        elif p["codice"] in cod_app2:
            cat = "app2"
        elif p.get("cups_tutti"):
            cat = "prec"
        else:
            cat = "no"
        cl = "B" if s["tabella"] == "B" else s.get("classe")
        r2 = lambda x: round(x or 0, 2)
        out.append([p["codice"], cat, cl, p.get("programma_num"), r2(s.get("costo")), r2(s.get("finanziato")),
                    r2(s.get("da_finanziare")), r2(s.get("avanzamento")), "|".join(s.get("cups") or [])])
    return out


def alberatura(v):
    """La posizione del CUP nell'alberatura del portafoglio, dalla fonte che ne
    decide lo stato: intervento in corso (Tabelle A e B, poi Appendice 2),
    opera ultimata (Tabella C, per voce), intervento di un contratto
    precedente. I CUP dei soli Servizi non ne hanno una."""
    y = (v["inv"] or [None])[0] or next((a for a in v["app"] if a.get("t")), None)
    prec = False
    if y is None and v["ult"]:
        vc = v["ult"]["voce"]
        return {"k": {"t": "C", "v": vc}, "tabella": "C - " + ALB_TABELLE["C"],
                "tipologia": (vc + " - " + ALB_VOCI_C[vc]) if vc in ALB_VOCI_C else (vc or "")}
    if y is None and v["prec"]:
        y, prec = max(v["prec"], key=lambda z: ORDINE.get(z["doc"], 0)), True
    if y is None or not y.get("t"):
        return {}
    t, cl, pn = y["t"], y.get("cl"), y.get("pn")
    pr, ct = ALB_CLASSI_TIP.get(pn or "", ("", ""))
    k = {"t": t, "cl": cl, "pn": pn, "c": y["c"]}
    if prec:
        k["doc"] = y["doc"]
    return {"k": k, "tabella": t + " - " + ALB_TABELLE.get(t, ""),
            "tipologia": (cl + " - " + CLASSI[cl]) if cl in CLASSI else ("Lotti costruttivi" if t == "B" else ""),
            "programma": pr, "classe_tip": (pn + " - " + ct) if pn else "",
            "intervento": y["c"] + (" (" + y["doc"] + ")" if prec else "")}


def main():
    D = json.load(open(sys.argv[1], encoding="utf-8"))
    A = json.load(open(sys.argv[2], encoding="utf-8"))
    uscita, dest_csv = sys.argv[3], sys.argv[4]

    for k, d in D["documenti"].items():
        ORDINE[k] = d.get("ordine") or 0
    # l'ultimo contratto con una Tabella A (l'aggiornamento 2023 non ne ha)
    ultimo = max((k for k, d in D["documenti"].items() if (d.get("righe_tabella_a") or 0) > 0),
                 key=lambda k: ORDINE[k])
    R = {}
    # classe, tabella e programma di ogni intervento nell'ultimo contratto
    ULT = {p["codice"]: (s.get("classe"), s.get("tabella"), p.get("programma_num"))
           for p in D["progetti"] for s in p["storico"] if s["doc"] == ultimo}

    def voce(cup):
        return R.setdefault(cup, {"cup": cup, "inv": [], "app": [], "ult": None, "prec": [], "srv": []})

    for p in D["progetti"]:
        for s in p["storico"]:
            for cup in s.get("cups") or []:
                # tabella, classe e programma di quel contratto: l'alberatura
                # del CUP si legge dalla fonte che ne decide lo stato
                x = {"c": p["codice"], "n": p["descrizione"], "cl": s.get("classe"),
                     "t": s.get("tabella"), "pn": p.get("programma_num"),
                     "costo": s.get("costo"), "doc": s["doc"], "p": s["pagina"]}
                v = voce(cup)
                if s["doc"] == ultimo:
                    if not any(y["c"] == x["c"] for y in v["inv"]):
                        v["inv"].append(x)
                elif not any(y["c"] == x["c"] for y in v["prec"]):
                    v["prec"].append(x)
    for u in D["opere_ultimate"]:
        if not u.get("cup"):
            continue
        v = voce(u["cup"])
        if v["ult"] is None or ORDINE.get(u["doc"], 0) >= ORDINE.get(v["ult"]["doc"], 0):
            # nel 2022-2026 la riga senza voce e' la rete AV/AC Torino-Milano-Napoli
            vc = u.get("riga") or ("A5000_0" if u["doc"] != "cdp2017" else None)
            v["ult"] = {"doc": u["doc"], "p": u["page"], "npp": u.get("npp"), "voce": vc,
                        "n": u.get("descr"), "data": u.get("data_esercizio"), "costo": u.get("costo")}
    # l'Appendice 2: i CUP dei programmi, con il file per il rimando al PDF
    extra = []
    if len(sys.argv) > 5:
        AP = json.load(open(sys.argv[5], encoding="utf-8"))
        did = "app2-" + AP["doc"]
        extra.append({"id": did, "titolo": "Appendice 2 alla Relazione Informativa, "
                      + ((D["documenti"].get(AP["doc"]) or {}).get("titolo") or AP["doc"]),
                      "file": "cdpi-" + AP["doc"] + "/" + AP["documento"],
                      "anno": (D["documenti"].get(AP["doc"]) or {}).get("anno")})
        ORDINE[did] = ORDINE.get(AP["doc"], 0)
        for r in AP["righe"]:
            v = voce(r["cup"])
            q = ULT.get(r["codice"])
            if not any(y["c"] == r["codice"] and y["n"] == r["descr"] for y in v["app"]):
                v["app"].append({"c": r["codice"], "n": r["descr"], "tab": r["tab"], "doc": did, "p": r["p"],
                                 **({"cl": q[0], "t": q[1], "pn": q[2]} if q else {})})
    S = A.get("servizi") or {}
    for a in S.get("assegnazioni") or []:
        voce(a["cup"])["srv"].append({"all": "4c", "n": a.get("d"), "f": a.get("f"), "t": a.get("t"),
                                      "doc": a["doc"], "p": a["p"], "sede": a.get("sede")})
    for a in S.get("pnrr") or []:
        voce(a["cup"])["srv"].append({"all": "12", "n": a.get("n"), "f": "PNRR " + (a.get("m") or ""),
                                      "t": a.get("t"), "doc": a["doc"], "p": a["p"]})

    righe, app = [], []
    for cup, v in sorted(R.items()):
        if v["inv"] or v["app"]:
            stato = "in corso"
        elif v["ult"]:
            stato = "concluso"
        elif v["srv"]:
            stato = "servizi"
        else:
            stato = "non piu' nel contratto"
        parti = (["Investimenti"] if (v["inv"] or v["app"] or v["ult"] or v["prec"]) else []) + (["Servizi"] if v["srv"] else [])
        # la fonte principale: quella che decide lo stato
        if v["inv"]:
            f0 = v["inv"][0]; descr = f0["n"]; doc, pag = f0["doc"], f0["p"]
            fonte = "Tabella A/B"
        elif v["app"]:
            f0 = v["app"][0]; descr = f0["n"]; doc, pag = f0["doc"], f0["p"]
            fonte = "Appendice 2 (CUP dei programmi)"
        elif v["ult"]:
            f0 = v["ult"]; descr = f0["n"]; doc, pag = f0["doc"], f0["p"]
            fonte = "Opere ultimate (Tabella C)"
        elif v["srv"]:
            f0 = v["srv"][0]; descr = f0["n"]; doc, pag = f0["doc"], f0["p"]
            fonte = "Servizi, Allegato " + f0["all"]
        else:
            f0 = max(v["prec"], key=lambda y: ORDINE.get(y["doc"], 0)); descr = f0["n"]
            doc, pag = f0["doc"], f0["p"]
            fonte = "Tabella A/B di un contratto precedente"
        al = alberatura(v)
        righe.append([
            cup, stato, "+".join(parti), fonte, descr or "",
            "|".join(y["c"] for y in v["inv"]),
            "|".join(dict.fromkeys(y["c"] for y in v["app"])),
            " | ".join(dict.fromkeys(y["n"] for y in v["app"])),
            "|".join(sorted({y["c"] for y in v["prec"]} - {y["c"] for y in v["inv"]})),
            v["ult"]["doc"] if v["ult"] else "", v["ult"]["data"] if v["ult"] else "",
            (v["ult"]["voce"] or "") if v["ult"] else "", (v["ult"]["npp"] or "") if v["ult"] else "",
            "|".join(sorted({"Allegato " + y["all"] for y in v["srv"]})),
            round(sum(y["t"] or 0 for y in v["srv"]), 2) if v["srv"] else "",
            doc, pag] + [al.get(k, "") for k in ("tabella", "tipologia", "programma", "classe_tip", "intervento")])
        app.append({"cup": cup, "st": stato, **({"alb": al["k"]} if al else {}), "inv": v["inv"], "app": v["app"], "ult": v["ult"],
                    "prec": v["prec"], "srv": v["srv"]})

    with open(dest_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cup", "stato", "parte", "fonte_principale", "descrizione",
                    "interventi_ultimo_contratto", "programmi_appendice_2", "oggetto_appendice_2",
                    "interventi_contratti_precedenti",
                    "opere_ultimate_edizione", "data_messa_in_esercizio", "opere_ultimate_voce",
                    "opere_ultimate_npp", "servizi_allegati", "servizi_importo_mln",
                    "documento", "pagina", "alberatura_tabella", "alberatura_tipologia_programma",
                    "alberatura_programma", "alberatura_classe_tipologica", "alberatura_intervento"])
        w.writerows(righe)
    cop = copertura(D, ultimo, {y["c"] for v in R.values() for y in v["app"]})
    with open(os.path.join(os.path.dirname(dest_csv) or ".", "copertura-cup-%s.csv" % ultimo), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["codice", "copertura_cup", "tabella", "classe", "classe_tipologica", "costo_mln", "assegnate_mln",
                    "da_finanziare_mln", "speso_mln", "cup_in_tabella"])
        nomi = {k: t for k, t, _d in COPERTURA}
        for r in cop:
            w.writerow([r[0], nomi[r[1]], "B" if r[2] == "B" else "A", "" if r[2] == "B" else r[2] or "", r[3] or ""] + r[4:8] + [r[8]])
    A["cup_registro"] = {"ultimo": ultimo, "righe": app, "documenti": extra,
                         "copertura": {"cat": [list(x) for x in COPERTURA], "righe": [r[:8] for r in cop]}}
    json.dump(A, open(uscita, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    from collections import Counter
    c = Counter(r[1] for r in righe)
    print("registro dei CUP: %d CUP distinti; %s" % (len(righe), ", ".join("%s %d" % kv for kv in sorted(c.items()))))
    print("  in corso: %d dalle Tabelle A e B, %d dall'Appendice 2, %d in entrambe; "
          "in corso e anche fra le opere ultimate: %d; Investimenti e Servizi: %d"
          % (sum(1 for x in app if x["inv"]), sum(1 for x in app if x["app"]),
             sum(1 for x in app if x["inv"] and x["app"]),
             sum(1 for x in app if (x["inv"] or x["app"]) and x["ult"]),
             sum(1 for x in app if (x["inv"] or x["app"] or x["ult"] or x["prec"]) and x["srv"])))


if __name__ == "__main__":
    main()
