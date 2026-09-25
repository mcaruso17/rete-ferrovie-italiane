"""La rete RFI sulla mappa, agganciata al registro ufficiale delle linee.

Fino a qui il sito aveva due registri che non si parlavano: l'Allegato 3 dei
contratti Servizi (identita' ufficiale delle linee, senza geometria) e
OpenStreetMap (geometria, senza identita' ufficiale). La rete che RFI pubblica
con il Piano Commerciale ha entrambe le cose: ogni tratta porta il codice di
linea commerciale, che e' il codice dell'Allegato 3 con la lettera cambiata.

    Allegato 3   C001  F011  N001  A001
    rete RFI     K001  J011  R001  A001

La corrispondenza non e' documentata: e' stata trovata confrontando i due
elenchi, e si accetta una linea solo se anche il nome torna (almeno un capo in
comune). Numeri uguali con lettere diverse non bastano: C011 e F011 esistono
entrambi.

Che cosa si scrive nell'app:
- rete_rfi.linee: per ogni linea dell'Allegato 3, i tracciati RFI e gli
  attributi della rete (rete TEN-T, massa assiale), piu' la data di apertura
  presa da OSM quando una linea OSM con data ricopre quasi tutto il tracciato;
- rete_rfi.altre: le tratte in esercizio senza codice di linea (bivi,
  raccordi), che si disegnano ma non si cliccano;
- rete_rfi.tocca: per ogni comune, le linee RFI che lo attraversano. Serve a
  registro_rfi.py per la seconda prova degli agganci, la stessa che
  aggancio.py fa sulle linee OSM.

Le tratte di progetto (codice PRJ, senza edizione del PIR) non sono rete in
esercizio: stanno gia' nello strato dei progetti del Piano Commerciale.

Uso:
  python3 rete_rfi.py rete-rfi.geojson mappa-regioni.json DIR_SERVIZI \
          app-in.json app-out.json
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometria import (proiettore, semplifica, path, punti_da_path,  # noqa: E402
                       anelli_da_path, dentro, IndiceSegmenti)
from toponimi import norm  # noqa: E402
from registro_rfi import registro  # noqa: E402
TOLL = 0.12
LETTERA = {"K": "C", "J": "F", "R": "N", "A": "A"}
VICINO = 3.0            # come in aggancio.py: circa 3 km dal centroide
COPRE = 0.8             # quota del tracciato RFI coperta da una linea OSM


VUOTE = {"nodo", "linea", "compresa", "via", "centrale", "bivio", "diramazione",
         "avac", "lmv", "direttissima", "della", "delle", "dei"}


def parole(nome):
    """Le parole significative di un nome di linea.

    Si confrontano parole e non capi: RFI scrive "Nodo di Torino" dove
    l'Allegato 3 scrive "Torino", e "SETTEBAGNI" dove l'altro ha "SETTE
    BAGNI". Con i capi interi nessun nodo tornava. Il codice deve comunque
    coincidere, quindi una parola in comune basta a escludere il caso di due
    linee diverse con lo stesso numero.
    """
    return {w for w in norm(nome or "").replace("-", " ").split()
            if len(w) > 2 and w not in VUOTE}


def prevalente(pesi):
    return max(pesi.items(), key=lambda kv: kv[1])[0] if pesi else None


def main():
    RETE, MAPPA, DIR, APP, OUT = sys.argv[1:6]
    pr = proiettore(MAPPA)
    gj = json.load(open(RETE, encoding="utf-8"))
    app = json.load(open(APP, encoding="utf-8"))
    reg = registro(DIR)

    linee, altre, scartate, rifiuti = {}, [], 0, collections.Counter()
    for f in gj["features"]:
        p, g = f["properties"], f.get("geometry")
        if not g:
            continue
        if (p.get("CODTRATTA_BDL") or "").startswith("PRJ") or not p.get("EDIZIONE_PIR"):
            scartate += 1
            continue
        tratti = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        ds = []
        for t in tratti:
            d = path(semplifica([pr(lon, lat) for lon, lat in t], TOLL))
            if d:
                ds.append(d)
        if not ds:
            continue
        cc = p.get("CODLINEA_COMM") or ""
        cod = (LETTERA.get(cc[:1], "") + cc[1:]) if cc else ""
        ok = cod in reg and (not reg[cod]["n"] or parole(reg[cod]["n"]) & parole(p.get("LINEA_COMM")))
        if cc and not ok:
            rifiuti[cc] += 1
        if not ok:
            altre.extend(ds)
            continue
        L = linee.setdefault(cod, {"d": [], "rfi": cc, "n_rfi": p.get("LINEA_COMM") or "",
                                   "_ten": collections.Counter(), "_peso": collections.Counter(),
                                   "_km": 0.0, "av": False})
        L["d"].extend(ds)
        lung = float(p.get("LENGTH_PIR") or 0) or 1.0
        L["_ten"][p.get("TIPO_RETE_TEN_T") or "fuori TEN-T"] += lung
        L["_peso"][p.get("PESO_ASSIALE") or ""] += lung
        L["av"] = L["av"] or p.get("LINEA_AV") == "SI"

    # --------------------------------- la data di apertura, presa da OSM
    # Il registro RFI non dice da quando una linea e' in esercizio; OSM a volte
    # si'. La si prende solo se la linea OSM ricopre quasi tutto il tracciato
    # RFI: una data di una linea che ne condivide mezzo tratto sarebbe falsa.
    geo = app.get("linee_geo") or {}
    ix = IndiceSegmenti()
    for oid, v in geo.items():
        if v.get("dal"):
            for d in v["d"]:
                ix.aggiungi(punti_da_path(d), oid)
    for cod, L in linee.items():
        pts = [q for d in L["d"] for q in punti_da_path(d)]
        cnt = collections.Counter()
        for q in pts:
            for oid in ix.vicine(q, 1.5):
                cnt[oid] += 1
        if cnt:
            oid, n = cnt.most_common(1)[0]
            if n / len(pts) >= COPRE:
                L["dal"], L["dal_osm"] = geo[oid]["dal"], oid

    # ------------------------------------- quali linee attraversano un comune
    ixl = IndiceSegmenti(cella=4.0)
    for cod, L in linee.items():
        for d in L["d"]:
            ixl.aggiungi(punti_da_path(d), cod)
    tocca = {}
    for istat, voce in (app.get("mappa_comuni") or {}).items():
        anelli = anelli_da_path(voce[0])
        if not anelli:
            continue
        xs = [q[0] for a in anelli for q in a]
        ys = [q[1] for a in anelli for q in a]
        cand = set()
        for gx in range(int((min(xs) - VICINO) // 4.0), int((max(xs) + VICINO) // 4.0) + 1):
            for gy in range(int((min(ys) - VICINO) // 4.0), int((max(ys) + VICINO) // 4.0) + 1):
                for a, b, k in ixl.g.get((gx, gy), ()):
                    cand.add((a, k))
        hit = set()
        for (x, y), k in cand:
            if k in hit:
                continue
            if any(dentro(x, y, an) for an in anelli) or \
                    (x - voce[1]) ** 2 + (y - voce[2]) ** 2 <= VICINO * VICINO:
                hit.add(k)
        if hit:
            tocca[istat] = sorted(hit)

    for L in linee.values():
        L["ten"] = prevalente(L.pop("_ten"))
        L["peso"] = prevalente(L.pop("_peso"))
        L.pop("_km")
    app["rete_rfi"] = {"fonte": gj.get("fonte", "RFI"), "scaricato": gj.get("scaricato", ""),
                       "linee": linee, "altre": altre, "tocca": tocca}
    json.dump(app, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))

    peso = len(json.dumps({"l": linee, "a": altre}, separators=(",", ":"))) // 1024
    senza = sorted(set(reg) - set(linee))
    print("rete RFI: %d linee del registro con tracciato su %d, %d tratte senza linea, "
          "%d tratte di progetto escluse, %d KB"
          % (len(linee), len(reg), len(altre), scartate, peso))
    print("  data di apertura da OSM per %d linee" % sum(1 for L in linee.values() if L.get("dal")))
    print("  comuni attraversati da almeno una linea RFI: %d" % len(tocca))
    if senza:
        print("  linee del registro senza tracciato RFI: %s" % ", ".join(senza))
    if rifiuti:
        print("  codici RFI scartati perche' il nome non torna: %s" % dict(rifiuti))


if __name__ == "__main__":
    main()
