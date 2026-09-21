"""Rilevamento colonne e ricostruzione griglia per le tabelle dei CdP."""
import re
from pdftext import extract_page, group_lines, TextItem

NUM_RE = re.compile(r"^[*^°º\s]*-?\s?\d{1,3}(?:\.\d{3})*,\d{1,2}\s*[*^°]?$")
NUM_LOOSE = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")
INT_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})*$")


# i richiami di nota dei CdP finiscono dentro al numero e non solo ai suoi lati
# ("5.7*79,42"): vanno tolti prima di decidere se una cella e' numerica
MARCATORI = re.compile(r"[*^°º\s]")


def is_num(s):
    s = MARCATORI.sub("", s)
    return bool(NUM_RE.match(s)) or bool(INT_RE.match(s)) or s in ("-", "‐")


def to_float(s):
    if s is None:
        return None
    s = s.strip().replace(" ", " ")
    s = MARCATORI.sub("", s)
    if s in ("", "-", "‐", "–"):
        return None
    neg = s.startswith("-") or s.startswith("(")
    s = s.lstrip("-(").rstrip(")")
    s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def clean(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s


def raw_cells(line, min_gap=2.6):
    """Segmenta una riga in celle su gap orizzontali, senza soglie adattive."""
    cells, cur, prev = [], [], None
    for it in line:
        if prev is not None:
            gap = it.x - (prev.x + prev.w)
            if gap > max(min_gap, 0.30 * prev.h):
                cells.append(cur)
                cur = []
            elif gap > 0.16 * prev.h and cur and cur[-1].text != " ":
                cur.append(TextItem(prev.x + prev.w, prev.y, 0, prev.h, " "))
        cur.append(it)
        prev = it
    if cur:
        cells.append(cur)
    out = []
    for c in cells:
        t = "".join(i.text for i in c).strip()
        if t:
            out.append((c[0].x, c[-1].x + c[-1].w, t, c))
    return out


def find_corridors(datalines, page_x0, page_x1, min_width=2.0):
    """Intervalli x mai coperti da glifi nelle righe dati -> separatori colonna."""
    spans = []
    for line in datalines:
        for it in line:
            if it.text.strip():
                spans.append((it.x, it.x + max(it.w, 0.3)))
    if not spans:
        return []
    spans.sort()
    merged = []
    cs, ce = spans[0]
    for a, b in spans[1:]:
        if a <= ce + 0.05:
            ce = max(ce, b)
        else:
            merged.append((cs, ce))
            cs, ce = a, b
    merged.append((cs, ce))
    gaps = []
    for i in range(len(merged) - 1):
        a, b = merged[i][1], merged[i + 1][0]
        if b - a >= min_width:
            gaps.append((a, b))
    return gaps


def build_columns(datalines, min_width=2.0):
    gaps = find_corridors(datalines, 0, 0, min_width)
    bounds = [(a + b) / 2.0 for a, b in gaps]
    return bounds


def atoms(line, gap=0.9, rel=0.16):
    """Runs di glifi contigui: mai spezzati da un confine di colonna."""
    out, cur, prev = [], [], None
    for it in line:
        if prev is not None and (it.x - (prev.x + prev.w)) > max(gap, rel * prev.h):
            out.append(cur)
            cur = []
        cur.append(it)
        prev = it
    if cur:
        out.append(cur)
    return out


def row_to_grid(line, bounds):
    """Assegna ogni atomo (run di glifi) alla colonna in cui cade il suo centro."""
    n = len(bounds) + 1
    cols = [[] for _ in range(n)]
    for grp in atoms(line):
        cx = (grp[0].x + grp[-1].x + grp[-1].w) / 2.0
        k = 0
        while k < len(bounds) and cx > bounds[k]:
            k += 1
        cols[k].extend(grp)
    out = []
    for c in cols:
        if not c:
            out.append("")
            continue
        c.sort(key=lambda t: t.x)
        s, prev = [], None
        for it in c:
            if prev is not None and it.x - (prev.x + prev.w) > 0.16 * prev.h:
                s.append(" ")
            s.append(it.text)
            prev = it
        out.append(clean("".join(s)))
    return out


def page_grid(doc, page, min_numeric=3, min_width=2.0):
    """Ritorna (colonne_bounds, righe) dove ogni riga e' (y, [celle])."""
    items = extract_page(doc, page)
    lines = group_lines(items)
    datalines, meta = [], []
    for ln in lines:
        cells = raw_cells(ln)
        nnum = sum(1 for _, _, t, _ in cells if is_num(t))
        if nnum >= min_numeric:
            datalines.append(ln)
        meta.append((ln, cells, nnum))
    if not datalines:
        return [], [(ln[0].y, [c[2] for c in cells], False) for ln, cells, _ in meta]
    bounds = build_columns(datalines, min_width)
    rows = []
    for ln, cells, nnum in meta:
        if nnum >= min_numeric:
            rows.append((ln[0].y, row_to_grid(ln, bounds), True))
        else:
            rows.append((ln[0].y, [c[2] for c in cells], False))
    return bounds, rows
