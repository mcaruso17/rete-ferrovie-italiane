"""Aggancia gli interventi del CdP ai progetti del Piano Commerciale RFI.

Qui il legame non si deduce: ogni elemento del Piano Commerciale (una tratta
di progetto, una localita' potenziata o nuova) porta nel campo "Riferimento
CdP-I" il codice dell'intervento, scritto da RFI. E' il livello piu' alto che
il sito possa mostrare, sopra "confermato", e resta comunque una fonte esterna
ai contratti: il Piano Commerciale e' un documento di RFI con le sue date e le
sue classificazioni, non il Contratto di Programma.

Serve anche a un'altra cosa: mettere alla prova le associazioni dedotte.
Per gli interventi che hanno sia il tracciato RFI sia un aggancio dedotto a
una linea OSM si misura se i due si sovrappongono. E' la prima verifica
esterna del metodo di aggancio, e il risultato va in pagina com'e'.

Uso:
  python3 aggancio_pc.py piano-commerciale-2026.json mappa-regioni.json \\
          app-in.json app-out.json
"""
import collections
import json
import math
import re
import sys

PC, MAPPA, APP, OUT = sys.argv[1:5]

TIPO = {"tratte": "tr", "localita_potenziate": "lp", "localita_nuove": "ln"}
# le caratteristiche dell'intervento, come le marca RFI con 0/1
CARATTERI = [("NUOVA_LINEA", "nuova linea"), ("RADDOPPIO_QUADRUPLICAMENTO", "raddoppio o quadruplicamento"),
             ("RIAPERTURA_LINEA", "riapertura"), ("ELETTRIFICAZIONE", "elettrificazione"),
             ("VELOCIZZAZIONE", "velocizzazione"), ("UPGRADE_TECNOLOGICO", "upgrade tecnologico"),
             ("UPGRADE_PRESTAZIONALE", "upgrade prestazionale"), ("PRG", "nuovo piano regolatore"),
             ("NUOVO_IMPIANTO", "nuovo impianto"), ("NUOVO_TERMINAL", "nuovo terminal"),
             ("POTENZIAMENTO_TERMINAL", "potenziamento terminal")]
# entro questa distanza (unita' di mappa, circa 1 km) un vertice del tracciato
# RFI conta come "sulla" linea OSM: le due geometrie sono semplificate in modo
# diverso e non coincidono al metro
VICINO = 2.0


def proiettore():
    pro = json.load(open(MAPPA, encoding="utf-8"))["proiezione"]
    cos0 = math.cos(math.radians(pro["lat0"]))
    x0, y0, s = pro["x0"], pro["y0"], pro["scala"]
    return lambda lon, lat: ((lon * cos0 - x0) * s, (-lat - y0) * s)


def path(pts):
    """Come in build_rete.py: primo punto assoluto, poi spostamenti relativi."""
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


def dist_segm(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    den = dx * dx + dy * dy
    t = 0.0 if not den else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / den))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def quota_vicina(pts, linea_paths):
    """Che parte dei vertici RFI sta a meno di VICINO dalla linea OSM."""
    segm = []
    for d in linea_paths:
        q = punti_da_path(d)
        segm.extend(zip(q, q[1:]))
    if not segm or not pts:
        return 0.0
    # griglia sui segmenti, per non confrontare ogni vertice con ogni segmento
    C = 5.0
    gr = collections.defaultdict(list)
    for a, b in segm:
        for gx in range(int(min(a[0], b[0]) // C) - 1, int(max(a[0], b[0]) // C) + 2):
            for gy in range(int(min(a[1], b[1]) // C) - 1, int(max(a[1], b[1]) // C) + 2):
                gr[(gx, gy)].append((a, b))
    vicini = 0
    for p in pts:
        cand = gr.get((int(p[0] // C), int(p[1] // C)), ())
        if any(dist_segm(p, a, b) <= VICINO for a, b in cand):
            vicini += 1
    return vicini / len(pts)


def main():
    pr = proiettore()
    pc = json.load(open(PC, encoding="utf-8"))
    app = json.load(open(APP, encoding="utf-8"))
    codici = {p["c"] for p in app["progetti"]}

    el, per_int, ignoti = {}, collections.defaultdict(list), collections.Counter()
    for nome, righe in pc["layer"].items():
        t = TIPO[nome]
        for r in righe:
            p, g = r["p"], r["g"]
            cdp = [c for c in p["CDP"] if c in codici]
            for c in p["CDP"]:
                if c not in codici:
                    ignoti[c] += 1
            if not cdp or not g:
                continue
            eid = "%s%d" % (t, p["OBJECTID"])
            v = {"t": t, "n": p.get("PROGETTO") or "", "cod": p.get("CODICE_PROG_LIN") or "",
                 "den": p.get("DENOMINAZIONE") or p.get("DESCRIZIONE_TRATTE") or "",
                 "cdp": cdp, "anno": p.get("ANNO_ATT_PC") or "",
                 "compl": p.get("ANNO_COMPLETAMENTO") or "", "pi": p.get("ANNO_ATT_PI") or "",
                 "reg": p.get("REGIONE") or "", "fin": p.get("FINANZIATO") or "",
                 "car": [lbl for k, lbl in CARATTERI if p.get(k) in (1, "1", "SI")]}
            if g["type"] == "Point":
                v["xy"] = [round(c, 1) for c in pr(*g["coordinates"])]
            else:
                linee = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
                v["d"] = [x for x in (path([pr(lon, lat) for lon, lat in l]) for l in linee) if x]
                if not v["d"]:
                    continue
            el[eid] = v
            for c in cdp:
                per_int[c].append(eid)

    # ------------------------------------------ la prova degli agganci dedotti
    # Solo le tratte: una localita' e' un punto, e un punto vicino a una linea
    # non dice che l'intervento sia su quella linea (un nodo ne tocca molte).
    geo = app.get("linee_geo") or {}
    prova = collections.defaultdict(lambda: [0, 0])     # livello -> [concordi, totali]
    dettaglio = {}
    for c, ids in per_int.items():
        pts = []
        for i in ids:
            if el[i]["t"] == "tr":
                for d in el[i]["d"]:
                    pts.extend(punti_da_path(d))
        if not pts:
            continue
        for t in (app.get("linee_intervento") or {}).get(c, []):
            L = geo.get(str(t["id"]))
            if not L:
                continue
            q = quota_vicina(pts, L["d"])
            ok = q >= 0.5
            livello = t["conf"]
            if (app.get("confermati") or {}).get(c, {}).get("osm") == str(t["id"]):
                livello = "confermato"
            prova[livello][0] += ok
            prova[livello][1] += 1
            dettaglio.setdefault(c, []).append({"id": str(t["id"]), "conf": livello,
                                                 "quota": round(q, 2)})
            # l'esito resta sull'aggancio stesso, cosi' la scheda e il
            # pannello della linea possono dire se il tracciato RFI lo conferma
            t["rfi"] = round(q, 2)

    # Una conferma smentita dal tracciato RFI non e' piu' una conferma. Il caso
    # che l'ha resa necessaria: "Potenziamento Palermo-Agrigento-Porto
    # Empedocle" era confermato sulla Catania-Agrigento, perche' registro RFI e
    # OSM condividevano il capo Agrigento; il tracciato dichiarato da RFI va
    # invece verso Lercara, cioe' verso Palermo.
    smentiti = {}
    for c, lista in dettaglio.items():
        cf = (app.get("confermati") or {}).get(c)
        if not cf:
            continue
        esito = next((x for x in lista if x["id"] == str(cf["osm"])), None)
        if esito and esito["quota"] < 0.5:
            smentiti[c] = dict(cf, quota=esito["quota"])
            del app["confermati"][c]

    app["pc"] = {"fonte": pc["fonte"], "servizio": pc["servizio"],
                 "scaricato": pc["scaricato"], "licenza": pc["licenza"],
                 "el": el, "per_int": dict(per_int),
                 "prova": {k: v for k, v in prova.items()}, "smentiti": smentiti,
                 "migliore": [sum(1 for l in dettaglio.values() if l[0]["quota"] >= 0.5),
                              len(dettaglio)]}
    json.dump(app, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))

    ordine = [d["id"] for d in app["documenti"]]
    def costo(p):
        ks = [d for d in ordine if d in p["h"]]
        return (p["h"][ks[-1]][0] or 0) if ks else 0
    tot = sum(costo(p) for p in app["progetti"])
    cop = sum(costo(p) for p in app["progetti"] if p["c"] in per_int)
    cnt = collections.Counter(v["t"] for v in el.values())
    print("piano commerciale: %d elementi agganciati (tratte %d, localita' potenziate %d, nuove %d)"
          % (len(el), cnt["tr"], cnt["lp"], cnt["ln"]))
    print("  interventi con tracciato dichiarato da RFI: %d su %d, %.0f%% del costo"
          % (len(per_int), len(app["progetti"]), 100 * cop / tot if tot else 0))
    if ignoti:
        print("  codici CdP citati da RFI ma assenti nella piattaforma: %s" % dict(ignoti))
    m = app["pc"]["migliore"]
    print("  primo aggancio OSM di ogni intervento concorde col tracciato RFI: %d su %d"
          % (m[0], m[1]))
    if smentiti:
        print("  conferme smentite dal tracciato RFI e tolte: %s" % ", ".join(sorted(smentiti)))
    for k in ("confermato", "alta", "media", "bassa"):
        if k in prova:
            a, n = prova[k]
            print("  prova agganci OSM %-10s %3d concordi su %3d (%.0f%%)" % (k, a, n, 100 * a / n))


if __name__ == "__main__":
    main()
