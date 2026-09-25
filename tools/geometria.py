"""Funzioni geometriche condivise, sulla proiezione della mappa.

Stavano copiate in build_rete.py, aggancio.py e aggancio_pc.py. Da quando la
rete ha due fonti (OpenStreetMap e RFI) servono a piu' passi, e tenerle in un
posto solo evita che due copie divergano: una semplificazione diversa fra due
strati li disallineerebbe sulla mappa.
"""
import collections
import json
import math
import re


def proiettore(mappa):
    """La proiezione di mappa-regioni.json: la stessa per tutti gli strati."""
    pro = json.load(open(mappa, encoding="utf-8"))["proiezione"]
    cos0 = math.cos(math.radians(pro["lat0"]))
    x0, y0, s = pro["x0"], pro["y0"], pro["scala"]
    return lambda lon, lat: ((lon * cos0 - x0) * s, (-lat - y0) * s)


def semplifica(pts, toll):
    """Douglas-Peucker iterativo (come in build_rete.py, dove e' spiegato)."""
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
                t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / den))
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
    """Path SVG: primo punto assoluto, poi spostamenti relativi a un decimale."""
    out, prec = [], None
    for x, y in pts:
        x, y = round(x, 1), round(y, 1)
        if prec is None:
            out.append("M%.1f %.1f" % (x, y))
        elif (x, y) != prec:
            out.append("l%.1f %.1f" % (x - prec[0], y - prec[1]))
        prec = (x, y)
    return "".join(out) if len(out) > 1 else None


def punti_da_path(d):
    """I vertici assoluti di un path relativo "M x y l dx dy ..."."""
    pts, x, y = [], 0.0, 0.0
    for cmd, a, b in re.findall(r"([Ml])(-?[\d.]+) (-?[\d.]+)", d):
        if cmd == "M":
            x, y = float(a), float(b)
        else:
            x, y = x + float(a), y + float(b)
        pts.append((x, y))
    return pts


def anelli_da_path(d):
    """I poligoni di un path SVG assoluto prodotto da comuni.py."""
    fuori = []
    for pezzo in d.split("M")[1:]:
        pts = [(float(a), float(b)) for a, b in
               re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", pezzo)]
        if len(pts) >= 3:
            fuori.append(pts)
    return fuori


def dentro(px, py, anello):
    """Punto nel poligono, ray casting."""
    d = False
    j = len(anello) - 1
    for i in range(len(anello)):
        xi, yi = anello[i]
        xj, yj = anello[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            d = not d
        j = i
    return d


def dist_segm(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    den = dx * dx + dy * dy
    t = 0.0 if not den else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / den))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


class IndiceSegmenti:
    """Segmenti di una o piu' linee su una griglia, per chiedere "quanto e'
    vicino questo punto" senza confrontarlo con tutta la rete."""

    def __init__(self, cella=5.0):
        self.c = cella
        self.g = collections.defaultdict(list)

    def aggiungi(self, pts, chiave=None):
        C = self.c
        for a, b in zip(pts, pts[1:]):
            for gx in range(int(min(a[0], b[0]) // C) - 1, int(max(a[0], b[0]) // C) + 2):
                for gy in range(int(min(a[1], b[1]) // C) - 1, int(max(a[1], b[1]) // C) + 2):
                    self.g[(gx, gy)].append((a, b, chiave))

    def vicine(self, p, raggio):
        """Le chiavi delle linee che passano entro raggio dal punto."""
        out = set()
        for a, b, k in self.g.get((int(p[0] // self.c), int(p[1] // self.c)), ()):
            if k not in out and dist_segm(p, a, b) <= raggio:
                out.add(k)
        return out


    def piu_vicina(self, p, raggio):
        """La chiave della linea piu' vicina entro raggio, o None."""
        best, kb = raggio, None
        for a, b, k in self.g.get((int(p[0] // self.c), int(p[1] // self.c)), ()):
            d = dist_segm(p, a, b)
            if d <= best:
                best, kb = d, k
        return kb


def campiona(pts, passo=0.3):
    """Punti a passo costante lungo la spezzata.

    Le quote "che parte del tracciato sta su quella linea" vanno misurate sulla
    lunghezza, non sui vertici: la semplificazione lascia molti vertici nelle
    curve e pochi nei rettilinei, e su una tratta corta due vertici in
    stazione pesavano un terzo del totale (Parma-Vicofertile risultava per un
    terzo sulla Milano-Bologna)."""
    out = []
    for a, b in zip(pts, pts[1:]):
        L = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        n = max(1, int(L / passo))
        out.extend((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n))
    if pts:
        out.append(pts[-1])
    return out


def quota_vicina(pts, linea_paths, raggio=2.0):
    """Che parte dei punti sta entro raggio dalla linea (lista di path)."""
    ix = IndiceSegmenti()
    for d in linea_paths:
        ix.aggiungi(punti_da_path(d), 0)
    if not pts:
        return 0.0
    return sum(1 for p in pts if ix.vicine(p, raggio)) / len(pts)
