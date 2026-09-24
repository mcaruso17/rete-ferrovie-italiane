"""Porta la rete ferroviaria OSM sulla proiezione della mappa e la semplifica.

Legge data/rete-ferroviaria.geojson (gradi, prodotto da rete_osm.py) e scrive
dentro l'app i tracciati gia' in coordinate SVG, pronti da disegnare.

La proiezione non viene ricalcolata: si prende da mappa-regioni.json, la stessa
che build_mappa.py usa per le regioni e comuni.py per i comuni. E' l'unico modo
perche' i tre strati si sovrappongano; ricavarne una propria, anche identica
nella formula, li disallineerebbe al primo cambio di parametri.

Uso:
  python3 build_rete.py rete-ferroviaria.geojson linee-ferroviarie.geojson \\
          mappa-regioni.json app-in.json app-out.json [tolleranza]

Sulla tolleranza. I path si scrivono con un decimale, quindi sotto 0,1 unita'
SVG (circa 100 m) non c'e' niente da rappresentare: la precisione del formato
e' il pavimento. Il valore predefinito, 0,12, sta appena sopra quel pavimento e
toglie comunque i tre quarti dei vertici, perche' OSM traccia le curve molto
piu' fitto di quanto una mappa nazionale possa mostrare.
"""
import json
import math
import os
import sys

SRC, LINEE, MAPPA, APP, OUT = sys.argv[1:6]
TOLL = float(sys.argv[6]) if len(sys.argv) > 6 else 0.12


def semplifica(pts, toll):
    """Douglas-Peucker iterativo.

    Iterativo e non ricorsivo come in build_mappa.py: li' gli anelli regionali
    sono corti, qui una polilinea cucita puo' avere decine di migliaia di punti
    e la ricorsione arriverebbe al limite dello stack.
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


def path(pts):
    """Path SVG con comandi relativi dopo il primo punto.

    Assoluto costerebbe quattro o cinque cifre per coordinata su tutta la
    mappa; relativo ne costa una o due, perche' fra due vertici semplificati la
    distanza e' di poche unita'. Sulla rete intera la differenza e' oltre la
    meta' del peso.
    """
    out = ["M%.1f %.1f" % pts[0]]
    px, py = pts[0]
    for x, y in pts[1:]:
        out.append("l%.1f %.1f" % (x - px, y - py))
        px, py = x, y
    return "".join(out)


def main():
    pro = json.load(open(MAPPA))["proiezione"]
    cos0 = math.cos(math.radians(pro["lat0"]))
    x0, y0, s = pro["x0"], pro["y0"], pro["scala"]

    def proietta(coords):
        return [((lon * cos0 - x0) * s, (-lat - y0) * s) for lon, lat in coords]

    # --------------------------------------------------- la rete per stato
    gj = json.load(open(SRC))
    gruppi = {}
    dentro = fuori = 0
    for f in gj["features"]:
        pr = f["properties"]
        s2 = semplifica(proietta(f["geometry"]["coordinates"]), TOLL)
        if len(s2) < 2:
            fuori += 1
            continue
        # in esercizio si distingue l'alta velocita'; per cantieri e progetti
        # non serve, quello che conta li' e' che non sono ancora rete
        chiave = pr.get("st", "eser")
        if chiave == "eser" and pr.get("av"):
            chiave = "av"
        gruppi.setdefault(chiave, []).append(path(s2))
        dentro += len(s2)

    # ------------------------------------------- le linee nominate, cliccabili
    lg = json.load(open(LINEE, encoding="utf-8"))
    linee = {}
    for f in lg["features"]:
        pr = f["properties"]
        tratti = []
        for tratto in f["geometry"]["coordinates"]:
            s2 = semplifica(proietta(tratto), TOLL)
            if len(s2) >= 2:
                tratti.append(path(s2))
        if not tratti:
            continue
        # piu' relazioni OSM possono essere la stessa linea: si accumulano
        # sotto la chiave che aggancio.py usa, cioe' il primo id incontrato
        linee[str(pr["id"])] = {"n": pr["nome"], "d": tratti,
                                "dal": pr.get("dal") or "",
                                "op": pr.get("operatore") or "",
                                "w": pr.get("wikipedia") or ""}

    app = json.load(open(APP))
    app["rete"] = {
        "fonte": "OpenStreetMap, contributori, ODbL",
        "ordinarie": gruppi.get("eser", []),
        "alta_velocita": gruppi.get("av", []),
        "in_costruzione": gruppi.get("cost", []),
        "in_progetto": gruppi.get("prog", []),
    }
    app["linee_geo"] = linee
    json.dump(app, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))

    peso = len(json.dumps(app["rete"], separators=(",", ":")))
    pl = len(json.dumps(app["linee_geo"], separators=(",", ":")))
    print("rete: %d polilinee, %d vertici, %d KB  (%s)"
          % (sum(len(v) for v in gruppi.values()), dentro, peso // 1024,
             ", ".join("%s %d" % (k, len(v)) for k, v in sorted(gruppi.items()))))
    print("linee nominate cliccabili: %d, %d KB" % (len(linee), pl // 1024))
    if fuori:
        print("  %d polilinee scartate: semplificate sotto i due punti" % fuori)


if __name__ == "__main__":
    main()
