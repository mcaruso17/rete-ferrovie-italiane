"""Estrazione testo con coordinate dai PDF, sopra pdfmini."""
import re, sys
from pdfmini import PDF, Parser, Stream, Name, Ref
import ttf

STD_ENC_DIFF = {}


def parse_tounicode(data):
    """Legge un CMap ToUnicode -> mappa codice intero -> stringa."""
    m = {}
    txt = data
    for blk in re.findall(rb"beginbfchar(.*?)endbfchar", txt, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            m[int(src, 16)] = hexstr_to_text(dst)
    for blk in re.findall(rb"beginbfrange(.*?)endbfrange", txt, re.S):
        for mm in re.finditer(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(?:<([0-9A-Fa-f]+)>|\[(.*?)\])",
            blk, re.S):
            lo, hi = int(mm.group(1), 16), int(mm.group(2), 16)
            if hi - lo > 65535:
                continue
            if mm.group(3):
                base = mm.group(3)
                bt = hexstr_to_text(base)
                if len(bt) == 1:
                    start = ord(bt)
                    for i in range(hi - lo + 1):
                        m[lo + i] = chr(start + i)
                else:
                    for i in range(hi - lo + 1):
                        m[lo + i] = bt
            else:
                items = re.findall(rb"<([0-9A-Fa-f]+)>", mm.group(4) or b"")
                for i, it in enumerate(items):
                    m[lo + i] = hexstr_to_text(it)
    return m


def hexstr_to_text(h):
    b = bytes.fromhex(h.decode() if isinstance(h, bytes) else h)
    if len(b) % 2:
        b += b"\0"
    try:
        return b.decode("utf-16-be")
    except Exception:
        return ""


WIN_ANSI_EXTRA = {
    0x80: "€", 0x82: "‚", 0x83: "ƒ", 0x84: "„", 0x85: "…",
    0x86: "†", 0x87: "‡", 0x88: "ˆ", 0x89: "‰", 0x8a: "Š",
    0x8b: "‹", 0x8c: "Œ", 0x8e: "Ž", 0x91: "‘", 0x92: "’",
    0x93: "“", 0x94: "”", 0x95: "•", 0x96: "–", 0x97: "—",
    0x98: "˜", 0x99: "™", 0x9a: "š", 0x9b: "›", 0x9c: "œ",
    0x9e: "ž", 0x9f: "Ÿ",
}

GLYPH_RE = re.compile(r"^(?:uni([0-9A-Fa-f]{4})|u([0-9A-Fa-f]{4,6}))$")
GLYPHNAMES = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$",
    "percent": "%", "ampersand": "&", "quotesingle": "'", "parenleft": "(",
    "parenright": ")", "asterisk": "*", "plus": "+", "comma": ",", "hyphen": "-",
    "period": ".", "slash": "/", "zero": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "colon": ":", "semicolon": ";", "less": "<", "equal": "=", "greater": ">",
    "question": "?", "at": "@", "bracketleft": "[", "backslash": "\\",
    "bracketright": "]", "asciicircum": "^", "underscore": "_", "grave": "`",
    "braceleft": "{", "bar": "|", "braceright": "}", "asciitilde": "~",
    "euro": "€", "quoteright": "’", "quoteleft": "‘",
    "quotedblleft": "“", "quotedblright": "”", "endash": "–",
    "emdash": "—", "bullet": "•", "degree": "°",
    "agrave": "à", "egrave": "è", "eacute": "é", "igrave": "ì",
    "ograve": "ò", "ugrave": "ù", "ccedilla": "ç",
    "Agrave": "À", "Egrave": "È", "Eacute": "É",
    "periodcentered": "·", "section": "§", "paragraph": "¶",
    "germandbls": "ß", "ordmasculine": "º", "ordfeminine": "ª",
}


def glyph_to_char(g):
    if g in GLYPHNAMES:
        return GLYPHNAMES[g]
    m = GLYPH_RE.match(g)
    if m:
        h = m.group(1) or m.group(2)
        try:
            return chr(int(h, 16))
        except Exception:
            return ""
    if len(g) == 1:
        return g
    return ""


class Font:
    def __init__(self, doc, fd):
        self.doc = doc
        self.fd = fd or {}
        self.cid = False
        self.tounicode = {}
        self.diff = {}
        self.base_enc = "StandardEncoding"
        self.widths = {}
        self.default_width = 500
        self.cmap_ranges = None
        self._build()

    def _build(self):
        doc, fd = self.doc, self.fd
        sub = fd.get("Subtype")
        tu = doc.d(fd, "ToUnicode")
        if isinstance(tu, Stream):
            try:
                self.tounicode = parse_tounicode(tu.data())
            except Exception:
                self.tounicode = {}
        if sub == "Type0":
            self.cid = True
            enc = fd.get("Encoding")
            if isinstance(enc, Stream):
                self.cmap_ranges = parse_cmap_ranges(enc.data())
            desc = doc.d(fd, "DescendantFonts")
            if isinstance(desc, list) and desc:
                df = doc.resolve(desc[0])
                self.default_width = doc.d(df, "DW", 1000) or 1000
                w = doc.d(df, "W")
                if isinstance(w, list):
                    self.widths = parse_w_array(doc, w)
                self._embedded_fallback(df)
            return
        self._embedded_fallback(fd)
        enc = doc.d(fd, "Encoding")
        if isinstance(enc, Name):
            self.base_enc = str(enc)
        elif isinstance(enc, dict):
            if "BaseEncoding" in enc:
                self.base_enc = str(doc.d(enc, "BaseEncoding"))
            diffs = doc.d(enc, "Differences")
            if isinstance(diffs, list):
                code = 0
                for it in diffs:
                    it = doc.resolve(it)
                    if isinstance(it, (int, float)):
                        code = int(it)
                    elif isinstance(it, str):
                        self.diff[code] = str(it)
                        code += 1
        fc = doc.d(fd, "FirstChar")
        ws = doc.d(fd, "Widths")
        if isinstance(ws, list) and isinstance(fc, int):
            for i, w in enumerate(ws):
                w = doc.resolve(w)
                if isinstance(w, (int, float)):
                    self.widths[fc + i] = w

    def _embedded_fallback(self, fd):
        """Mappa CID/GID -> unicode leggendo il font incorporato."""
        doc = self.doc
        desc = doc.d(fd, "FontDescriptor")
        if not isinstance(desc, dict):
            return
        prog = None
        for k in ("FontFile2", "FontFile3", "FontFile"):
            v = doc.d(desc, k)
            if isinstance(v, Stream):
                prog = v
                break
        if prog is None:
            return
        try:
            data = prog.data()
        except Exception:
            return
        if not data:
            return
        g2u = ttf.gid_to_unicode(data)
        if g2u:
            self.gid2uni = g2u
        names = ttf.post_names(data)
        if names:
            self.gidnames = names
        c2g = doc.d(fd, "CIDToGIDMap")
        if isinstance(c2g, Stream):
            try:
                m = c2g.data()
                self.cid2gid = {i: (m[2 * i] << 8) | m[2 * i + 1]
                                for i in range(len(m) // 2)}
            except Exception:
                pass

    # Legature dei font sottoinsiemizzati dei CdP: il ToUnicode del PDF le omette
    # e il font incorporato non ha ne' cmap ne' nomi glifo, quindi vanno dedotte
    # dal contesto. Verificate su 1241 occorrenze nel corpus (415="ti", 425="tt").
    CORPUS_LIGATURES = {415: "ti", 425: "tt"}

    def _fallback_char(self, code):
        gid = code
        c2g = getattr(self, "cid2gid", None)
        if c2g is not None:
            gid = c2g.get(code, 0)
        g2u = getattr(self, "gid2uni", None)
        if g2u:
            ch = g2u.get(gid)
            if ch:
                return ch
        gn = getattr(self, "gidnames", None)
        if gn:
            nm = gn.get(gid)
            if nm:
                c = glyph_to_char(nm)
                if c:
                    return c
        if self.cid:
            return self.CORPUS_LIGATURES.get(code, "")
        return ""

    def decode(self, s):
        """bytes -> lista di (codice, testo)."""
        out = []
        if self.cid:
            if self.cmap_ranges is not None:
                i = 0
                while i < len(s):
                    matched = False
                    for nb in (1, 2, 3, 4):
                        if i + nb > len(s):
                            break
                        code = int.from_bytes(s[i:i + nb], "big")
                        if self.cmap_ranges.get(nb) and any(
                                lo <= code <= hi for lo, hi in self.cmap_ranges[nb]):
                            out.append((code, self.tounicode.get(code)
                                        or self._fallback_char(code)))
                            i += nb
                            matched = True
                            break
                    if not matched:
                        code = int.from_bytes(s[i:i + 2], "big")
                        out.append((code, self.tounicode.get(code)
                                    or self._fallback_char(code)))
                        i += 2
            else:
                for i in range(0, len(s) - 1, 2):
                    code = (s[i] << 8) | s[i + 1]
                    out.append((code, self.tounicode.get(code)
                                or self._fallback_char(code)))
            return out
        for b in s:
            if self.tounicode.get(b):
                out.append((b, self.tounicode[b]))
            elif b in self.diff:
                out.append((b, glyph_to_char(self.diff[b])))
            elif self.base_enc == "WinAnsiEncoding" and b in WIN_ANSI_EXTRA:
                out.append((b, WIN_ANSI_EXTRA[b]))
            else:
                out.append((b, bytes([b]).decode("latin-1")))
        return out

    def width(self, code):
        w = self.widths.get(code)
        if w is None:
            w = self.default_width
        return w / 1000.0


def parse_cmap_ranges(data):
    r = {}
    for blk in re.findall(rb"begincodespacerange(.*?)endcodespacerange", data, re.S):
        for lo, hi in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            nb = len(lo) // 2
            r.setdefault(nb, []).append((int(lo, 16), int(hi, 16)))
    return r or None


def parse_w_array(doc, w):
    out = {}
    i = 0
    w = [doc.resolve(x) for x in w]
    while i < len(w):
        a = w[i]
        if i + 1 < len(w) and isinstance(w[i + 1], list):
            arr = [doc.resolve(x) for x in w[i + 1]]
            for j, v in enumerate(arr):
                if isinstance(v, (int, float)):
                    out[int(a) + j] = v
            i += 2
        elif i + 2 < len(w):
            b, v = w[i + 1], w[i + 2]
            try:
                if int(b) - int(a) < 70000:
                    for c in range(int(a), int(b) + 1):
                        out[c] = v
            except Exception:
                pass
            i += 3
        else:
            break
    return out


def mat_mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2,
            c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


class TextItem:
    __slots__ = ("x", "y", "w", "h", "text")

    def __init__(self, x, y, w, h, text):
        self.x, self.y, self.w, self.h, self.text = x, y, w, h, text

    def __repr__(self):
        return "T(%.0f,%.0f,%r)" % (self.x, self.y, self.text)


def page_content(doc, page):
    c = doc.d(page, "Contents")
    parts = []
    if isinstance(c, Stream):
        parts.append(c.data())
    elif isinstance(c, list):
        for it in c:
            it = doc.resolve(it)
            if isinstance(it, Stream):
                parts.append(it.data())
    return b"\n".join(parts)


def get_fonts(doc, res, depth=0):
    fonts = {}
    res = doc.resolve(res)
    if not isinstance(res, dict) or depth > 8:
        return fonts
    fd = doc.d(res, "Font")
    if isinstance(fd, dict):
        for k, v in fd.items():
            f = doc.resolve(v)
            if isinstance(f, dict):
                try:
                    fonts[k] = Font(doc, f)
                except Exception:
                    pass
    return fonts


def extract_page(doc, page, include_xobjects=True):
    items = []
    res = doc.d(page, "Resources") or {}
    content = page_content(doc, page)
    _run(doc, content, res, items, (1, 0, 0, 1, 0, 0), 0, include_xobjects)
    rot = doc.d(page, "Rotate") or 0
    mb = doc.d(page, "MediaBox") or [0, 0, 595, 842]
    mb = [float(doc.resolve(v)) for v in mb]
    if rot:
        rot = int(rot) % 360
        x0, y0, x1, y1 = mb
        W, H = x1 - x0, y1 - y0
        for it in items:
            x, y = it.x, it.y
            if rot == 90:
                it.x, it.y = y - y0, W - (x - x0)
            elif rot == 180:
                it.x, it.y = x1 - x, y1 - y
            elif rot == 270:
                it.x, it.y = y1 - y, x - x0
    return items


def _run(doc, content, res, items, base_ctm, depth, include_xobjects):
    if depth > 6:
        return
    fonts = get_fonts(doc, res)
    xobjs = doc.d(res, "XObject") if include_xobjects else None
    p = Parser(content, 0, doc)
    stack = []
    ctm = base_ctm
    ctm_stack = []
    tm = tlm = (1, 0, 0, 1, 0, 0)
    font = None
    fsize = 1.0
    tc = tw = 0.0
    th = 1.0
    trise = 0.0
    tleading = 0.0
    while True:
        try:
            tok = p.token()
        except Exception:
            break
        if tok is None:
            break
        if isinstance(tok, tuple) and tok[0] == "KW" and not re.match(rb"^[+-.\d]", tok[1]):
            op = tok[1]
            args = stack
            try:
                if op == b"q":
                    ctm_stack.append(ctm)
                elif op == b"Q":
                    if ctm_stack:
                        ctm = ctm_stack.pop()
                elif op == b"cm" and len(args) >= 6:
                    ctm = mat_mul(tuple(float(a) for a in args[-6:]), ctm)
                elif op == b"BT":
                    tm = tlm = (1, 0, 0, 1, 0, 0)
                elif op == b"Tf" and len(args) >= 2:
                    font = fonts.get(str(args[-2]))
                    fsize = float(args[-1])
                elif op == b"Td" and len(args) >= 2:
                    tlm = mat_mul((1, 0, 0, 1, float(args[-2]), float(args[-1])), tlm)
                    tm = tlm
                elif op == b"TD" and len(args) >= 2:
                    tleading = -float(args[-1])
                    tlm = mat_mul((1, 0, 0, 1, float(args[-2]), float(args[-1])), tlm)
                    tm = tlm
                elif op == b"Tm" and len(args) >= 6:
                    tm = tlm = tuple(float(a) for a in args[-6:])
                elif op == b"T*":
                    tlm = mat_mul((1, 0, 0, 1, 0, -tleading), tlm)
                    tm = tlm
                elif op == b"TL" and args:
                    tleading = float(args[-1])
                elif op == b"Tc" and args:
                    tc = float(args[-1])
                elif op == b"Tw" and args:
                    tw = float(args[-1])
                elif op == b"Tz" and args:
                    th = float(args[-1]) / 100.0
                elif op == b"Ts" and args:
                    trise = float(args[-1])
                elif op in (b"Tj", b"'", b'"', b"TJ"):
                    if op == b"'":
                        tlm = mat_mul((1, 0, 0, 1, 0, -tleading), tlm)
                        tm = tlm
                    elif op == b'"':
                        if len(args) >= 3:
                            tw, tc = float(args[-3]), float(args[-2])
                        tlm = mat_mul((1, 0, 0, 1, 0, -tleading), tlm)
                        tm = tlm
                    arg = args[-1] if args else None
                    seq = arg if isinstance(arg, list) else [arg]
                    tm = _show(doc, seq, font, fsize, tc, tw, th, trise,
                               tm, ctm, items)
                elif op == b"Do" and args and isinstance(xobjs, dict):
                    xo = doc.d(xobjs, str(args[-1]))
                    if isinstance(xo, Stream) and xo.dict.get("Subtype") == "Form":
                        mtx = doc.resolve(xo.dict.get("Matrix")) or [1, 0, 0, 1, 0, 0]
                        sub = mat_mul(tuple(float(doc.resolve(v)) for v in mtx), ctm)
                        r2 = doc.resolve(xo.dict.get("Resources")) or res
                        _run(doc, xo.data(), r2, items, sub, depth + 1, include_xobjects)
            except Exception:
                pass
            stack = []
        else:
            try:
                stack.append(p.obj(tok))
            except Exception:
                stack.append(None)
            if len(stack) > 32:
                stack = stack[-16:]
    return items


def _show(doc, seq, font, fsize, tc, tw, th, trise, tm, ctm, items):
    if font is None:
        class _F:
            cid = False
            def decode(self, s):
                return [(b, bytes([b]).decode("latin-1")) for b in s]
            def width(self, c):
                return 0.5
        font = _F()
    for el in seq:
        if isinstance(el, (int, float)):
            tm = mat_mul((1, 0, 0, 1, -el / 1000.0 * fsize * th, 0), tm)
            continue
        if not isinstance(el, bytes):
            continue
        for code, ch in font.decode(el):
            w0 = font.width(code)
            trm = mat_mul((fsize * th, 0, 0, fsize, 0, trise), mat_mul(tm, ctm))
            if ch and ch not in ("\x00",):
                scale = (trm[0] ** 2 + trm[1] ** 2) ** 0.5
                if ch == "\xa0":
                    ch = " "
                items.append(TextItem(trm[4], trm[5], w0 * (scale or fsize),
                                      scale or fsize, ch))
            adv = (w0 * fsize + tc + (tw if (code == 32 and not font.cid) else 0)) * th
            tm = mat_mul((1, 0, 0, 1, adv, 0), tm)
    return tm


def group_lines(items, ytol=2.2):
    if not items:
        return []
    items = sorted(items, key=lambda t: (-t.y, t.x))
    lines, cur, cury = [], [], None
    for it in items:
        if cury is None or abs(it.y - cury) <= ytol:
            cur.append(it)
            cury = it.y if cury is None else cury
        else:
            lines.append(sorted(cur, key=lambda t: t.x))
            cur, cury = [it], it.y
    if cur:
        lines.append(sorted(cur, key=lambda t: t.x))
    return lines


def line_cells(line, gap_factor=0.32, min_gap=1.6):
    """Raggruppa i glifi di una riga in celle separate da spazi larghi."""
    cells = []
    cur = []
    prev = None
    for it in line:
        if prev is not None:
            gap = it.x - (prev.x + prev.w)
            thr = max(min_gap, gap_factor * prev.h * 3.0)
            if gap > thr:
                cells.append(cur)
                cur = []
            elif gap > max(0.6, 0.18 * prev.h) and cur and cur[-1].text != " ":
                cur.append(TextItem(prev.x + prev.w, prev.y, 0, prev.h, " "))
        cur.append(it)
        prev = it
    if cur:
        cells.append(cur)
    out = []
    for c in cells:
        txt = "".join(i.text for i in c).strip()
        if txt:
            out.append((c[0].x, c[-1].x + c[-1].w, txt))
    return out


def page_text(doc, page):
    items = extract_page(doc, page)
    out = []
    for line in group_lines(items):
        cells = line_cells(line)
        out.append("\t".join(c[2] for c in cells))
    return "\n".join(out)


if __name__ == "__main__":
    path = sys.argv[1]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else lo + 1
    doc = PDF(path)
    pgs = doc.pages()
    for i in range(lo, min(hi, len(pgs))):
        print("======== PAGE %d ========" % (i + 1))
        print(page_text(doc, pgs[i]))
