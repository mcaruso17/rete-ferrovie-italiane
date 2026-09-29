"""Dati del cruscotto delle opere (prototipo), dal file dell'applicazione.

Il cruscotto e' una seconda pagina, piu' leggera della piattaforma: si sceglie
un contratto e si scende nelle opere, ciascuna con costi, avanzamento, tratte
RFI e chilometri. Prende solo quello che serve da cdp-rfi-app.json e lo
incorpora nella pagina, come inject_data.py fa per la piattaforma.

Uso:
  python3 cruscotto_dati.py ../data/cdp-rfi-app.json ../piattaforma/cruscotto.html
"""
import json
import os
import re
import sys


def main():
    app = json.load(open(sys.argv[1], encoding="utf-8"))
    pagina = sys.argv[2]
    rr = app["rete_rfi"]
    pc = app.get("pc", {})
    reg = app["regioni"]

    # nomi degli impianti: stazioni e, per bivi e posti di movimento, "imp"
    nomi = {s[4]: s[2] for s in rr["stazioni"]}
    for k, v in (rr["imp"].items() if isinstance(rr["imp"], dict) else rr["imp"]):
        nomi.setdefault(k, v)

    # tratte RFI dichiarate per intervento: una tratta porta i progetti PC,
    # e un progetto PC porta i codici CdP (aggancio_pc.py)
    per_el = {}
    for ti, els in pc.get("tratte", {}).items():
        for e in els:
            per_el.setdefault(e, []).append(int(ti))
    tratte_int = {}
    for cod, els in pc.get("per_int", {}).items():
        s = set()
        for e in els:
            s.update(per_el.get(e, []))
        if s:
            tratte_int[cod] = sorted(s)

    usate = sorted({t for v in tratte_int.values() for t in v})
    pos = {t: i for i, t in enumerate(usate)}
    TR = []
    for t in usate:
        r = rr["tratte"][t]
        TR.append([r[0], r[1], nomi.get(r[2], r[2]), nomi.get(r[3], r[3]), r[4], r[5],
                   r[6], r[7], r[8], r[9]])

    schede = pc.get("schede", [])
    SCH = [{"t": s.get("t"), "anno": s.get("anno"), "pnrr": s.get("pnrr"),
            "ben": [b["k"] for b in s.get("benefici", []) if b.get("k")],
            "num": s.get("numeri", []), "pag": s.get("pag", [])} for s in schede]

    reg_rfi = app.get("registro_rfi", {})
    lin_dich = pc.get("linee_rfi", {})
    lin_ded = app.get("linee_rfi_intervento", {})
    ATT = app.get("attribuzione_regionale", {})

    OP = []
    for p in app["progetti"]:
        c = p["c"]
        els = [pc["el"][e] for e in pc.get("per_int", {}).get(c, []) if e in pc.get("el", {})]
        anni = sorted({e.get("anno") for e in els if e.get("anno")})
        car = sorted({x for e in els for x in (e.get("car") or [])})
        lin = []
        for x in lin_dich.get(c, []):
            r = reg_rfi.get(x["c"], {})
            lin.append([x["c"], r.get("n", ""), r.get("km"), "dichiarata"])
        for x in lin_ded.get(c, []):
            if any(l[0] == x["c"] for l in lin):
                continue
            r = reg_rfi.get(x["c"], {})
            lin.append([x["c"], r.get("n", ""), r.get("km"), x.get("conf", "")])
        OP.append({
            "c": c, "n": p.get("n") or "", "pg": p.get("pg") or "", "pn": p.get("pn") or "",
            "cl": p.get("cl") or "", "pnrr": bool(p.get("pnrr")),
            "reg": [reg.get(r, r) for r in ATT.get(c, [])],
            "cups": p.get("cups") or ([p["cup"]] if p.get("cup") else []),
            "sa": p.get("sa") or [],
            # per contratto: costo, assegnate, da finanziare, avanzamento, pagina, stato
            "h": {d: [v[0], v[1], v[2], v[3], v[5], v[6]] for d, v in p["h"].items()},
            "ud": p.get("ud"), "pd": p.get("pd"),
            "tr": [pos[t] for t in tratte_int.get(c, [])],
            # geometria dei progetti RFI: serve per le linee nuove, che non
            # stanno su nessuna tratta esistente
            "g": [d for e in els for d in (e.get("d") or [])],
            "anno": anni, "car": car,
            "sch": pc.get("schede_int", {}).get(c, []),
            "lin": lin,
        })

    dati = {
        "documenti": [{"id": d["id"], "titolo": d["titolo"], "anno": d["anno"],
                       "file": d["file"], "avanz_al": d.get("avanz_al")}
                      for d in app["documenti"]],
        "classi": app.get("classi", {}),
        "legenda_stato": app.get("legenda_stato", {}),
        "viewBox": app["mappa"]["viewBox"],
        "regioni": [r["d"] for r in app["mappa"]["regioni"]],
        # le tratte RFI per linea: fondo della mappa e geometria delle tratte
        "linee": {k: v["d"] for k, v in rr["linee"].items()},
        "tratte": TR, "schede": SCH, "opere": OP,
        "pc_pdf": pc.get("pdf"),
    }
    blob = json.dumps(dati, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = open(pagina, encoding="utf-8").read()
    nuovo, n = re.subn(r'(<script type="application/json" id="dati">).*?(</script>)',
                       lambda m: m.group(1) + blob + m.group(2), html, flags=re.S)
    if n != 1:
        sys.exit("blocco dati non trovato in %s" % pagina)
    open(pagina, "w", encoding="utf-8").write(nuovo)
    print("%s: %d opere, %d tratte, %d KB di dati" % (os.path.basename(pagina), len(OP),
                                                      len(TR), len(blob) // 1024))


if __name__ == "__main__":
    main()
