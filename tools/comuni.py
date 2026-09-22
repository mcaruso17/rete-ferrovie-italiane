"""Attribuisce gli interventi ai comuni che il contratto nomina.

ATTENZIONE al significato del dato. Questi NON sono i comuni attraversati
dall'infrastruttura: sono i comuni CITATI nella descrizione dell'intervento,
cioe' i capi tratta, i nodi e le stazioni che RFI scrive nel titolo dell'opera.
Un raddoppio Bovino-Cervaro attraversa anche i comuni in mezzo, che qui non
compaiono perche' il documento non li nomina e i Contratti di Programma non
contengono ne' tracciati ne' coordinate. Per i comuni realmente attraversati
servirebbe la geometria delle linee (OpenStreetMap), che qui non c'e'.

Le regole di lettura sono quelle di toponimi.py, le stesse dell'attribuzione
regionale, cosi' i due strati non possono contraddirsi.

Uso:
  python3 comuni.py MUNICIPALITIES.geojson PROVINCES.geojson app.json \\
          mappa-regioni.json out.json [tolleranza]
"""
import json, os, sys, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toponimi import ESCLUSI_COMUNI, MANUALI_COMUNI, norm, compila, trova

MUN, PROV, APP, MAPPA, OUT = sys.argv[1:6]
# i comuni sono piccoli: la tolleranza delle regioni (0,012) li ridurrebbe a
# triangoli. 0,0018 vale circa 200 m, abbastanza per riconoscerne la forma
TOLL = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0018
AREA_MIN = 0.00002


def gazzettiere(mun, prov):
    """Nome di luogo -> codice ISTAT del comune.

    Tiene solo i nomi che identificano un comune senza ambiguita': se lo stesso
    nome esiste in piu' comuni non vale, a meno che sia un capoluogo di
    provincia, nel qual caso vince il capoluogo.
    """
    per_nome = collections.defaultdict(list)
    info = {}
    for f in mun["features"]:
        p = f["properties"]
        c = p["com_istat_code"]
        info[c] = {"nome": p["name"], "prov": p["prov_name"],
                   "pa": p["prov_acr"], "reg": p["reg_istat_code"]}
        per_nome[norm(p["name"])].append(c)

    gaz = {n: cs[0] for n, cs in per_nome.items()
           if n and len(n) >= 5 and n not in ESCLUSI_COMUNI and len(cs) == 1}

    for f in prov["features"]:
        nome = norm(f["properties"]["prov_name"])
        if nome in ESCLUSI_COMUNI:
            continue
        # il comune capoluogo e' quello omonimo dentro la sua stessa provincia
        omonimi = [c for c in per_nome.get(nome, [])
                   if norm(info[c]["prov"]) == nome]
        if omonimi:
            gaz[nome] = omonimi[0]

    per_coppia = {(norm(i["nome"]), i["pa"]): c for c, i in info.items()}
    mancanti = []
    for alias, coppia in MANUALI_COMUNI.items():
        c = per_coppia.get((norm(coppia[0]), coppia[1]))
        if c:
            gaz[alias] = c
        else:
            mancanti.append(alias)
    if mancanti:
        print("alias senza comune corrispondente: %s" % ", ".join(mancanti),
              file=sys.stderr)
    return gaz, info


# --- geometria: stessa proiezione della mappa regionale ---------------------

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


def tracciato(geom, pro):
    k = math.cos(math.radians(pro["lat0"]))
    x0, y0, S = pro["x0"], pro["y0"], pro["scala"]
    parti = []
    for anello in anelli(geom):
        pts = [(lon * k, -lat) for lon, lat in anello]
        if area(pts) < AREA_MIN:
            continue
        s = douglas_peucker(pts, TOLL)
        if len(s) >= 4:
            parti.append(s)
    if not parti:
        return None
    out = []
    for s in parti:
        c = ["M%.1f %.1f" % ((s[0][0] - x0) * S, (s[0][1] - y0) * S)]
        for x, y in s[1:]:
            c.append("L%.1f %.1f" % ((x - x0) * S, (y - y0) * S))
        c.append("Z")
        out.append("".join(c))
    # un punto su cui appoggiare il segnaposto: molti comuni a questa scala
    # sono larghi pochi pixel e il poligono da solo non si riesce a cliccare
    grande = max(parti, key=len)
    cx = sum(x for x, _y in grande) / len(grande)
    cy = sum(y for _x, y in grande) / len(grande)
    return ["".join(out), round((cx - x0) * S, 1), round((cy - y0) * S, 1)]


def lungo_asse(punti):
    """Indici dei punti ordinati lungo la direzione in cui sono piu' distesi.

    L'ordine in cui il documento cita i luoghi non e' quello del percorso:
    "Roma-Pescara ... Roma-Mandela-Tagliacozzo" nomina prima i due capi e poi
    le stazioni in mezzo, e una spezzata che li unisse in quell'ordine
    tornerebbe indietro due volte. Proiettare sull'asse principale del gruppo
    (il primo autovettore della covarianza) rimette i punti in fila.

    Funziona sui corridoi, cioe' sul caso che interessa. Su un nodo con
    diramazioni a stella un ordine giusto non esiste.
    """
    n = len(punti)
    mx = sum(p[0] for p in punti) / n
    my = sum(p[1] for p in punti) / n
    sxx = sum((p[0] - mx) ** 2 for p in punti)
    syy = sum((p[1] - my) ** 2 for p in punti)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in punti)
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    lam = tr / 2.0 + math.sqrt(max(0.0, tr * tr / 4.0 - det))
    if abs(sxy) > 1e-9:
        vx, vy = lam - syy, sxy
    elif sxx >= syy:
        vx, vy = 1.0, 0.0
    else:
        vx, vy = 0.0, 1.0
    k = math.hypot(vx, vy) or 1.0
    vx, vy = vx / k, vy / k
    return sorted(range(n),
                  key=lambda i: (punti[i][0] - mx) * vx + (punti[i][1] - my) * vy)


def spezzata(istat, forme):
    """Collegamento schematico fra i comuni nominati da un intervento.

    NON e' il tracciato della linea: e' una spezzata fra i punti che il
    contratto nomina, buona solo a far vedere in che zona cade l'opera.
    """
    pts = [(forme[i][1], forme[i][2]) for i in istat if i in forme]
    if len(pts) < 2:
        return None
    ordine = lungo_asse(pts)
    d = ["M%.1f %.1f" % pts[ordine[0]]]
    for i in ordine[1:]:
        d.append("L%.1f %.1f" % pts[i])
    return "".join(d)


def main():
    mun = json.load(open(MUN))
    prov = json.load(open(PROV))
    gaz, info = gazzettiere(mun, prov)
    pattern = compila(gaz)

    app = json.load(open(APP))
    per_intervento, senza = {}, 0
    for p in app["progetti"]:
        trovati = []
        for nome in trova(p.get("n") or "", pattern):
            c = gaz[nome]
            if c not in trovati:
                trovati.append(c)
        if trovati:
            per_intervento[p["c"]] = trovati
        else:
            senza += 1

    usati = {c for v in per_intervento.values() for c in v}
    pro = json.load(open(MAPPA))["proiezione"]
    forme = {}
    for f in mun["features"]:
        c = f["properties"]["com_istat_code"]
        if c in usati:
            d = tracciato(f["geometry"], pro)
            if d:
                forme[c] = d

    app["comuni"] = {c: [info[c]["nome"], info[c]["pa"], info[c]["reg"],
                         info[c]["prov"]]
                     for c in sorted(usati)}
    app["comuni_intervento"] = per_intervento
    app["mappa_comuni"] = forme
    app["tratte_schematiche"] = {}
    for cod, istat in per_intervento.items():
        d = spezzata(istat, forme)
        if d:
            app["tratte_schematiche"][cod] = d
    json.dump(app, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))

    tot = len(app["progetti"])
    print("interventi con almeno un comune nominato: %d su %d (%d%%)"
          % (tot - senza, tot, round(100 * (tot - senza) / tot)))
    print("comuni distinti: %d, di cui disegnabili %d" % (len(usati), len(forme)))
    print("collegamenti schematici: %d" % len(app["tratte_schematiche"]))
    n = collections.Counter(len(v) for v in per_intervento.values())
    print("comuni per intervento:", dict(sorted(n.items())))
    print("dimensione: %.0f KB" % (os.path.getsize(OUT) / 1024))


main()
