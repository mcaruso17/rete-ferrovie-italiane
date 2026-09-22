"""Riduce i confini regionali ISTAT a tracciati SVG leggeri per la mappa.

Fonte: openpolis/geojson-italy (dati ISTAT, CC BY 4.0). Il file originale pesa
2,7 MB: qui viene proiettato su un piano e semplificato con Douglas-Peucker,
scartando le isole minori sotto la soglia d'area, fino a qualche decina di KB.
"""
import json, math, sys

SRC = sys.argv[1]
OUT = sys.argv[2]
TOLL = float(sys.argv[3]) if len(sys.argv) > 3 else 0.012
AREA_MIN = float(sys.argv[4]) if len(sys.argv) > 4 else 0.004

LAT0 = 42.0  # latitudine di riferimento per la correzione delle longitudini


def proietta(lon, lat):
    return lon * math.cos(math.radians(LAT0)), -lat


def dist_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def douglas_peucker(pts, toll):
    if len(pts) < 3:
        return pts
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        d = dist_seg(pts[i], pts[0], pts[-1])
        if d > dmax:
            dmax, idx = d, i
    if dmax <= toll:
        return [pts[0], pts[-1]]
    return (douglas_peucker(pts[:idx + 1], toll)[:-1]
            + douglas_peucker(pts[idx:], toll))


def area(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def anelli(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        return [c[0]]
    if t == "MultiPolygon":
        return [p[0] for p in c]
    return []


d = json.load(open(SRC))
regioni, tutti = [], []
for f in d["features"]:
    p = f["properties"]
    nome = p["reg_name"].split("/")[0]
    parti = []
    for anello in anelli(f["geometry"]):
        pts = [proietta(x, y) for x, y in anello]
        if area(pts) < AREA_MIN:
            continue
        s = douglas_peucker(pts, TOLL)
        if len(s) >= 4:
            parti.append(s)
            tutti.extend(s)
    if not parti:
        continue
    regioni.append({"nome": nome, "istat": p["reg_istat_code"],
                    "iso": p["reg_iso_3166_2"], "parti": parti})

xs = [p[0] for p in tutti]
ys = [p[1] for p in tutti]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
W = 1000.0
S = W / (x1 - x0)
H = (y1 - y0) * S


def d_attr(parti):
    out = []
    for s in parti:
        c = ["M%.1f %.1f" % ((s[0][0] - x0) * S, (s[0][1] - y0) * S)]
        for x, y in s[1:]:
            c.append("L%.1f %.1f" % ((x - x0) * S, (y - y0) * S))
        c.append("Z")
        out.append("".join(c))
    return "".join(out)


mappa = {
    "viewBox": "0 0 %.0f %.0f" % (W, H),
    "fonte": "Confini regionali ISTAT via openpolis/geojson-italy (CC BY 4.0)",
    # la trasformazione serve a chi disegna altri confini sulla stessa mappa
    # (i comuni): senza questi numeri i due strati non si sovrappongono
    "proiezione": {"lat0": LAT0, "x0": x0, "y0": y0, "scala": S},
    "regioni": [{"n": r["nome"], "istat": r["istat"], "iso": r["iso"],
                 "d": d_attr(r["parti"])} for r in regioni],
}
json.dump(mappa, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
import os
print("%d regioni, %d anelli, %.0f KB, viewBox %s"
      % (len(regioni), sum(len(r["parti"]) for r in regioni),
         os.path.getsize(OUT) / 1024, mappa["viewBox"]))
