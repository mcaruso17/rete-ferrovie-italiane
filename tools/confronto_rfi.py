"""Confronto fra la lista di CUP ricevuta (file Excel "ANALISI MEF LISTA
CUP-CDP": CUP in BDAP, stato del CUP, parte del contratto in cui RFI lo
colloca nell'aggiornamento 2025 e nel 2026 in lavorazione) e quello che
troviamo noi nei documenti dei contratti.

Per ogni CUP dell'unione delle due liste:
- dal file: parte 2025 (CDP-I, CDP-S), parte 2026 (WIP), stato in BDAP;
- da noi: lo stato del registro dei CUP (in corso, concluso, non piu' nel
  contratto, servizi) con la fonte, oppure, se nessuna tabella estratta lo
  riporta, i documenti e le pagine in cui il CUP e' comunque scritto
  (cup_nel_testo.py);
- l'esito del confronto, una sola voce per CUP, nell'ordine di gravita' in
  cui una verifica le guarderebbe.

L'Excel si legge col modulo zipfile (un foglio, valori semplici): niente
dipendenze in piu' per la build.

Uso:
  python3 confronto_rfi.py app-in.json app-out.json file.xlsx ../data/cup-nel-testo.json ../data
"""
import csv
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# gli esiti, dal piu' urgente da chiarire al piu' tranquillo
ESITI = [
    ("chiuso-in-corso", "Chiuso in BDAP, in corso nel contratto",
     "Il contratto 2025 lo tiene fra gli interventi in corso, BDAP lo dà chiuso."),
    ("parte-diversa", "Parte del contratto diversa",
     "Il file lo colloca in una parte (Investimenti o Servizi), i documenti nell'altra."),
    ("non-nei-documenti", "Investimenti, non nei documenti",
     "Il file lo colloca negli Investimenti, ma il CUP non è scritto in nessun PDF dei contratti e degli allegati pubblicati."),
    ("manca-nel-file", "In corso nel contratto, assente dal file",
     "Il contratto 2025 lo elenca fra gli interventi in corso (tabelle o Appendice 2), il file non lo riporta."),
    ("solo-testo", "Nei documenti, fuori dalle tabelle",
     "Nel file e scritto nei PDF, ma non in una tabella che estraiamo (schede, note, contratti precedenti)."),
    ("servizi-non-verificabile", "Servizi, non verificabile",
     "Il file lo colloca nei Servizi; il contratto Servizi scrive i CUP solo negli Allegati 4c e 12, e qui non c'è."),
    ("concluso-attivo", "Opera ultimata, CUP attivo in BDAP",
     "Concorda la parte, ma il contratto lo dà fra le opere ultimate e in BDAP il CUP è ancora attivo."),
    ("concorda", "Concorda", "Stessa parte del contratto nel file e nei documenti."),
    ("concluso-fuori", "Opera ultimata, assente dal file",
     "Fra le opere ultimate di qualche edizione, non nel file: atteso se il CUP è chiuso o fuori dall'estrazione BDAP."),
    ("solo-nostro-altro", "Altro, solo nei documenti",
     "Nei documenti ma non nel file, in contratti precedenti o nella parte Servizi."),
]


def leggi_xlsx(path):
    z = zipfile.ZipFile(path)
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            sst.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    foglio = wb.find("m:sheets/m:sheet", NS).get("name")
    sh = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    righe = []
    for row in sh.findall("m:sheetData/m:row", NS):
        r = {}
        for c in row.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            v = c.find("m:v", NS)
            if v is None:
                t = c.find("m:is/m:t", NS)
                val = t.text if t is not None else None
            elif c.get("t") == "s":
                val = sst[int(v.text)]
            else:
                val = v.text
            r[col] = val.strip() if isinstance(val, str) else val
        righe.append(r)
    return foglio, righe


def main():
    app_in, app_out, xlsx, testo, cartella = sys.argv[1:6]
    A = json.load(open(app_in, encoding="utf-8"))
    foglio, righe = leggi_xlsx(xlsx)
    intest = [righe[0].get(k) for k in "ABCD"]
    F = {}
    for r in righe[1:]:
        cup = (r.get("A") or "").strip().upper()
        if cup:
            F[cup] = {"stato": r.get("B") or "", "p25": r.get("C") or "", "p26": r.get("D") or ""}
    T = json.load(open(testo, encoding="utf-8")) if os.path.exists(testo) else {}
    REG = {x["cup"]: x for x in (A.get("cup_registro") or {}).get("righe") or []}

    def parte_nostra(x):
        inv = bool(x["inv"] or x.get("app") or x["ult"] or x["prec"])
        return ("I" if inv else "") + ("S" if x["srv"] else "")

    out, conta = [], {}
    for cup in sorted(set(F) | set(REG)):
        f, x = F.get(cup), REG.get(cup)
        st = x["st"] if x else ""
        if f:
            pf = (f["p25"] or f["p26"]).replace("CDP-", "")
        if f and x:
            pn = parte_nostra(x)
            if f["stato"].lower().startswith("chiuso") and st == "in corso":
                es = "chiuso-in-corso"
            elif pf not in pn:
                es = "parte-diversa"
            elif st == "concluso" and f["stato"].lower().startswith("attivo"):
                es = "concluso-attivo"
            else:
                es = "concorda"
        elif f:
            es = "solo-testo" if cup in T else "servizi-non-verificabile" if pf == "S" else "non-nei-documenti"
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
        out.append({"cup": cup, "es": es,
                    "f": [f["p25"], f["p26"], f["stato"]] if f else None,
                    "st": st, "dove": dove, "ops": ops, "n": descr,
                    "testo": (T.get(cup) or [])[:6]})

    with open(os.path.join(cartella, "confronto-rfi.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cup", "esito", "file_parte_agg2025", "file_parte_agg2026_wip", "file_stato_bdap",
                    "stato_nei_documenti", "dove_nei_documenti", "interventi", "descrizione", "pagine_nel_testo_dei_pdf"])
        nomi = {k: t for k, t, _d in ESITI}
        for r in out:
            w.writerow([r["cup"], nomi[r["es"]], *(r["f"] or ["", "", ""]), r["st"],
                        " | ".join("%s, %s p. %s" % tuple(d) for d in r["dove"]), "|".join(r["ops"]), r["n"],
                        " | ".join("%s p. %s" % (os.path.basename(d), p) for d, p in r["testo"])])

    nf = len(F)
    A["confronto_rfi"] = {
        "file": os.path.basename(xlsx), "foglio": foglio, "colonne": intest,
        "n_file": nf, "n_registro": len(REG), "comuni": len(set(F) & set(REG)),
        "parti_file": {k: sum(1 for v in F.values() if (v["p25"] or "") == k) for k in ("CDP-I", "CDP-S")},
        "solo_2026": {k: sum(1 for v in F.values() if not v["p25"] and v["p26"] == k) for k in ("CDP-I", "CDP-S")},
        "stati_bdap": {k: sum(1 for v in F.values() if v["stato"] == k) for k in sorted({v["stato"] for v in F.values()})},
        "n_testo": len(T),
        "esiti": [[k, t, d] for k, t, d in ESITI], "conta": conta, "righe": out,
    }
    json.dump(A, open(app_out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("confronto con il file RFI: %d CUP nel file, %d nel registro, %d in comune; %s"
          % (nf, len(REG), len(set(F) & set(REG)),
             ", ".join("%s %d" % (k, conta.get(k, 0)) for k, _t, _d in ESITI)))


if __name__ == "__main__":
    main()
