"""Compone il file dati della piattaforma a partire dal dataset normalizzato."""
import json, sys, re, collections

src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src))

ORD = {k: v["ordine"] for k, v in d["documenti"].items()}
DOCS = sorted((k for k in d["documenti"] if d["documenti"][k].get("righe_tabella_a")),
              key=lambda k: ORD[k])


def r2(x):
    return None if x is None else round(x, 2)


progetti = []
for p in d["progetti"]:
    if not any(s["doc"] in DOCS for s in p["storico"]):
        continue
    st = {s["doc"]: s for s in p["storico"]}
    progetti.append({
        "c": p["codice"],
        "n": re.sub(r"\s+", " ", p["descrizione"] or "").strip(),
        "pn": p.get("programma_num"), "pg": p.get("programma"),
        "po": p.get("programma_originale"), "sp": p.get("sottoprogramma"),
        "cl": p.get("classe"), "cln": p.get("classe_nome"),
        "cup": p["cup"], "cups": p.get("cups") or [],
        "dpp": p["classe_dpp"],
        "pnrr": p["paniere_pnrr"],
        "sa": p["stato_attuativo"][:2],
        "sf": p["stato_finanziario"],
        "pag": p["pagina"],
        "ud": p["ultimo_doc"],
        "h": {k: [r2(st[k]["costo"]), r2(st[k]["finanziato"]),
                  r2(st[k]["da_finanziare"]), r2(st[k]["avanzamento"]),
                  [r2(v) for v in (st[k]["fonti"] or {}).values()]
                  if st[k].get("fonti") else None]
              for k in st if k in DOCS},
    })

fonti_nomi = {}
for doc in DOCS:
    from schema import TABELLA_A
    fonti_nomi[doc] = TABELLA_A[doc]["fonti"]

ult = []
for u in d["opere_ultimate"]:
    ult.append({"d": u["doc"], "p": u["page"], "cup": u["cup"],
                "npp": u["npp"], "n": u["descr"][:160], "v": r2(u["costo"]),
                "dt": u["data_esercizio"]})

t2 = []
for r in d["tavola2"]:
    if not r["anni"]:
        continue
    t2.append({"d": r["doc"], "p": r["page"], "riga": r["riga"],
               "sez": r["sezione"], "cap": r["capitolo"], "pg": r["pg"],
               "n": r["voce"][:170], "y": r["anni"],
               "v": [r2(x) for x in r["valori"]]})

t1 = []
for r in d["tavola1"]:
    t1.append({"d": r["doc"], "p": r["page"], "vista": r["vista"],
               "n": r["voce"][:120], "v": [r2(x) for x in r["valori"]]})

app = {
    "documenti": [{"id": k, **{x: d["documenti"][k][x] for x in
                               ("titolo", "file", "periodo", "anno", "ordine",
                                "precedente", "avanz_al", "righe_tabella_a")}}
                  for k in DOCS],
    "aggregati": {k: d["aggregati"][k] for k in DOCS},
    "fonti_nomi": fonti_nomi,
    "etichette": d["etichette"],
    "legenda_stato": d["stato_attuativo_legenda"],
    "classi": d.get("classi", {}),
    "validazione": d["validazione"],
    "progetti": progetti,
    "opere_ultimate": ult,
    "tavola2": t2,
    "tavola1": t1,
    "sintesi_ultimate": d.get("sintesi_ultimate", []),
}
json.dump(app, open(out, "w"), ensure_ascii=False, separators=(",", ":"))
print("progetti=%d  opere_ultimate=%d  tavola2=%d  tavola1=%d"
      % (len(progetti), len(ult), len(t2), len(t1)))
import os
print("dimensione: %.0f KB" % (os.path.getsize(out) / 1024))
