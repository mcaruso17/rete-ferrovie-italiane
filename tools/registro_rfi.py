"""Registro ufficiale delle linee (CdP Servizi) e aggancio degli interventi.

Due registri descrivono la stessa rete, ciascuno con il suo mestiere, e qui
restano distinti:

- il registro RFI (Allegato 3 dei contratti Servizi) e' l'autorita' sull'identita'
  della linea: codice, denominazione, chilometri, treni al giorno, gruppo di
  traffico. Non ha geometria;
- OpenStreetMap (aggancio.py) e' l'autorita' sulla geometria: dove passano i
  binari. Non ha dati ufficiali.

Non si costruisce una tabella di corrispondenza fra i due. Provato: su 296 linee
RFI solo 29 hanno due capi in comune con una relazione OSM, perche' RFI spezza
la rete in tratte fini ("Casale Popolo - Casale Monferrato", 3,5 km) e OSM tiene
relazioni lunghe ("Ferrovia Monza-Molteno-Lecco" copre due linee RFI).
Presentare quelle 29 come una mappatura sarebbe peggio che non averla.

Si agganciano invece gli interventi a ciascun registro separatamente. Sul
registro RFI la prova e' solo il nome, ma e' un nome scritto dalla stessa fonte
della descrizione dell'intervento, e a parita' di metodo rende di piu' dei nomi
OSM (232 agganci contro 210, 65 in fascia alta contro 47).

Il livello "confermato" sta sopra "alta" e richiede tre cose insieme: aggancio
alto sul registro RFI, aggancio alto su una linea OSM, e le due linee che
condividono almeno un capo. L'ultima condizione e' quella che rende la conferma
una conferma: due agganci alti su linee che non hanno niente in comune sono due
indizi discordi, non uno confermato due volte.

Uso:
  python3 registro_rfi.py DIR_SERVIZI app-in.json app-out.json
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toponimi import norm, linea_av, cita_av, declassa  # noqa: E402

DIR, APP, OUT = sys.argv[1:4]

# L'ordine conta: per chilometri e treni vale il documento piu' recente in cui
# la linea compare, per la denominazione il primo che ce l'ha. Il contratto
# base perde il nome di 14 linee, che nell'atto 2023 ci sono tutti: prenderlo da
# li' non e' dedurre, e' leggere lo stesso registro in un'edizione piu' pulita.
ORDINE = ["cdps2022", "srv2023", "srv2024", "srv2025", "srv2026"]
TITOLI = {
    "cdps2022": "CdP 2022-2026 parte Servizi",
    "srv2023": "CdP Servizi, primo atto integrativo (agg. 2023)",
    "srv2024": "CdP Servizi, secondo atto integrativo (agg. 2024)",
    "srv2025": "CdP Servizi, terzo atto integrativo (agg. 2025)",
    "srv2026": "CdP Servizi, quarto atto integrativo (agg. 2026)",
}

VUOTE = {"linea", "ferrovia", "ferroviaria", "compresa", "comprese", "via", "e",
         "di", "del", "della", "dei", "delle", "centrale", "scalo",
         "smistamento", "nuova", "ex", "lmv", "avac", "av", "ac", "storica",
         "bassa", "alta", "porta", "nord", "sud", "est", "ovest", "c", "le"}
NODO_SE_OLTRE = 3


def capi(nome):
    """I capi di una linea dal suo nome.

    Le denominazioni RFI hanno due convenzioni che non stanno nei nomi OSM: il
    nodo di riferimento fra quadre ("[MILANO] PIOLTELLO L. - BRESCIA", dove
    Milano non e' un capo ma la citta' del nodo) e le varianti fra tonde
    ("compresa via Novi L."). Entrambe si tolgono prima di spezzare.
    """
    n = re.sub(r"\([^)]*\)", " ", nome or "")
    n = re.sub(r"\[[^\]]*\]", " ", n)
    out = []
    for p in re.split(r"\s*[-–/]\s*", n):
        w = [x for x in norm(p).split() if x and x not in VUOTE]
        if w:
            out.append(" ".join(w))
    return out


def registro():
    """Il registro unito sui codici, con la fonte di ogni valore."""
    reg = {}
    for doc in ORDINE:
        f = os.path.join(DIR, doc + ".json")
        if not os.path.exists(f):
            continue
        for l in json.load(open(f, encoding="utf-8")).get("linee", []):
            r = reg.setdefault(l["codice"], {"c": l["codice"], "n": "",
                                             "doc_n": None, "pag_n": None})
            if not r["n"] and l["linea"]:
                r["n"], r["doc_n"], r["pag_n"] = l["linea"], doc, l["pagina"]
            # i dati quantitativi si aggiornano: vale l'edizione piu' recente
            r.update({"g": l["gruppo"], "km": l["km"], "tr": l["treni_giorno"],
                      "doc": doc, "pag": l["pagina"]})
            # la serie per edizione: chilometri e treni cambiano da un orario
            # all'altro, e la vista Servizi della rete li mette in fila
            r.setdefault("st", {})[doc] = [l["km"], l["treni_giorno"]]
    return reg


def main():
    reg = registro()
    linee = [(c, capi(r["n"])) for c, r in reg.items() if r["n"]]
    linee = [(c, cs) for c, cs in linee if cs]
    freq = collections.Counter(x for _c, cs in linee for x in set(cs))

    app = json.load(open(APP, encoding="utf-8"))
    per_int = {}
    for pr in app["progetti"]:
        testo = norm(pr.get("n") or "")
        trovate = []
        for cod, cs in linee:
            hit = [x for x in cs if re.search(r"\b" + re.escape(x) + r"\b", testo)]
            if not hit:
                continue
            if len(set(hit)) >= 2:
                conf = "alta"
            elif any(freq[x] <= NODO_SE_OLTRE for x in hit):
                conf = "media"
            else:
                conf = "bassa"
            if linea_av(reg[cod]["n"], cod) and not cita_av(pr.get("n") or ""):
                conf = declassa(conf)
            trovate.append({"c": cod, "conf": conf, "capi": hit})
        if not trovate:
            continue
        rango = {"alta": 0, "media": 1, "bassa": 2}
        trovate.sort(key=lambda t: (rango[t["conf"]], -len(t["capi"]), t["c"]))
        per_int[pr["c"]] = trovate[:6]

    # ------------------------------------------------------ la conferma
    # stessa funzione per i due registri: confrontare capi estratti con regole
    # diverse farebbe sembrare diversi due nomi uguali
    osm_capi = {str(lid): set(capi(v["n"]))
                for lid, v in (app.get("linee") or {}).items()}
    # Un capo condiviso che e' un nodo non prova lo stesso corridoio. Alla prima
    # prova la regola accettava qualunque capo in comune, e "Raddoppio
    # Pescara-Bari" risultava confermato perche' RFI (Foggia-Bari) e OSM
    # (Napoli-Bari AV/AC) condividono Bari, che sta su mezza rete pugliese.
    # Stesso difetto con Taranto, Mortara, Palermo. La frequenza si conta sui
    # due registri insieme: un nome e' un nodo per la rete, non per una fonte.
    freq_tutti = collections.Counter(
        x for cs in [set(cs) for _c, cs in linee] + list(osm_capi.values())
        for x in cs)

    def stesso_corridoio(a, b):
        comuni = a & b
        return len(comuni) >= 2 or any(freq_tutti[x] <= NODO_SE_OLTRE
                                       for x in comuni)

    confermati = {}
    for cod, lista in per_int.items():
        rfi_alte = [t for t in lista if t["conf"] == "alta"]
        osm_alte = [t for t in (app.get("linee_intervento") or {}).get(cod, [])
                    if t["conf"] == "alta"]
        for r in rfi_alte:
            cr = set(capi(reg[r["c"]]["n"]))
            for o in osm_alte:
                if stesso_corridoio(cr, osm_capi.get(str(o["id"]), set())):
                    confermati[cod] = {"rfi": r["c"], "osm": str(o["id"])}
                    break
            if cod in confermati:
                break

    app["registro_rfi"] = {c: {k: r[k] for k in ("n", "g", "km", "tr", "doc",
                                                  "pag", "doc_n", "pag_n", "st")}
                           for c, r in reg.items()}
    app["registro_rfi_fonti"] = TITOLI
    app["linee_rfi_intervento"] = per_int
    app["confermati"] = confermati
    json.dump(app, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))

    tot = len(app["progetti"])
    liv = collections.Counter(v[0]["conf"] for v in per_int.values())
    senza = sum(1 for r in reg.values() if not r["n"])
    km = sum(r["km"] or 0 for r in reg.values())
    print("registro RFI: %d linee, %.1f km, %d senza denominazione in nessuna edizione"
          % (len(reg), km, senza))
    print("interventi agganciati al registro: %d su %d (%d%%)  alta %d, media %d, bassa %d"
          % (len(per_int), tot, round(100 * len(per_int) / tot),
             liv["alta"], liv["media"], liv["bassa"]))
    both = set(per_int) | set(app.get("linee_intervento") or {})
    print("con almeno un registro: %d su %d (%d%%)"
          % (len(both), tot, round(100 * len(both) / tot)))
    print("confermati da entrambi i registri sullo stesso corridoio: %d"
          % len(confermati))


if __name__ == "__main__":
    main()
