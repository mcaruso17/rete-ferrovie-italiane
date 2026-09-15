"""Estrazione strutturata delle tabelle dei Contratti di Programma RFI.

Strategia:
  * le colonne numeriche sono allineate a destra: si individuano raggruppando
    i bordi destri dei numeri su tutte le pagine della stessa tabella;
  * la fascia di testo a sinistra (codice, descrizione, classe DPP, paniere
    PNRR, stato attuativo) si interpreta per pattern, non per posizione,
    perche' le descrizioni lunghe cancellano i corridoi bianchi.
"""
import sys, re, json, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import raw_cells, atoms, is_num, to_float, clean
from schema import PROGRAMMI

CODE = re.compile(r"^[A-Z]{0,2}\d{3,4}[A-Z]{0,3}(_[A-Z0-9]{1,2})?$")
CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
DPP = re.compile(r"^(INV|PR|PF|SF)([+/ ](INV|PR|PF|SF))*$")
STATO = re.compile(r"^(FAP|PFTE|PD|PE|AN|RE|ES|SF|PP|PRV|E|F|O)(\s*\([A-Z]\))?$")
NUMISH = re.compile(r"\d")


def norm(s):
    s = clean(s)
    for a, b in (("‐", "-"), ("‑", "-"), ("–", "-"), ("−", "-")):
        s = s.replace(a, b)
    return s


def head_text(lines, n=6):
    return norm(" ".join("".join(t.text for t in l) for l in lines[:n])).upper()


def table_kind(h):
    hh = h.replace(" ", "").replace("-", "")
    if "TABELLAAPORTAFOGLIO" in hh:
        return "A"
    if "TABELLABINVESTIMENTI" in hh:
        return "B"
    if "TABELLADETTAGLIOOPEREULTIMATE" in hh:
        return "C_DET"
    if "TABELLACOPERE" in hh:
        return "C"
    if "TABELLADCREDI" in hh:
        return "D"
    if "TAVOLA2" in hh:
        return "T2"
    if "TAVOLA1BIS" in hh:
        return "T1BIS"
    if "TAVOLA1" in hh:
        return "T1"
    return None


def geom(doc, pg):
    mb = [float(doc.resolve(v)) for v in (doc.d(pg, "MediaBox") or [0, 0, 595, 842])]
    rot = int(doc.d(pg, "Rotate") or 0) % 360
    w, h = mb[2] - mb[0], mb[3] - mb[1]
    if rot in (90, 270):
        w, h = h, w
    return (round(w), round(h))


def atom_text(grp):
    s, prev = [], None
    for it in grp:
        if prev is not None and it.x - (prev.x + prev.w) > 0.16 * prev.h:
            s.append(" ")
        s.append(it.text)
        prev = it
    return norm("".join(s))


def numeric_atoms(line):
    out = []
    for grp in atoms(line):
        t = atom_text(grp)
        if is_num(t):
            out.append((grp[0].x, grp[-1].x + grp[-1].w, t))
    return out


def cluster_edges(edges, tol=3.0, min_support=6, merge_below=14.0):
    """Raggruppa i bordi destri dei numeri: una colonna per gruppo.

    Le colonne stampate distano almeno ~26pt, quindi due gruppi piu' vicini di
    `merge_below` sono la stessa colonna (numeri seguiti da un asterisco di nota
    spostano il bordo destro di qualche punto).
    """
    edges = sorted(edges)
    if not edges:
        return []
    groups, cur = [], [edges[0]]
    for e in edges[1:]:
        if e - cur[-1] <= tol:
            cur.append(e)
        else:
            groups.append(cur)
            cur = [e]
    groups.append(cur)
    cl = [(sum(g) / len(g), len(g)) for g in groups if len(g) >= min_support]
    out = []
    for c, n in cl:
        if out and c - out[-1][0] < merge_below:
            pc, pn = out[-1]
            out[-1] = ((pc * pn + c * n) / (pn + n), pn + n)
        else:
            out.append((c, n))
    return out


def parse_prefix(line, xlimit):
    """Interpreta la fascia di testo a sinistra dell'area numerica."""
    toks = []
    for grp in atoms(line, gap=1.4, rel=0.22):
        xr = grp[-1].x + grp[-1].w
        if xr > xlimit:
            continue
        t = atom_text(grp)
        if t:
            toks.append((grp[0].x, t))
    res = {"code": None, "cup": None, "dpp": None, "paniere_pnrr": False,
           "stato": [], "descr": []}
    for x, t in toks:
        tc = t.strip()
        if res["code"] is None and CODE.match(tc):
            res["code"] = tc
        elif CUP.match(tc.replace(" ", "")):
            res["cup"] = tc.replace(" ", "")
        elif DPP.match(tc.replace(" ", "")):
            res["dpp"] = tc.replace(" ", "")
        elif tc in ("X", "x") and x > 250:
            res["paniere_pnrr"] = True
        elif STATO.match(tc) and x > 200:
            res["stato"].append(tc)
        else:
            res["descr"].append(tc)
    res["descr"] = norm(" ".join(res["descr"]))
    return res


def col_labels(pagelines, cols, xnum0):
    n = len(cols)
    buckets = [[] for _ in range(n)]
    lefts = [xnum0] + [cols[i - 1][0] for i in range(1, n)]
    for lines, ytop in pagelines:
        for l in lines:
            if l[0].y <= ytop:
                continue
            cs = raw_cells(l)
            if sum(1 for c in cs if is_num(c[2])) >= 3:
                continue
            for x0, x1, txt, _g in cs:
                if not txt or is_num(txt) or len(txt) > 60:
                    continue
                hits = [i for i in range(n)
                        if x1 > lefts[i] - 4 and x0 < cols[i][0] + 6]
                if not hits or len(hits) > 2:
                    continue
                for i in hits:
                    buckets[i].append((-round(l[0].y, 1), x0, txt))
    out = []
    for b in buckets:
        b.sort()
        seen, parts = set(), []
        for _, _, t in b:
            if t.lower() not in seen:
                seen.add(t.lower())
                parts.append(t)
        out.append(norm(" ".join(parts[:12])))
    return out


def vista_page(lines):
    """La Tabella A ripete gli stessi interventi in due viste: per status
    attuativo/finanziario e per classi tipologiche di destinazione. Sommarle
    entrambe raddoppierebbe gli importi."""
    for l in lines[:8]:
        t = norm("".join(x.text for x in l)).lower()
        if "per status attuativo" in t:
            return "status"
        if "per classi tipologiche" in t or "classi pologiche" in t:
            return "classi"
    return None


CLASSE_RE = re.compile(r"^(?:Classe\s+)?([a-eA-E])\s*-\s*(\S.*)$")


def classify_page(lines):
    """La classe (a..e) e' stampata nell'intestazione di pagina."""
    for l in lines[:8]:
        t = norm("".join(x.text for x in l))
        m = CLASSE_RE.match(t)
        if m and len(t) < 90:
            return m.group(1).lower(), norm(m.group(2))
    return None, None


NON_PROGRAMMA = ("TOTALE", "VARIAZIONE", "PORTAFOGLIO", "INVESTIMENTI REALIZZATI",
                 "OPERE ULTIMATE", "DI CUI")


def is_programma(testo):
    """Riconosce la riga di totale che apre un programma dentro la tabella."""
    t = norm(testo)
    if not t or len(t) < 8 or len(t) > 170:
        return False
    if t.upper().startswith(NON_PROGRAMMA):
        return False
    return bool(re.match(r"^[A-Z0-9]", t))


def extract_doc(path, doc_id):
    doc = PDF(path)
    pages = doc.pages()
    cache, groups = {}, {}
    for pi, pg in enumerate(pages):
        try:
            items = extract_page(doc, pg)
        except Exception:
            continue
        if not items:
            continue
        lines = group_lines(items)
        kind = table_kind(head_text(lines))
        if kind is None:
            continue
        cache[pi] = lines
        groups.setdefault((kind, geom(doc, pg)), []).append(pi)

    out_rows, layouts = [], {}
    for (kind, g), pis in groups.items():
        edges, lefts, coderows = [], [], 0
        for pi in pis:
            for l in cache[pi]:
                na = numeric_atoms(l)
                if len(na) < 3:
                    continue
                edges.extend(a[1] for a in na)
                lefts.append(min(a[0] for a in na))
                cs = raw_cells(l)
                if cs and CODE.match(cs[0][2]):
                    coderows += 1
        if not edges:
            continue
        lefts.sort()
        xnum0 = lefts[max(0, len(lefts) // 20)] - 6
        cols = cluster_edges(edges, 3.0, 6, 14.0)
        cols = [c for c in cols if c[0] > xnum0]
        if not cols:
            continue
        pagelines = []
        for pi in pis:
            dl = [l for l in cache[pi] if len(numeric_atoms(l)) >= 3]
            if dl:
                pagelines.append((cache[pi], max(l[0].y for l in dl) + 1))
        labels = col_labels(pagelines, cols, xnum0)
        lk = "%s|%dx%d" % (kind, g[0], g[1])
        layouts[lk] = {"kind": kind, "geom": list(g), "xnum0": round(xnum0, 1),
                       "ncols": len(cols),
                       "edges": [round(c[0], 1) for c in cols],
                       "support": [c[1] for c in cols],
                       "labels": labels,
                       "pages": sorted(p + 1 for p in pis)}
        centers = [c[0] for c in cols]

        def assign(line):
            vals = [None] * len(centers)
            extra = []
            for grp in atoms(line):
                t = atom_text(grp)
                if not is_num(t):
                    continue
                xr = grp[-1].x + grp[-1].w
                if xr <= xnum0:
                    continue
                d = [abs(xr - c) for c in centers]
                k = d.index(min(d))
                if min(d) > 7:
                    extra.append((round(xr, 1), t))
                elif vals[k] is None:
                    vals[k] = t
                else:
                    extra.append((round(xr, 1), t))
            return vals, extra

        vista_corr = None
        prog_corr = None
        sotto_corr = None
        cls_prec = None
        for pi in sorted(pis):
            lines = cache[pi]
            v = vista_page(lines)
            if v:
                vista_corr = v
            cls, cls_nome = classify_page(lines)
            if cls and cls != cls_prec:
                prog_corr = None
                sotto_corr = None
                cls_prec = cls
            ordered = sorted(lines, key=lambda l: -l[0].y)
            cur = None
            for l in ordered:
                pre = parse_prefix(l, xnum0)
                vals, ex = assign(l)
                nv = sum(1 for v in vals if v is not None)
                if pre["code"] and nv >= 3:
                    if cur:
                        out_rows.append(cur)
                    cur = {"doc": doc_id, "page": pi + 1, "kind": kind,
                           "layout": lk, "classe": cls,
                           "classe_nome": cls_nome, "programma": prog_corr,
                           "sottoprogramma": sotto_corr,
                           "vista": vista_corr,
                           "code": pre["code"], "cup": pre["cup"],
                           "cups": [pre["cup"]] if pre["cup"] else [],
                           "descr": pre["descr"], "dpp": pre["dpp"],
                           "paniere_pnrr": pre["paniere_pnrr"],
                           "stato": pre["stato"], "vals": vals,
                           "cont": [], "off": ex}
                elif nv >= 3 and not pre["code"] and is_programma(pre["descr"]):
                    if cur:
                        out_rows.append(cur)
                        cur = None
                    # dentro un programma compaiono anche i totali di
                    # sotto-raggruppamento (le singole direttrici): il
                    # programma di riferimento resta l'ultimo riconosciuto
                    if norm(pre["descr"]) in PROGRAMMI:
                        prog_corr = pre["descr"]
                        sotto_corr = None
                    else:
                        sotto_corr = pre["descr"]
                elif cur is not None:
                    # una riga di continuazione porta al massimo un paio di
                    # valori (tipicamente l'avanzamento): con tre o piu' numeri
                    # siamo gia' sulla riga di totale del programma
                    if nv >= 3:
                        out_rows.append(cur)
                        cur = None
                    elif nv or pre["descr"] or pre["dpp"] or pre["stato"] \
                            or pre["cup"]:
                        cur["cont"].append({"descr": pre["descr"],
                                            "dpp": pre["dpp"],
                                            "stato": pre["stato"],
                                            "vals": vals})
                        # i CUP stanno quasi sempre su righe proprie sotto
                        # l'intervento, e un intervento puo' averne piu' d'uno
                        if pre["cup"] and pre["cup"] not in cur["cups"]:
                            cur["cups"].append(pre["cup"])
                        if pre["dpp"] and not cur["dpp"]:
                            cur["dpp"] = pre["dpp"]
                        if pre["stato"]:
                            cur["stato"] = list(dict.fromkeys(
                                cur["stato"] + pre["stato"]))
                        if len(cur["cont"]) > 8:
                            out_rows.append(cur)
                            cur = None
            if cur:
                out_rows.append(cur)
    return out_rows, layouts


if __name__ == "__main__":
    path, doc_id, out = sys.argv[1], sys.argv[2], sys.argv[3]
    rows, layouts = extract_doc(path, doc_id)
    with open(out, "w") as fh:
        json.dump({"doc": doc_id, "rows": rows, "layouts": layouts},
                  fh, ensure_ascii=False)
    c = collections.Counter(r["layout"] for r in rows)
    print("%-9s righe=%4d | %s" % (doc_id, len(rows),
          "  ".join("%s:%dcol/%drighe" % (k, layouts[k]["ncols"], v)
                    for k, v in sorted(c.items()))))
