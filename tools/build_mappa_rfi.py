"""La mappa dei progetti RFI: piattaforma/mappa-rfi.html, pubblicata come
mappa-rfi.html. Una pagina a parte, chiesta dal dirigente, che mostra solo i
legami di cui siamo sicuri: le geometrie del Piano Commerciale 2026
(servizio ArcGIS "Scenari infrastrutturali" di RFI) in cui RFI scrive il
codice dell'intervento nel campo "Riferimento CdP-I". Nessun aggancio dedotto
per nome o per vicinanza, che stanno nella piattaforma principale.

Strati, tutti sulla proiezione di mappa-regioni.json:
- regioni ISTAT (sfondo);
- la rete RFI di oggi (SHAPE_TRATTE), solo come riferimento visivo;
- tratte e localita' di progetto con almeno un codice del portafoglio 2025.
Un elemento puo' riportare piu' codici (lo stesso tracciato serve due
interventi): resta uno, con tutti i suoi codici.

Al clic la scheda dell'intervento: importi dal file base-interventi, CUP da
base-cup (con la fonte di ogni importo), il progetto come lo descrive RFI.
La geometria sta solo dentro la pagina: la scheda del servizio non indica una
licenza, quindi non se ne fa un file scaricabile a parte.

Uso:
  python3 build_mappa_rfi.py ../data ../piattaforma/mappa-rfi.html
"""
import csv
import json
import os
import re
import sys

from geometria import path, proiettore, semplifica

# opere di linea del Piano Commerciale: i campi a 0/1 dicono il tipo di intervento
TIPI_TRATTA = [("NUOVA_LINEA", "nuova linea"), ("RADDOPPIO_QUADRUPLICAMENTO", "raddoppio o quadruplicamento"),
               ("RIAPERTURA_LINEA", "riapertura"), ("ELETTRIFICAZIONE", "elettrificazione"),
               ("UPGRADE_TECNOLOGICO", "upgrade tecnologico"), ("UPGRADE_PRESTAZIONALE", "upgrade prestazionale"),
               ("VELOCIZZAZIONE", "velocizzazione")]
TIPI_LOC = [("PRG", "piano regolatore generale"), ("NUOVO_IMPIANTO", "nuovo impianto"),
            ("NUOVO_TERMINAL", "nuovo terminal"), ("POTENZIAMENTO_TERMINAL", "potenziamento terminal"),
            ("VELOCIZZAZIONE", "velocizzazione"), ("UPGRADE_TECNOLOGICO", "upgrade tecnologico"),
            ("UPGRADE_PRESTAZIONALE", "upgrade prestazionale")]


def leggi(d, f):
    return list(csv.DictReader(open(os.path.join(d, f), encoding="utf-8")))


def num(x):
    return round(float(x), 2) if x not in ("", None) else None


def linee(g):
    if g["type"] == "LineString":
        return [g["coordinates"]]
    if g["type"] == "MultiLineString":
        return g["coordinates"]
    return []


def main():
    d, out = sys.argv[1], sys.argv[2]
    pr = proiettore(os.path.join(d, "mappa-regioni.json"))
    mappa = json.load(open(os.path.join(d, "mappa-regioni.json"), encoding="utf-8"))
    interv = {r["codice_intervento"]: r for r in leggi(d, "base-interventi-agg2025.csv")}
    cups = leggi(d, "base-cup-agg2025.csv")
    pc = json.load(open(os.path.join(d, "piano-commerciale-2026.json"), encoding="utf-8"))

    # rete di oggi: un path per l'alta velocita' e uno per il resto, solo sfondo
    rete = {"av": [], "conv": []}
    for f in json.load(open(os.path.join(d, "tratte-rfi.geojson"), encoding="utf-8"))["features"]:
        p = f["properties"]
        for ln in linee(f["geometry"]):
            s = path(semplifica([pr(x, y) for x, y in ln], 0.35))
            if s:
                rete["av" if p.get("LINEA_AV") == "AV" else "conv"].append(s)

    progetti, codici_mappa, fuori = [], set(), set()
    for strato, fs in pc["layer"].items():
        for f in fs:
            p = f["p"]
            cod = [c for c in (p.get("CDP") or []) if c in interv]
            fuori |= {c for c in (p.get("CDP") or []) if c not in interv}
            if not cod:
                continue
            codici_mappa |= set(cod)
            el = {"k": strato, "c": cod, "n": p.get("PROGETTO") or "", "a": p.get("ANNO_ATT_PC") or "",
                  "lp": p.get("CODICE_PROG_LIN") or ""}
            if strato == "tratte":
                el["d"] = "".join(s for s in (path(semplifica([pr(x, y) for x, y in ln], 0.15))
                                             for ln in linee(f["g"])) if s)
                el["t"] = p.get("DESCRIZIONE_TRATTE") or ""
                el["y"] = [n for k, n in TIPI_TRATTA if p.get(k) == 1]
            else:
                x, y = pr(*f["g"]["coordinates"][:2])
                el["xy"] = [round(x, 1), round(y, 1)]
                el["t"] = p.get("DENOMINAZIONE") or ""
                el["y"] = ([n for k, n in TIPI_LOC if p.get(k) == 1] if strato == "localita_potenziate"
                           else [x for x in (p.get("STAZIONE_FERMATA"), p.get("STATO")) if x])
            progetti.append(el)

    imp = ["costo_vita_intera_mln", "risorse_assegnate_mln", "mef_mln", "fsc_pac_mln", "mit_mln", "pnrr_mln",
           "altro_mln", "fabbisogno_mln", "speso_mln", "incrementi_2025_mln", "riduzioni_2025_mln",
           "rimodulazioni_2025_mln", "assegnate_aggiornamento_precedente_mln"]
    schede = {}
    for c in sorted(codici_mappa):
        it = interv[c]
        schede[c] = {"de": it["descrizione_intervento"], "ta": it["tabella"], "ti": it["tipologia_programma"],
                     "pr": it["programma"], "cl": it["classe_tipologica"], "pg": it["pagina_pdf"],
                     "nc": int(it["n_cup"] or 0), **{k[:-4]: num(it[k]) for k in imp}, "cup": []}
    for r in cups:
        for c in r["codice_intervento"].split("|"):
            if c in schede:
                schede[c]["cup"].append({"cup": r["cup"], "og": r["oggetto_cup"], "pe": r["perimetro"],
                                         "fi": r["fonte_importi"], "st": r["stato_attuativo"],
                                         "co": num(r["costo_mln"]), "ri": num(r["risorse_assegnate_mln"]),
                                         "sp": num(r["speso_mln"]), "pa": r["pagina"],
                                         "uno": r["fonte_importi"].startswith("Intervento con un solo CUP"),
                                         "piu": r["n_interventi"] != "1"})
    tot = {k: round(sum(num(interv[c][k]) or 0 for c in codici_mappa), 2)
           for k in ("costo_vita_intera_mln", "risorse_assegnate_mln")}
    tot_all = {k: round(sum(num(r[k]) or 0 for r in interv.values()), 2)
               for k in ("costo_vita_intera_mln", "risorse_assegnate_mln")}
    dati = {"vb": mappa["viewBox"], "reg": [r["d"] for r in mappa["regioni"]], "rete": rete,
            "prog": progetti, "int": schede,
            "meta": {"n_int": len(codici_mappa), "n_int_tot": len(interv), "tot": tot, "tot_all": tot_all,
                     "n_cup": len({x["cup"] for s in schede.values() for x in s["cup"]}), "fonte": pc["servizio"],
                     "scaricato": pc.get("scaricato", ""), "fuori": len(fuori)}}

    html = open(out, encoding="utf-8").read()
    js = json.dumps(dati, ensure_ascii=False, separators=(",", ":"))
    nuovo, n = re.subn(r"/\*DATI\*/.*?/\*FINE\*/", lambda m: "/*DATI*/" + js + "/*FINE*/", html, flags=re.S)
    if n != 1:
        sys.exit("marcatori /*DATI*/ /*FINE*/ non trovati in " + out)
    open(out, "w", encoding="utf-8").write(nuovo)
    print("mappa-rfi.html: %d elementi di progetto (%s), %d interventi del 2025 su %d, %d CUP; codici RFI fuori "
          "dal portafoglio 2025: %d; dati %d KB" % (
              len(progetti), ", ".join("%s %d" % (k, sum(1 for p in progetti if p["k"] == k)) for k in pc["layer"]),
              len(codici_mappa), len(interv), dati["meta"]["n_cup"], len(fuori), len(js) // 1024))


if __name__ == "__main__":
    main()
