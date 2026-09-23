"""Estrae la rete ferroviaria in esercizio da un estratto OpenStreetMap.

Questo e' l'unico passo della catena che esce dalla libreria standard: serve
`osmium` per leggere il formato PBF. Per questo NON sta in build_all.sh e il
suo prodotto, data/rete-ferroviaria.geojson, e' versionato: chi ricostruisce il
sito non ha bisogno ne' dei 2,5 GB dell'estratto ne' della rete. Si rilancia
solo per aggiornare la geometria.

  pip install osmium
  curl -O https://download.openstreetmap.fr/extracts/europe/italy-latest.osm.pbf
  python3 tools/rete_osm.py italy-latest.osm.pbf

Nota sulla fonte: overpass-api.de non risponde da questo ambiente (il CONNECT
passa, la destinazione resetta), quindi si scarica l'estratto in blocco. Per
tutte le ferrovie italiane e' comunque la strada giusta: con Overpass sarebbero
decine di interrogazioni con rate limit.

Cosa si tiene e cosa no. Servono le linee di corsa, non l'armamento: i binari
di stazione e di scalo (qualsiasi way con un tag `service`: siding, spur, yard,
crossover) moltiplicano la geometria senza aggiungere niente di leggibile a
scala nazionale. Dismesse, in costruzione e in progetto cadono da sole perche'
in OSM hanno un valore di `railway` diverso. Restano fuori anche tram e
metropolitane, che sono reti urbane.
"""
import argparse
import json
import os
from collections import defaultdict

import osmium

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TIENI = {"rail", "narrow_gauge"}
SCARTA_USO = {"industrial", "military", "test", "tourism"}


def leggi(pbf):
    """Le linee di corsa dell'estratto, in gradi, una lista per way."""
    fuori = []
    # i nodi vanno letti perche' la cache delle coordinate si riempia, quindi
    # il filtro che restringe alle sole way viene dopo, non prima
    proc = (osmium.FileProcessor(pbf, osmium.osm.NODE | osmium.osm.WAY)
            .with_locations("flex_mem")
            .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
            .with_filter(osmium.filter.KeyFilter("railway")))
    for w in proc:
        t = w.tags
        if t.get("railway") not in TIENI:
            continue
        if "service" in t or t.get("usage") in SCARTA_USO:
            continue
        pts = []
        for n in w.nodes:
            if not n.location.valid():
                continue
            p = (round(n.lon, 6), round(n.lat, 6))
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(pts) >= 2:
            fuori.append((1 if t.get("highspeed") == "yes" else 0, pts))
    return fuori


def cuci(linee):
    """Unisce in polilinee lunghe le tratte che condividono un estremo.

    OSM spezza una linea a ogni cambio di attributo, quindi la stessa ferrovia
    arriva in decine di pezzi. Ricucirli serve al disegno (molti meno `M` nel
    path) e alla semplificazione, che su una polilinea lunga toglie molto di
    piu' che su tanti frammenti. Dove si incontrano tre o piu' linee vince la
    catena che arriva per prima: le altre restano separate.
    """
    estremi = defaultdict(list)
    for i, ln in enumerate(linee):
        estremi[ln[0]].append(i)
        estremi[ln[-1]].append(i)
    usata = [False] * len(linee)
    fuori = []
    for i, ln in enumerate(linee):
        if usata[i]:
            continue
        usata[i] = True
        catena = list(ln)
        for _ in range(2):                  # prima in coda, poi in testa
            while True:
                coda = catena[-1]
                j = next((k for k in estremi[coda]
                          if not usata[k] and (linee[k][0] == coda
                                               or linee[k][-1] == coda)), None)
                if j is None:
                    break
                usata[j] = True
                seg = linee[j]
                catena.extend(seg[1:] if seg[0] == coda else seg[-2::-1])
            catena.reverse()
        fuori.append(catena)
    return fuori


def semplifica(pts, toll):
    """Douglas-Peucker iterativo, tolleranza in gradi.

    Serve solo a togliere il peso che nessuno usera' mai: OSM traccia le curve
    con un vertice ogni pochi metri, e il passo successivo (build_rete.py) non
    puo' comunque rappresentare niente sotto il centinaio di metri, perche' i
    path SVG si scrivono con un decimale. Qui si taglia molto piu' in basso di
    li', intorno ai 15 m, cosi' il file versionato resta riusabile anche per
    scopi diversi dal disegno della mappa.

    Iterativo e non ricorsivo: una polilinea cucita puo' avere decine di
    migliaia di punti e la ricorsione arriverebbe al limite dello stack.
    """
    if len(pts) < 3:
        return pts
    tieni = [False] * len(pts)
    tieni[0] = tieni[-1] = True
    pila = [(0, len(pts) - 1)]
    t2 = toll * toll
    while pila:
        i, j = pila.pop()
        if j <= i + 1:
            continue
        x0, y0 = pts[i]
        dx, dy = pts[j][0] - x0, pts[j][1] - y0
        den = dx * dx + dy * dy
        peggio, ip = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            if den:
                t = ((px - x0) * dx + (py - y0) * dy) / den
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                ex, ey = px - (x0 + t * dx), py - (y0 + t * dy)
            else:
                ex, ey = px - x0, py - y0
            d = ex * ex + ey * ey
            if d > peggio:
                peggio, ip = d, k
        if peggio > t2:
            tieni[ip] = True
            pila.append((i, ip))
            pila.append((ip, j))
    return [p for p, k in zip(pts, tieni) if k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf", help="estratto .osm.pbf che copre l'Italia")
    ap.add_argument("--out", default=os.path.join(ROOT, "data",
                                                  "rete-ferroviaria.geojson"))
    ap.add_argument("--tolleranza", type=float, default=0.00014,
                    help="tolleranza Douglas-Peucker in gradi (predefinita "
                         "0,00014, circa 15 m alle latitudini italiane)")
    args = ap.parse_args()

    linee = leggi(args.pbf)
    print("linee di corsa  %6d tratte, %7d vertici"
          % (len(linee), sum(len(p) for _, p in linee)))

    gruppi = defaultdict(list)
    for av, pts in linee:
        gruppi[av].append(pts)

    feats = []
    for av in sorted(gruppi):
        for catena in cuci(gruppi[av]):
            s2 = semplifica(catena, args.tolleranza)
            if len(s2) < 2:
                continue
            feats.append({
                "type": "Feature",
                "properties": {"av": av},
                "geometry": {"type": "LineString", "coordinates":
                             [list(p) for p in s2]},
            })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats},
              open(args.out, "w"), separators=(",", ":"))
    pts = sum(len(f["geometry"]["coordinates"]) for f in feats)
    av = sum(1 for f in feats if f["properties"]["av"])
    print("cucite e ridotte %5d polilinee, %7d vertici (tolleranza %.5f gradi)"
          % (len(feats), pts, args.tolleranza))
    print("alta velocita   %6d polilinee" % av)
    print("scritto         %6.2f MB  %s"
          % (os.path.getsize(args.out) / 1e6, args.out))


if __name__ == "__main__":
    main()
