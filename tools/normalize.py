"""Costruisce il dataset normalizzato dei Contratti di Programma RFI."""
import sys, os, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tables import to_float
from schema import DOCS, TABELLA_A, ETICHETTE, STATO_ATTUATIVO, PROGRAMMI, CLASSI

RAW = sys.argv[1]
EXTRA = sys.argv[2]
OUT = sys.argv[3]


def valori(r):
    """Valori della riga, integrando quelli scritti sulle righe di continuazione."""
    v = [to_float(x) for x in r["vals"]]
    for c in r["cont"]:
        for i, x in enumerate(c["vals"]):
            if x is not None and i < len(v) and v[i] is None:
                v[i] = to_float(x)
    return v


# le righe di continuazione raccolgono anche le note a margine della pagina:
# la descrizione si ferma al primo marcatore di nota
TAGLIO = re.compile(
    r"\s*(Legenda\b|Nota bene\b|Nota:|Note:|comprende interventi finanziati"
    r"|Stato attuativo:|Classe DPP:|\* ?Le stime|per memoria\b.*$)", re.I)


def descrizione(r):
    parts = [r["descr"]] + [c["descr"] for c in r["cont"] if c["descr"]]
    s = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    s = TAGLIO.split(s)[0].strip(" -;,")
    return s


def pulisci_programma(p):
    if not p:
        return None, None, None
    p = re.sub(r"\s+", " ", p).strip()
    num, nome = PROGRAMMI.get(p, (None, p))
    return num, nome, p


def main():
    docs, progetti, valid = {}, {}, []
    ultimate, tavola2, tavola1 = [], [], []
    for doc_id, meta in sorted(DOCS.items(), key=lambda kv: kv[1]["ordine"]):
        praw = os.path.join(RAW, doc_id + ".json")
        if not os.path.exists(praw):
            continue
        d = json.load(open(praw))
        sch = TABELLA_A.get(doc_id)
        nA = nOK = 0
        for r in d["rows"]:
            if r["kind"] not in ("A", "B"):
                continue
            # la Tabella A ripete gli stessi interventi in due viste: si tiene
            # solo quella per status attuativo, l'altra e' identica al centesimo
            if r["kind"] == "A" and r.get("vista") == "classi":
                continue
            v = valori(r)
            rec = {"doc": doc_id, "pagina": r["page"], "tabella": r["kind"],
                   "codice": r["code"], "cup": r.get("cup"),
                   "descrizione": descrizione(r),
                   "classe_dpp": r.get("dpp"),
                   "paniere_pnrr": bool(r.get("paniere_pnrr")),
                   "stato_attuativo": list(dict.fromkeys(r.get("stato") or [])),
                   "classe": r.get("classe"),
                   "classe_nome": CLASSI.get(r.get("classe") or "",
                                             r.get("classe_nome")),
                   "sottoprogramma": (r.get("sottoprogramma") or "").strip()
                   or None}
            (rec["programma_num"], rec["programma"],
             rec["programma_originale"]) = pulisci_programma(r.get("programma"))
            if sch and r["kind"] == "A" and len(v) == sch["ncols"]:
                for i, name in sch["map"].items():
                    rec[name] = v[i]
                fonti = {k: rec.get(k) for k in sch["fonti"]}
                fab = {k: rec.get(k) for k in sch["fabbisogni"]}
                rec["fonti"] = fonti
                rec["fabbisogni"] = fab
                rec["da_finanziare"] = sum(x for x in fab.values() if x) or 0.0
                rec["fab_breve"] = sum((rec.get(k) or 0) for k in sch["breve"])
                rec["fab_medio"] = sum((rec.get(k) or 0) for k in sch["medio"])
                rec["fab_lungo"] = sum((rec.get(k) or 0) for k in sch["lungo"])
                fin = rec.get("finanziato_totale")
                sf = sum(x for x in fonti.values() if x)
                ok_fonti = fin is not None and abs(fin - sf) < 0.1
                cos = rec.get("costo_totale")
                # l'identita' sul costo non vale per gli interventi la cui
                # stima si ferma all'arco di Piano (nota a margine del documento)
                ok_costo = (cos is not None and fin is not None
                            and abs(cos - (fin + rec["da_finanziare"])) < 0.1)
                rec["_check"] = {"fonti": ok_fonti, "costo": ok_costo}
                nA += 1
                nOK += 1 if ok_fonti else 0
                valid.append((doc_id, r["code"], ok_fonti, ok_costo))
            else:
                rec["vals_grezzi"] = v
            progetti.setdefault(r["code"], []).append(rec)
        docs[doc_id] = dict(meta)
        docs[doc_id]["righe_tabella_a"] = nA
        docs[doc_id]["righe_valide"] = nOK
        docs[doc_id]["colonne"] = (
            [ETICHETTE.get(TABELLA_A[doc_id]["map"][i], TABELLA_A[doc_id]["map"][i])
             for i in sorted(TABELLA_A[doc_id]["map"])] if doc_id in TABELLA_A else [])
        pex = os.path.join(EXTRA, doc_id + ".json")
        if os.path.exists(pex):
            e = json.load(open(pex))
            ultimate.extend(e["opere_ultimate"])
            tavola2.extend(e["tavola2"])
            tavola1.extend(e.get("tavola1", []))

    ordine = {k: v["ordine"] for k, v in DOCS.items()}
    for code in progetti:
        progetti[code].sort(key=lambda r: ordine.get(r["doc"], 99))

    ultimate_cup = set(u["cup"] for u in ultimate if u["cup"])
    out = []
    for code, snaps in sorted(progetti.items()):
        ult = [s for s in snaps if s["tabella"] == "A"]
        last = (ult or snaps)[-1]
        first = (ult or snaps)[0]
        descr = next((s["descrizione"] for s in reversed(snaps)
                      if s["descrizione"]), "")
        prog = next((s["programma"] for s in reversed(snaps) if s["programma"]), None)
        prognum = next((s["programma_num"] for s in reversed(snaps)
                        if s["programma_num"]), None)
        progorig = next((s["programma_originale"] for s in reversed(snaps)
                         if s["programma_originale"]), None)
        sotto = next((s["sottoprogramma"] for s in reversed(snaps)
                      if s.get("sottoprogramma")), None)
        fin = last.get("finanziato_totale")
        cos = last.get("costo_totale")
        daf = last.get("da_finanziare")
        if fin is None or cos is None:
            stato_fin = "non determinato"
        elif cos <= 0.001:
            stato_fin = "per memoria"
        elif daf is not None and daf < 0.005:
            stato_fin = "integralmente finanziato"
        elif fin < 0.005:
            stato_fin = "non finanziato"
        else:
            stato_fin = "parzialmente finanziato"
        out.append({
            "codice": code, "descrizione": descr, "programma": prog,
            "programma_num": prognum, "programma_originale": progorig,
            "sottoprogramma": sotto,
            "classe": last.get("classe"),
            "classe_nome": last.get("classe_nome"),
            "cup": next((s["cup"] for s in reversed(snaps) if s.get("cup")), None),
            "classe_dpp": last.get("classe_dpp"),
            "paniere_pnrr": any(s.get("paniere_pnrr") for s in snaps),
            "stato_attuativo": last.get("stato_attuativo") or [],
            "tabella": last["tabella"],
            "ultimo_doc": last["doc"], "primo_doc": first["doc"],
            "presenza": [s["doc"] for s in snaps],
            "costo_totale": cos, "finanziato": fin, "da_finanziare": daf,
            "avanzamento": last.get("avanzamento"),
            "fonti": last.get("fonti"), "fabbisogni": last.get("fabbisogni"),
            "fab_breve": last.get("fab_breve"), "fab_medio": last.get("fab_medio"),
            "fab_lungo": last.get("fab_lungo"),
            "stato_finanziario": stato_fin,
            "pagina": last["pagina"],
            "storico": [{"doc": s["doc"], "pagina": s["pagina"],
                         "costo": s.get("costo_totale"),
                         "finanziato": s.get("finanziato_totale"),
                         "da_finanziare": s.get("da_finanziare"),
                         "avanzamento": s.get("avanzamento"),
                         "stato": s.get("stato_attuativo") or [],
                         "fonti": s.get("fonti")}
                        for s in snaps],
        })

    nv = sum(1 for _d, _c, a, b in valid if a)
    nc = sum(1 for _d, _c, a, b in valid if b)
    report = {
        "righe_verificate": len(valid), "righe_conformi": nv,
        "percentuale": round(100.0 * nv / max(1, len(valid)), 1),
        "righe_costo_conformi": nc,
        "percentuale_costo": round(100.0 * nc / max(1, len(valid)), 1),
        "per_documento": {d: {"righe": docs[d].get("righe_tabella_a", 0),
                              "conformi": docs[d].get("righe_valide", 0)}
                          for d in docs},
    }
    aggregati = {}
    for doc_id in docs:
        snaps = [s for p in out for s in p["storico"] if s["doc"] == doc_id]
        aggregati[doc_id] = {
            "n_interventi": len(snaps),
            "costo": round(sum(s["costo"] or 0 for s in snaps), 2),
            "finanziato": round(sum(s["finanziato"] or 0 for s in snaps), 2),
            "da_finanziare": round(sum(s["da_finanziare"] or 0 for s in snaps), 2),
            "avanzamento": round(sum(s["avanzamento"] or 0 for s in snaps), 2),
        }
    res = {"documenti": docs, "progetti": out, "opere_ultimate": ultimate,
           "tavola2": tavola2, "tavola1": tavola1, "aggregati": aggregati,
           "validazione": report,
           "stato_attuativo_legenda": STATO_ATTUATIVO,
           "classi": CLASSI,
           "etichette": ETICHETTE}
    json.dump(res, open(OUT, "w"), ensure_ascii=False)
    print("progetti distinti: %d | opere ultimate: %d | righe Tavola 2: %d"
          % (len(out), len(ultimate), len(tavola2)))
    print("finanziato = somma fonti          : %d/%d righe (%.1f%%)"
          % (nv, len(valid), report["percentuale"]))
    print("costo = finanziato + fabbisogni   : %d/%d righe (%.1f%%)"
          % (nc, len(valid), report["percentuale_costo"]))
    for d, s in report["per_documento"].items():
        print("   %-9s %4d righe Tab.A, %4d conformi" % (d, s["righe"], s["conformi"]))
    c = collections.Counter(p["stato_finanziario"] for p in out)
    print("stato finanziario (ultimo documento disponibile):", dict(c))
    for k, a in aggregati.items():
        print("   %-9s %3d interventi  costo %11.2f  finanziato %11.2f  da finanziare %11.2f"
              % (k, a["n_interventi"], a["costo"], a["finanziato"], a["da_finanziare"]))


main()
