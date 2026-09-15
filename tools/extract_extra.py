"""Estrazione di Tabella C (opere ultimate) e Tavola 2 (fonti di cassa).

La Tavola 2 e' l'unico punto dei Contratti in cui compaiono i capitoli di
bilancio e i piani gestionali: sono importi di CASSA per anno, aggregati,
non riconducibili al singolo intervento.
"""
import sys, re, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import raw_cells, is_num, to_float, clean
from extract import (table_kind, head_text, norm, atoms, atom_text,
                     cluster_edges, numeric_atoms)

CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{10,12}$")
DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
T2ROW = re.compile(r"^(\d{1,3})(-\d{1,3})?$")
PG = re.compile(r"^Pg\s?\.?\s?(\d{1,3})$", re.I)
CAP = re.compile(r"^\d{4}$")


def opere_ultimate(doc, pages, doc_id):
    out = []
    for pi in pages:
        lines = group_lines(extract_page(doc, pages[pi]))
        for l in lines:
            cs = raw_cells(l)
            if len(cs) < 4:
                continue
            txt = [c[2] for c in cs]
            dt = next((t for t in txt if DATE.match(t)), None)
            cup = next((t for t in txt if CUP.match(t.replace(" ", ""))), None)
            nums = [(c[0], c[2]) for c in cs if is_num(c[2])]
            if dt is None or not nums:
                continue
            costo = to_float(nums[-1][1])
            descr = max((t for t in txt
                         if not is_num(t) and not DATE.match(t)
                         and not CUP.match(t.replace(" ", ""))),
                        key=len, default="")
            riga = txt[0] if txt and len(txt[0]) <= 6 else None
            npp = next((t for t in txt[1:4]
                        if re.match(r"^[A-Z]?\d{3,4}$", t)), None)
            out.append({"doc": doc_id, "page": pi + 1, "riga": riga,
                        "cup": cup, "npp": npp, "descr": norm(descr),
                        "costo": costo, "data_esercizio": dt})
    return out


def tavola2(doc, pages, doc_id):
    """Righe della Tavola 2: impieghi e fonti di cassa per anno."""
    out = []
    for pi in sorted(pages):
        lines = group_lines(extract_page(doc, pages[pi]))
        anni, bande = [], []
        for l in lines[:16]:
            cs = raw_cells(l)
            yy = [((c[0] + c[1]) / 2.0, c[2]) for c in cs
                  if re.match(r"^20\d{2}$", c[2])]
            if len(yy) >= 3:
                yy.sort()
                anni = [int(y[1]) for y in yy]
                cx = [y[0] for y in yy]
                step = (cx[-1] - cx[0]) / max(1, len(cx) - 1)
                bande = [(c - step * 0.62, c + step * 0.62) for c in cx]
                break
        sezione = None
        for l in lines:
            cs = raw_cells(l)
            if not cs:
                continue
            t0 = cs[0][2].strip()
            joined = " ".join(c[2] for c in cs).upper()
            if "IMPIEGHI DI CASSA" in joined:
                sezione = "impieghi"
            elif re.search(r"\bFONTI\b", joined) and len(cs) <= 9:
                sezione = "fonti"
            if not T2ROW.match(t0):
                continue
            # i numeri delle righe aggregate sono composti con spaziature
            # irregolari ("1 3.054"): si ricompongono per banda d'anno
            pezzi = [[] for _ in bande]
            labels = []
            for grp in atoms(l, gap=1.4, rel=0.22):
                tx = atom_text(grp)
                if not tx or tx == t0:
                    continue
                cx = (grp[0].x + grp[-1].x + grp[-1].w) / 2.0
                k = next((i for i, (a, b) in enumerate(bande) if a <= cx <= b), None)
                if k is not None and re.match(r"^[-\u2010\u2013.,\d ]+$", tx):
                    pezzi[k].append((grp[0].x, tx))
                elif not is_num(tx):
                    labels.append((grp[0].x, tx))
            nums = []
            for p in pezzi:
                p.sort()
                s = "".join(t for _x, t in p).replace(" ", "")
                nums.append(to_float(s) if s else None)
            if not any(v is not None for v in nums):
                continue
            cap = pgm = None
            desc = []
            for x, tx in labels:
                s = tx.strip()
                if cap is None and CAP.match(s) and x < 120:
                    cap = s
                elif pgm is None and PG.match(s.replace(" ", "")):
                    pgm = "PG" + PG.match(s.replace(" ", "")).group(1)
                else:
                    desc.append(s)
            out.append({"doc": doc_id, "page": pi + 1, "riga": t0,
                        "sezione": sezione, "capitolo": cap, "pg": pgm,
                        "voce": norm(" ".join(desc)),
                        "anni": anni, "valori": nums})
    return out


def tavola1(doc, pages, doc_id, vista):
    """Totali ufficiali per classe / programma (Tavola 1 e 1bis)."""
    lines_all = {pi: group_lines(extract_page(doc, pages[pi])) for pi in pages}
    edges = []
    for lines in lines_all.values():
        for l in lines:
            na = numeric_atoms(l)
            if len(na) >= 3:
                edges.extend(a[1] for a in na)
    if not edges:
        return []
    cols = cluster_edges(edges, 3.0, 3, 14.0)
    centers = [c[0] for c in cols]
    xnum0 = min(centers) - 40
    out = []
    for pi, lines in sorted(lines_all.items()):
        for l in lines:
            vals = [None] * len(centers)
            etichetta = []
            for grp in atoms(l):
                t = atom_text(grp)
                if not t:
                    continue
                xr = grp[-1].x + grp[-1].w
                if is_num(t) and xr > xnum0:
                    dd = [abs(xr - c) for c in centers]
                    k = dd.index(min(dd))
                    if min(dd) <= 7 and vals[k] is None:
                        vals[k] = to_float(t)
                elif grp[0].x < xnum0:
                    etichetta.append(t)
            if sum(1 for v in vals if v is not None) < 3:
                continue
            lab = norm(" ".join(etichetta))
            if not lab:
                continue
            out.append({"doc": doc_id, "page": pi + 1, "vista": vista,
                        "voce": lab, "valori": vals,
                        "colonne": [round(c, 1) for c in centers]})
    return out


def run(path, doc_id):
    doc = PDF(path)
    pgs = doc.pages()
    byk = {}
    for pi, pg in enumerate(pgs):
        try:
            lines = group_lines(extract_page(doc, pg))
        except Exception:
            continue
        k = table_kind(head_text(lines))
        if k:
            byk.setdefault(k, {})[pi] = pg
    res = {"opere_ultimate": [], "tavola2": [], "tavola1": []}
    if "C_DET" in byk:
        res["opere_ultimate"] = opere_ultimate(doc, byk["C_DET"], doc_id)
    if "T2" in byk:
        res["tavola2"] = tavola2(doc, byk["T2"], doc_id)
    res["tavola1"] = []
    if "T1" in byk:
        res["tavola1"] += tavola1(doc, byk["T1"], doc_id, "status")
    if "T1BIS" in byk:
        res["tavola1"] += tavola1(doc, byk["T1BIS"], doc_id, "classi")
    return res


if __name__ == "__main__":
    path, doc_id, out = sys.argv[1], sys.argv[2], sys.argv[3]
    r = run(path, doc_id)
    json.dump(r, open(out, "w"), ensure_ascii=False)
    print("%-9s opere_ultimate=%4d  Tavola2=%3d (capitoli/pg=%2d)  Tavola1=%2d"
          % (doc_id, len(r["opere_ultimate"]), len(r["tavola2"]),
             sum(1 for x in r["tavola2"] if x["capitolo"] or x["pg"]),
             len(r["tavola1"])))
