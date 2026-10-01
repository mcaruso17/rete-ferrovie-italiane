"""Confronto fra la lista di CUP ricevuta da RFI (CUP presenti in BDAP con lo
stato del CUP: documenti/rfi/lista-cup-bdap.csv) e quello che troviamo noi nei
documenti dei contratti.

Della lista si pubblicano solo CUP e stato: niente altro del file originale.

Per ogni CUP dell'unione delle due liste:
- dalla lista: lo stato in BDAP (attivo, chiuso);
- da noi: lo stato del registro dei CUP (in corso, concluso, non piu' nel
  contratto, servizi) con la fonte, oppure, se nessuna tabella estratta lo
  riporta, i documenti e le pagine in cui il CUP e' comunque scritto
  (cup_nel_testo.py);
- l'esito del confronto, una sola voce per CUP, nell'ordine in cui una
  verifica le guarderebbe.

Uso:
  python3 confronto_rfi.py app-in.json app-out.json lista.csv ../data/cup-nel-testo.json ../data
"""
import csv
import json
import os
import sys

# gli esiti, dal piu' urgente da chiarire al piu' tranquillo
ESITI = [
    ("chiuso-in-corso", "Chiuso in BDAP, in corso nel contratto",
     "Il contratto 2025 lo tiene fra gli interventi in corso, BDAP lo dà chiuso."),
    ("manca-nel-file", "In corso nel contratto, assente dalla lista",
     "Il contratto 2025 lo elenca fra gli interventi in corso (tabelle o Appendice 2), la lista non lo riporta."),
    ("non-nei-documenti", "Nella lista, non nei documenti",
     "Il CUP non è scritto in nessun PDF dei contratti e degli allegati pubblicati. Per lo più atteso per la "
     "parte Servizi, che scrive i CUP solo negli Allegati 4c e 12; per un intervento d'investimento va chiarito."),
    ("solo-testo", "Nei documenti, fuori dalle tabelle",
     "Nella lista e scritto nei PDF, ma non in una tabella che estraiamo (schede intervento, delibere)."),
    ("concluso-attivo", "Opera ultimata, CUP attivo in BDAP",
     "Il contratto lo dà fra le opere ultimate e in BDAP il CUP è ancora attivo."),
    ("concorda", "In entrambe", "Nella lista e nei documenti, senza contraddizioni di stato."),
    ("concluso-fuori", "Opera ultimata, assente dalla lista",
     "Fra le opere ultimate di qualche edizione, non nella lista: atteso se il CUP è chiuso o fuori dall'estrazione BDAP."),
    ("solo-nostro-altro", "Altro, solo nei documenti",
     "Nei documenti ma non nella lista: contratti precedenti o parte Servizi."),
]


def main():
    app_in, app_out, lista, testo, cartella = sys.argv[1:6]
    A = json.load(open(app_in, encoding="utf-8"))
    F = {}
    with open(lista, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["cup"].strip():
                F[r["cup"].strip().upper()] = r["stato_bdap"].strip()
    T = json.load(open(testo, encoding="utf-8")) if os.path.exists(testo) else {}
    REG = {x["cup"]: x for x in (A.get("cup_registro") or {}).get("righe") or []}

    out, conta = [], {}
    for cup in sorted(set(F) | set(REG)):
        f, x = F.get(cup), REG.get(cup)
        st = x["st"] if x else ""
        if f and x:
            if f.lower().startswith("chiuso") and st == "in corso":
                es = "chiuso-in-corso"
            elif st == "concluso" and f.lower().startswith("attivo"):
                es = "concluso-attivo"
            else:
                es = "concorda"
        elif f:
            es = "solo-testo" if cup in T else "non-nei-documenti"
        else:
            es = {"in corso": "manca-nel-file", "concluso": "concluso-fuori"}.get(st, "solo-nostro-altro")
        conta[es] = conta.get(es, 0) + 1
        # dove lo troviamo: prima la fonte del registro, poi il testo
        dove = []
        if x:
            if x["inv"]:
                dove.append(["Tabella A/B", x["inv"][0]["doc"], x["inv"][0]["p"]])
            if x.get("app"):
                dove.append(["Appendice 2", x["app"][0]["doc"], x["app"][0]["p"]])
            if x["ult"]:
                dove.append(["Opere ultimate", x["ult"]["doc"], x["ult"]["p"]])
            if x["srv"]:
                dove.append(["Servizi, Allegato " + x["srv"][0]["all"], x["srv"][0]["doc"], x["srv"][0]["p"]])
            if x["prec"] and not dove:
                y = x["prec"][-1]
                dove.append(["Tabella A/B precedente", y["doc"], y["p"]])
        ops = []
        if x:
            for k in ("inv", "app", "prec"):
                for y in x.get(k) or []:
                    if y["c"] not in ops:
                        ops.append(y["c"])
        descr = ""
        if x:
            descr = ((x["inv"] or x.get("app") or [{}])[0].get("n") or (x["ult"] or {}).get("n")
                     or ((x["srv"] or [{}])[0].get("n")) or ((x["prec"] or [{}])[0].get("n")) or "")
        out.append({"cup": cup, "es": es, "f": f, "st": st, "dove": dove, "ops": ops, "n": descr,
                    "testo": (T.get(cup) or [])[:6]})

    with open(os.path.join(cartella, "confronto-rfi.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cup", "esito", "nella_lista", "stato_bdap", "stato_nei_documenti", "dove_nei_documenti",
                    "interventi", "descrizione", "pagine_nel_testo_dei_pdf"])
        nomi = {k: t for k, t, _d in ESITI}
        for r in out:
            w.writerow([r["cup"], nomi[r["es"]], bool(r["f"]), r["f"] or "", r["st"],
                        " | ".join("%s, %s p. %s" % tuple(d) for d in r["dove"]), "|".join(r["ops"]), r["n"],
                        " | ".join("%s p. %s" % (os.path.basename(d), p) for d, p in r["testo"])])

    A["confronto_rfi"] = {
        "n_file": len(F), "n_registro": len(REG), "comuni": len(set(F) & set(REG)),
        "stati_bdap": {k: sum(1 for v in F.values() if v == k) for k in sorted(set(F.values()))},
        "n_testo": len(T), "esiti": [[k, t, d] for k, t, d in ESITI], "conta": conta, "righe": out,
    }
    json.dump(A, open(app_out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("confronto con la lista RFI: %d CUP nella lista, %d nel registro, %d in comune; %s"
          % (len(F), len(REG), len(set(F) & set(REG)),
             ", ".join("%s %d" % (k, conta.get(k, 0)) for k, _t, _d in ESITI)))


if __name__ == "__main__":
    main()
