"""Aggancia gli interventi del contratto alle linee ferroviarie nominate in OSM.

ATTENZIONE al significato del dato. Questo e' l'unico punto del progetto in cui
si produce un'informazione che i documenti non contengono: i Contratti di
Programma non dicono su quale linea insiste un intervento, e qui lo si deduce.
E' una deduzione, non un fatto. Ogni aggancio porta il livello di confidenza e
la prova su cui si regge, la pagina lo dichiara al lettore, e nessun altro dato
del sito viene derivato da qui.

Le prove sono due, indipendenti fra loro.

**Nome.** La descrizione dell'intervento nomina i capi della linea: "Raddoppio
Milano-Mortara" contro "Ferrovia Milano-Mortara". Prova forte quando i capi
nominati sono due, perche' l'opera dichiara la tratta; debole con uno solo,
perche' Roma e Bologna compaiono in decine di nomi di linea.

**Geometria.** La linea attraversa i comuni che l'intervento nomina. Questa
prova non dipende da come le due fonti chiamano le cose, quindi prende i casi
che il nome manca: RFI scrive "Raddoppio Bovino-Cervaro", che sono stazioni
intermedie e non compaiono in nessun nome di linea OSM, ma la linea che le
attraversa si trova lo stesso.

Il livello finale nasce dalla prova migliore. Le due prove restano distinte nel
risultato perche' vogliono dire cose diverse, e il lettore deve poterle
distinguere.

Uso:
  python3 aggancio.py linee-ferroviarie.geojson mappa-regioni.json \\
          app-in.json app-out.json
"""
import collections
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toponimi import norm, linea_av, cita_av, declassa  # noqa: E402

LINEE, MAPPA, APP, OUT = sys.argv[1:5]

# parole che nei nomi OSM delle linee non identificano un luogo
VUOTE = {
    "linea", "ferrovia", "ferroviaria", "tratta", "via", "di", "del", "della",
    "dei", "delle", "da", "a", "al", "alla", "il", "lo", "la", "e", "per",
    "centrale", "c", "le", "cle", "smistamento", "scalo", "porta", "nuova",
    "bassa", "alta", "nord", "sud", "est", "ovest", "raccordo", "bretella",
    "railway", "line", "bahn", "strecke", "stazione", "fs", "rfi", "velocita",
}
# un capo che compare in molti nomi di linea non prova niente da solo: e' un
# nodo, non una tratta. La soglia esce dai dati, non da un elenco scritto a
# mano, cosi' non invecchia con il cambiare della base OSM.
NODO_SE_OLTRE = 3
# un vertice di linea entro questo raggio dal centroide comunale, quando il
# poligono non lo contiene: un'unita' di mappa vale circa 980 m
VICINO = 3.0


def estremi(nome):
    """I capi di una linea, dal suo nome OSM.

    I nomi arrivano in forme molto diverse: "Treviglio-Cremona", "Savona - San
    Giuseppe di Cairo (via Santuario)", "Linea Catania Centrale - Agrigento
    Centrale / Agrigento Bassa-Porto Empedocle". Si tolgono le parentesi, si
    spezza su trattini e barre, e di ogni pezzo restano le parole che non sono
    qualificatori.
    """
    n = re.sub(r"\([^)]*\)", " ", nome or "")
    pezzi = re.split(r"\s*[-–—/]\s*|\s*=?>+\s*|\s*<=>\s*", n)
    fuori = []
    for p in pezzi:
        parole = [w for w in norm(p).split() if w and w not in VUOTE]
        if parole:
            fuori.append(" ".join(parole))
    return fuori


def anelli_da_path(d):
    """I poligoni di un path SVG prodotto da comuni.py: M x y L x y ... Z."""
    fuori = []
    for pezzo in d.split("M")[1:]:
        pts = []
        for m in re.finditer(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", pezzo):
            pts.append((float(m.group(1)), float(m.group(2))))
        if len(pts) >= 3:
            fuori.append(pts)
    return fuori


def dentro(px, py, anello):
    """Punto nel poligono, ray casting."""
    d = False
    n = len(anello)
    j = n - 1
    for i in range(n):
        xi, yi = anello[i]
        xj, yj = anello[j]
        if (yi > py) != (yj > py):
            if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                d = not d
        j = i
    return d


def main():
    pro = json.load(open(MAPPA, encoding="utf-8"))["proiezione"]
    cos0 = math.cos(math.radians(pro["lat0"]))
    x0, y0, s = pro["x0"], pro["y0"], pro["scala"]

    # ---------------------------------------------------------- le linee
    gj = json.load(open(LINEE, encoding="utf-8"))
    per_nome = {}
    for f in gj["features"]:
        p = f["properties"]
        capi = estremi(p["nome"])
        if not capi:
            continue
        # La chiave sono i capi ordinati, non il nome: OSM porta la stessa
        # linea sotto voci diverse ("Ferrovia Torino-Genova" e "Linea
        # Torino-Genova") e anche invertita ("Ferrovia Bari-Taranto" e
        # "Ferrovia Taranto-Bari"). Tenerle separate mostrerebbe due o tre
        # volte lo stesso aggancio come se fossero linee diverse.
        chiave = tuple(sorted(set(capi)))
        L = per_nome.setdefault(chiave, {
            "id": p["id"], "nome": p["nome"], "uso": p.get("uso", ""),
            "dal": p.get("dal", ""), "capi": capi, "punti": [], "fusi": []})
        L["fusi"].append(p["id"])
        if not L.get("dal") and p.get("dal"):
            L["dal"] = p["dal"]
        # fra i nomi che si fondono vince il piu' descrittivo
        if len(p["nome"]) > len(L["nome"]):
            L["nome"] = p["nome"]
        for tratto in f["geometry"]["coordinates"]:
            for lon, lat in tratto:
                L["punti"].append(((lon * cos0 - x0) * s, (-lat - y0) * s))
    linee = [L for L in per_nome.values() if L["capi"] and L["punti"]]

    # quante linee distinte hanno quel capo: sopra la soglia e' un nodo
    freq = collections.Counter(c for L in linee for c in set(L["capi"]))

    # -------------------------------------------- indice dei vertici linea
    # una griglia grossolana: senza, il controllo comune per comune sarebbe
    # 300 linee x 50.000 vertici x 200 comuni
    CELLA = 4.0
    griglia = collections.defaultdict(list)
    for i, L in enumerate(linee):
        for (x, y) in L["punti"]:
            griglia[(int(x // CELLA), int(y // CELLA))].append((i, x, y))

    app = json.load(open(APP, encoding="utf-8"))
    MCOM = app.get("mappa_comuni", {})
    PERINT = app.get("comuni_intervento", {})

    # ------------------------------------------- linee che toccano un comune
    tocca = collections.defaultdict(set)      # istat -> indici di linea
    for istat, voce in MCOM.items():
        anelli = anelli_da_path(voce[0])
        if not anelli:
            continue
        xs = [p[0] for a in anelli for p in a]
        ys = [p[1] for a in anelli for p in a]
        bx0, bx1 = min(xs) - VICINO, max(xs) + VICINO
        by0, by1 = min(ys) - VICINO, max(ys) + VICINO
        cx, cy = voce[1], voce[2]
        cand = []
        for gx in range(int(bx0 // CELLA), int(bx1 // CELLA) + 1):
            for gy in range(int(by0 // CELLA), int(by1 // CELLA) + 1):
                cand.extend(griglia.get((gx, gy), ()))
        for i, x, y in cand:
            if i in tocca[istat]:
                continue
            if any(dentro(x, y, a) for a in anelli):
                tocca[istat].add(i)
            elif (x - cx) ** 2 + (y - cy) ** 2 <= VICINO * VICINO:
                # il centroide e' un ripiego per i comuni piccolissimi, che a
                # questa scala sono semplificati a pochi punti e possono non
                # contenere nessun vertice pur essendo attraversati
                tocca[istat].add(i)

    # ------------------------------------------------------- gli agganci
    per_int = {}
    livelli = collections.Counter()
    prove = collections.Counter()
    for pr in app["progetti"]:
        cod = pr["c"]
        testo = norm(pr.get("n") or "")
        comuni = PERINT.get(cod, [])
        geo = collections.Counter()
        for istat in comuni:
            for i in tocca.get(istat, ()):
                geo[i] += 1

        trovate = []
        for i, L in enumerate(linee):
            capi = [c for c in L["capi"]
                    if re.search(r"\b" + re.escape(c) + r"\b", testo)]
            n_geo = geo.get(i, 0)
            if not capi and not n_geo:
                continue
            specifici = [c for c in capi if freq[c] <= NODO_SE_OLTRE]
            if len(capi) >= 2 or n_geo >= 2:
                conf = "alta"
            elif specifici or n_geo == 1:
                conf = "media"
            else:
                conf = "bassa"
            # una linea AV vale solo se l'intervento dice di esserlo: vedi
            # linea_av in toponimi.py per il caso che l'ha resa necessaria
            if linea_av(L["nome"]) and not cita_av(pr.get("n") or ""):
                conf = declassa(conf)
            p = []
            if len(capi) >= 2:
                p.append("nome")
            elif capi:
                p.append("nome-parziale")
            if n_geo:
                p.append("comuni")
            trovate.append({"id": L["id"], "nome": L["nome"], "conf": conf,
                            "capi": capi, "comuni": n_geo, "prova": p})
        if not trovate:
            continue
        ordine = {"alta": 0, "media": 1, "bassa": 2}
        trovate.sort(key=lambda t: (ordine[t["conf"]], -t["comuni"],
                                    -len(t["capi"]), t["nome"]))
        # oltre una manciata di linee l'informazione smette di informare
        trovate = trovate[:6]
        per_int[cod] = trovate
        livelli[trovate[0]["conf"]] += 1
        for pv in trovate[0]["prova"]:
            prove[pv] += 1

    app["linee"] = {str(L["id"]): {"n": L["nome"], "u": L["uso"]}
                    for L in linee}
    app["linee_intervento"] = per_int

    # build_rete.py ha scritto una voce cliccabile per ogni relazione OSM, ma
    # qui le relazioni si fondono sui capi: senza questa riconciliazione le
    # linee non canoniche resterebbero cliccabili a vuoto, perche' gli agganci
    # stanno tutti sotto l'id sopravvissuto. Si fondono anche le geometrie,
    # cosi' cliccando un tratto si accende tutta la linea e non mezza.
    geo = app.get("linee_geo") or {}
    fuso = {}
    orfani = 0
    for L in linee:
        capo = str(L["id"])
        d = []
        for rid in L["fusi"]:
            v = geo.get(str(rid))
            if v:
                d.extend(v["d"])
        if not d:
            orfani += 1
            continue
        fuso[capo] = {"n": L["nome"], "d": d, "dal": L.get("dal", ""),
                      "op": (geo.get(capo) or {}).get("op", ""),
                      "w": (geo.get(capo) or {}).get("w", "")}
    app["linee_geo"] = fuso
    if orfani:
        print("  %d linee senza geometria, non cliccabili" % orfani)
    print("linee cliccabili riconciliate: %d (erano %d voci separate)"
          % (len(fuso), len(geo)))
    json.dump(app, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))

    tot = len(app["progetti"])
    print("linee distinte per nome: %d (da %d relazioni OSM)"
          % (len(linee), len(gj["features"])))
    print("interventi con almeno una linea: %d su %d (%d%%)"
          % (len(per_int), tot, round(100 * len(per_int) / tot)))
    print("  confidenza del migliore: alta %d, media %d, bassa %d"
          % (livelli["alta"], livelli["media"], livelli["bassa"]))
    print("  prova del migliore: %s"
          % ", ".join("%s %d" % kv for kv in prove.most_common()))


if __name__ == "__main__":
    main()
