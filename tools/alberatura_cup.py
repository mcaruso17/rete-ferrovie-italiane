"""L'alberatura del portafoglio dell'ultimo aggiornamento, fino al CUP:
data/alberatura-cup-agg2025.csv, chiesto dal dirigente.

Livelli, una riga per sub-intervento:
1. tabella e denominazione del portafoglio (A in corso e programmatici, B per
   lotti costruttivi, C opere ultimate);
2. tipologia di programma (le classi a..e; per la Tabella C la voce);
3. programma (non scritto nell'articolato: emerge dalle tabelle, A01..A09
   nelle Appendici 4 e 5);
4. classe tipologica di destinazione (01..09);
5. macro-intervento: il codice senza la lettera finale, come l'ufficio legge
   il portafoglio (A1004 per A1004A, A1004B...; 0049 per 0049A e 0049B;
   P055 per P055_A). Il documento non gli da' un nome: macro_intervento_nome
   e' quello dell'intervento, o i nomi dei suoi interventi separati da " | ";
5.1 intervento: la riga del CdP con il suo codice;
5.2 sub-intervento: le righe senza codice sotto l'intervento.
   - progetti (Tabelle A e B): le opere, i lotti e le fasi stampati sotto
     l'intervento (stati-opere-agg2025.csv); se la tabella non ne stampa,
     quelle della scheda dell'Appendice 3;
   - programmi (classe a): i sottoprogetti dell'avanzamento programma
     (Appendice 3) e gli oggetti dell'Appendice 2, uno per CUP;
   - Tabella C: le opere ultimate della voce.
6. CUP: quello del sub-intervento quando un documento lo dice (Appendice 3
   per le opere, Appendice 2 e 3 per i sottoprogetti, Tabella C); per
   un'opera senza CUP nella scheda, il CUP dell'intervento se e' uno solo.
   I CUP dell'intervento che nessun documento attribuisce a un sub-intervento
   stanno su una riga con il sub-intervento vuoto: cosi' ogni CUP c'e'.

Controllo: i CUP in corso dell'alberatura sono gli stessi del file delle
assegnazioni (990), e ogni intervento delle Tabelle A e B c'e' almeno una
volta (223).

Uso:
  python3 alberatura_cup.py ../data
"""
import csv
import json
import os
import re
import sys

from assegnazioni_cup import norm
from schema import ALB_TABELLE, ALB_VOCI_C


def leggi(d, f):
    return list(csv.DictReader(open(os.path.join(d, f), encoding="utf-8")))


def macro(codice):
    # A1004A -> A1004, P055_A -> P055, 1604A -> 1604; NA026 resta NA026
    return re.sub(r"(_[A-Z]|(?<=\d)[A-Z])$", "", codice)


def nome_macro(interventi):
    # il documento non da' un nome al macro-intervento: con piu' interventi si
    # elencano i loro nomi. La parte comune dei nomi sembrava un nome ma non lo
    # e' ("Accesso al Brennero lotto" per 0292A, B e C)
    return " | ".join(dict.fromkeys(i["descrizione_intervento"] for i in interventi))


COLONNE = ["tabella", "denominazione_portafoglio", "tipologia_programma", "programma_codice", "programma",
           "classe_tipologica", "macro_intervento", "macro_intervento_nome", "n_interventi_nel_macro",
           "intervento", "intervento_descrizione", "sub_intervento", "cup", "fonte_sub_intervento",
           "fonte_cup", "stato_attuativo", "fase_finanziata", "costo_sub_intervento_mln", "pagina"]


def main():
    d = sys.argv[1]
    interv = leggi(d, "assegnazioni-interventi-agg2025.csv")
    opere = leggi(d, "stati-opere-agg2025.csv")
    a3 = json.load(open(os.path.join(d, "appendice3-agg2025.json")))["schede"]
    a2 = json.load(open(os.path.join(d, "appendice-cup-agg2025.json")))["righe"]
    a4 = {r["c"]: r["prog"] for r in json.load(open(os.path.join(d, "appendice4-agg2025.json")))["righe"]}
    ultimate = [r for r in leggi(d, "opere-ultimate.csv") if r["documento"] == "agg2025"]

    per_macro = {}
    for it in interv:
        per_macro.setdefault(macro(it["codice_intervento"]), []).append(it)
    op_per = {}
    for o in opere:
        op_per.setdefault(o["codice_intervento"], []).append(o)
    a2_per = {}
    for r in a2:
        a2_per.setdefault(r["codice"], []).append(r)

    righe = []
    for it in interv:
        cod = it["codice_intervento"]
        t = it["tabella"][:1]
        m = macro(cod)
        base = {"tabella": t, "denominazione_portafoglio": ALB_TABELLE.get(t, ""),
                "tipologia_programma": it["tipologia_programma"], "programma_codice": a4.get(cod, ""),
                "programma": it["programma"], "classe_tipologica": it["classe_tipologica"],
                "macro_intervento": m, "n_interventi_nel_macro": len(per_macro[m]),
                "macro_intervento_nome": nome_macro(per_macro[m]),
                "intervento": cod, "intervento_descrizione": it["descrizione_intervento"]}
        cups = [c for c in it["cup"].split("|") if c]
        usati = set()
        sub = []
        if it["tipologia_programma"].startswith("a"):
            # programma: sottoprogetti dell'avanzamento (Appendice 3), poi gli
            # oggetti dell'Appendice 2 il cui CUP la scheda non elenca
            for x in a3.get(cod, {}).get("avanzamento", []):
                if not x["subtotale"]:
                    sub.append({"sub_intervento": x["nome"], "cup": x["cup"], "fonte_sub_intervento": "Appendice 3",
                                "fonte_cup": "Appendice 3" if x["cup"] else "", "stato_attuativo": x["stato"],
                                "costo_sub_intervento_mln": x["costo"], "pagina": "App. 3 p. %d" % x["pagina"]})
            visti = {s["cup"] for s in sub}
            for x in a2_per.get(cod, []):
                if x["cup"] not in visti:
                    visti.add(x["cup"])
                    sub.append({"sub_intervento": x.get("descr", ""), "cup": x["cup"], "fonte_sub_intervento": "Appendice 2",
                                "fonte_cup": "Appendice 2", "pagina": "App. 2 p. %s" % x.get("p", "")})
        else:
            ops = op_per.get(cod, [])
            for o in ops:
                c = o["cup_opera_appendice3"]
                fc = "Appendice 3" if c else ""
                if not c and len(cups) == 1:
                    c, fc = cups[0], "unico CUP dell'intervento"
                sub.append({"sub_intervento": o["descrizione_opera"], "cup": c,
                            "fonte_sub_intervento": "Tabella " + t, "fonte_cup": fc,
                            "stato_attuativo": o["stato_attuativo"], "fase_finanziata": o["fase_finanziata"],
                            "costo_sub_intervento_mln": o["costo_totale_opera_mln"], "pagina": "p. %s" % o["pagina_pdf"]})
            if not ops:
                # la tabella non stampa opere (0119, 0263): quelle della scheda
                for x in a3.get(cod, {}).get("opere", []):
                    c = x["cup"] or (cups[0] if len(cups) == 1 else "")
                    sub.append({"sub_intervento": x["opera"], "cup": c, "fonte_sub_intervento": "Appendice 3",
                                "fonte_cup": "Appendice 3" if x["cup"] else ("unico CUP dell'intervento" if c else ""),
                                "stato_attuativo": x["stato"], "pagina": "App. 3 p. %d" % x["pagina"]})
        # un CUP della scheda che non e' fra quelli dell'intervento nelle tabelle
        # (J57D25000060001 in A2009...) resta, ma la fonte lo dice
        for s in sub:
            if s["cup"] and s["cup"] not in cups:
                s["fonte_cup"] += " (CUP non nelle Tabelle A e B ne' nell'Appendice 2)"
            usati.add(s["cup"])
        resto = [c for c in cups if c not in usati]
        for c in resto:
            sub.append({"sub_intervento": "", "cup": c, "fonte_sub_intervento": "",
                        "fonte_cup": "CUP dell'intervento, sub-intervento non indicato"})
        if not sub:
            sub.append({"sub_intervento": "", "cup": "", "fonte_sub_intervento": "",
                        "fonte_cup": "nessun CUP nei documenti"})
        for s in sub:
            righe.append({**base, **s})

    # Tabella C: voce, opera ultimata (NPP come codice), CUP
    voce_reg = {g["cup"]: g["opere_ultimate_voce"] for g in leggi(d, "cup-registro.csv")}
    for r in ultimate:
        # le righe della rete AV/AC a p. 143 non ripetono la voce A5000_0: la
        # da' il registro dei CUP, o la descrizione per I019, che non ha CUP
        v = r["riga"] or voce_reg.get(r["cup"], "") or \
            ("A5000_0" if "AV/AC Torino-Milano-Napoli" in r["descrizione"] else "")
        righe.append({"tabella": "C", "denominazione_portafoglio": ALB_TABELLE.get("C", ""),
                      "tipologia_programma": "%s - %s" % (v, ALB_VOCI_C.get(v, "")) if ALB_VOCI_C.get(v) else v,
                      "macro_intervento": v, "intervento": r["npp"], "sub_intervento": r["descrizione"],
                      "cup": r["cup"], "fonte_sub_intervento": "Tabella C", "fonte_cup": "Tabella C" if r["cup"] else "",
                      "stato_attuativo": "ultimato il " + r["data_messa_in_esercizio"] if r["data_messa_in_esercizio"] else "ultimato",
                      "costo_sub_intervento_mln": r["costo_mln"], "pagina": "p. %s" % r["pagina"]})

    # controlli
    in_corso = {r["cup"] for r in righe if r["tabella"] in "AB" and r["cup"]}
    attesi = {c for it in interv for c in it["cup"].split("|") if c}
    extra = sorted(in_corso - attesi)
    if attesi - in_corso:
        sys.exit("CUP delle assegnazioni assenti dall'alberatura: %s" % sorted(attesi - in_corso)[:10])
    if {r["intervento"] for r in righe if r["tabella"] in "AB"} != {it["codice_intervento"] for it in interv}:
        sys.exit("interventi mancanti nell'alberatura")
    with open(os.path.join(d, "alberatura-cup-agg2025.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNE, extrasaction="ignore")
        w.writeheader()
        w.writerows(righe)
    ab = [r for r in righe if r["tabella"] in "AB"]
    print("alberatura-cup-agg2025.csv: %d righe (Tabelle A e B %d, Tabella C %d); %d macro-interventi, %d interventi; "
          "CUP in corso %d (+%d solo nelle schede: %s); righe A/B con CUP del sub-intervento %d, CUP dell'intervento "
          "non attribuito %d, senza CUP %d" % (
              len(righe), len(ab), len(righe) - len(ab), len({r["macro_intervento"] for r in ab}),
              len({r["intervento"] for r in ab}), len(attesi), len(extra), ", ".join(extra),
              sum(1 for r in ab if r["cup"] and r["sub_intervento"]),
              sum(1 for r in ab if r["fonte_cup"].startswith("CUP dell'intervento")),
              sum(1 for r in ab if not r["cup"])))


if __name__ == "__main__":
    main()
