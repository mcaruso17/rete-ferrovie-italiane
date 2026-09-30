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
import sys

ORDINE = {}


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

    def voce(cup):
        return R.setdefault(cup, {"cup": cup, "inv": [], "app": [], "ult": None, "prec": [], "srv": []})

    for p in D["progetti"]:
        for s in p["storico"]:
            for cup in s.get("cups") or []:
                x = {"c": p["codice"], "n": p["descrizione"], "cl": p.get("classe"),
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
            v["ult"] = {"doc": u["doc"], "p": u["page"], "npp": u.get("npp"), "voce": u.get("riga"),
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
            if not any(y["c"] == r["codice"] and y["n"] == r["descr"] for y in v["app"]):
                v["app"].append({"c": r["codice"], "n": r["descr"], "tab": r["tab"], "doc": did, "p": r["p"]})
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
            doc, pag])
        app.append({"cup": cup, "st": stato, "inv": v["inv"], "app": v["app"], "ult": v["ult"],
                    "prec": v["prec"], "srv": v["srv"]})

    with open(dest_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cup", "stato", "parte", "fonte_principale", "descrizione",
                    "interventi_ultimo_contratto", "programmi_appendice_2", "oggetto_appendice_2",
                    "interventi_contratti_precedenti",
                    "opere_ultimate_edizione", "data_messa_in_esercizio", "opere_ultimate_voce",
                    "opere_ultimate_npp", "servizi_allegati", "servizi_importo_mln",
                    "documento", "pagina"])
        w.writerows(righe)
    A["cup_registro"] = {"ultimo": ultimo, "righe": app, "documenti": extra}
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
