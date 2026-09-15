"""Estrattore PDF minimale in Python puro (solo stdlib).

Serve perche' in questo ambiente non e' possibile installare pdfplumber/pymupdf.
Supporta: xref stream, object stream (ObjStm), FlateDecode, testo con coordinate.
"""
import re, zlib, sys


class Name(str):
    __slots__ = ()


class Ref:
    __slots__ = ("num", "gen")

    def __init__(self, num, gen=0):
        self.num, self.gen = num, gen

    def __repr__(self):
        return "Ref(%d)" % self.num

    def __eq__(self, o):
        return isinstance(o, Ref) and o.num == self.num

    def __hash__(self):
        return hash(("R", self.num))


class Stream:
    __slots__ = ("dict", "raw", "_data")

    def __init__(self, d, raw):
        self.dict, self.raw, self._data = d, raw, None

    def data(self):
        if self._data is None:
            self._data = decode_stream(self.dict, self.raw)
        return self._data


WS = b"\x00\t\n\x0c\r "
DELIM = b"()<>[]{}/%"


def decode_stream(d, raw):
    filt = d.get("Filter")
    if filt is None:
        return raw
    if not isinstance(filt, list):
        filt = [filt]
    parms = d.get("DecodeParms") or d.get("DP")
    if not isinstance(parms, list):
        parms = [parms] * len(filt)
    out = raw
    for f, p in zip(filt, parms):
        if f in ("FlateDecode", "Fl"):
            try:
                out = zlib.decompress(out)
            except zlib.error:
                dec = zlib.decompressobj()
                try:
                    out = dec.decompress(out)
                except zlib.error:
                    return b""
            if isinstance(p, dict) and p.get("Predictor", 1) > 1:
                out = apply_predictor(out, p)
        elif f in ("ASCIIHexDecode", "AHx"):
            h = re.sub(rb"[^0-9A-Fa-f]", b"", out.split(b">")[0])
            if len(h) % 2:
                h += b"0"
            out = bytes.fromhex(h.decode())
        elif f in ("ASCII85Decode", "A85"):
            import base64
            s = out.strip()
            if s.startswith(b"<~"):
                s = s[2:]
            if s.endswith(b"~>"):
                s = s[:-2]
            out = base64.a85decode(s)
        elif f in ("LZWDecode", "LZW"):
            out = lzw_decode(out)
            if isinstance(p, dict) and p.get("Predictor", 1) > 1:
                out = apply_predictor(out, p)
        else:
            # DCTDecode/JPXDecode/CCITT: immagini, non servono al testo
            return b""
    return out


def lzw_decode(data):
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    bitpos, codelen, prev = 0, 9, None
    nbits = len(data) * 8
    while bitpos + codelen <= nbits:
        byte = bitpos // 8
        chunk = int.from_bytes(data[byte:byte + 3].ljust(3, b"\0"), "big")
        code = (chunk >> (24 - codelen - (bitpos % 8))) & ((1 << codelen) - 1)
        bitpos += codelen
        if code == 256:
            table = [bytes([i]) for i in range(256)] + [b"", b""]
            codelen, prev = 9, None
            continue
        if code == 257:
            break
        if prev is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        else:
            entry = prev + prev[:1]
            table.append(entry)
        out += entry
        prev = entry
        if len(table) + 1 >= (1 << codelen) and codelen < 12:
            codelen += 1
    return bytes(out)


def apply_predictor(data, parms):
    pred = parms.get("Predictor", 1)
    if pred < 2:
        return data
    colors = parms.get("Colors", 1)
    bpc = parms.get("BitsPerComponent", 8)
    columns = parms.get("Columns", 1)
    bpp = max(1, (colors * bpc + 7) // 8)
    rowlen = (columns * colors * bpc + 7) // 8
    if pred == 2:
        return data
    out = bytearray()
    prev = bytearray(rowlen)
    i = 0
    while i + 1 <= len(data):
        ft = data[i]
        i += 1
        row = bytearray(data[i:i + rowlen])
        if len(row) < rowlen:
            row += bytearray(rowlen - len(row))
        i += rowlen
        if ft == 1:
            for j in range(bpp, rowlen):
                row[j] = (row[j] + row[j - bpp]) & 0xFF
        elif ft == 2:
            for j in range(rowlen):
                row[j] = (row[j] + prev[j]) & 0xFF
        elif ft == 3:
            for j in range(rowlen):
                left = row[j - bpp] if j >= bpp else 0
                row[j] = (row[j] + ((left + prev[j]) >> 1)) & 0xFF
        elif ft == 4:
            for j in range(rowlen):
                a = row[j - bpp] if j >= bpp else 0
                b = prev[j]
                c = prev[j - bpp] if j >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[j] = (row[j] + pr) & 0xFF
        out += row
        prev = row
    return bytes(out)


class Lexer:
    def __init__(self, buf, pos=0):
        self.buf, self.pos = buf, pos

    def skip_ws(self):
        b, n = self.buf, len(self.buf)
        while self.pos < n:
            c = b[self.pos]
            if c in WS:
                self.pos += 1
            elif c == 0x25:  # %
                while self.pos < n and b[self.pos] not in b"\r\n":
                    self.pos += 1
            else:
                return

    def token(self):
        self.skip_ws()
        b, n = self.buf, len(self.buf)
        if self.pos >= n:
            return None
        c = b[self.pos]
        if c == 0x2F:  # /
            start = self.pos + 1
            self.pos += 1
            while self.pos < n and b[self.pos] not in WS and b[self.pos] not in DELIM:
                self.pos += 1
            raw = b[start:self.pos]
            if b"#" in raw:
                raw = re.sub(rb"#([0-9A-Fa-f]{2})",
                             lambda m: bytes([int(m.group(1), 16)]), raw)
            return Name(raw.decode("latin-1"))
        if c == 0x28:  # (
            return self.read_lit_string()
        if c == 0x3C:  # <
            if self.pos + 1 < n and b[self.pos + 1] == 0x3C:
                self.pos += 2
                return "<<"
            return self.read_hex_string()
        if c == 0x3E and self.pos + 1 < n and b[self.pos + 1] == 0x3E:
            self.pos += 2
            return ">>"
        if c == 0x5B:
            self.pos += 1
            return "["
        if c == 0x5D:
            self.pos += 1
            return "]"
        if c in b"{}":
            self.pos += 1
            return chr(c)
        start = self.pos
        while self.pos < n and b[self.pos] not in WS and b[self.pos] not in DELIM:
            self.pos += 1
        if self.pos == start:
            self.pos += 1
        return ("KW", b[start:self.pos])

    def read_lit_string(self):
        b, n = self.buf, len(self.buf)
        self.pos += 1
        depth, out = 1, bytearray()
        while self.pos < n:
            c = b[self.pos]
            if c == 0x5C:  # backslash
                self.pos += 1
                if self.pos >= n:
                    break
                e = b[self.pos]
                mp = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
                if e in mp:
                    out.append(mp[e])
                    self.pos += 1
                elif 0x30 <= e <= 0x37:
                    oct_ = 0
                    for _ in range(3):
                        if self.pos < n and 0x30 <= b[self.pos] <= 0x37:
                            oct_ = oct_ * 8 + (b[self.pos] - 0x30)
                            self.pos += 1
                        else:
                            break
                    out.append(oct_ & 0xFF)
                elif e in b"\r\n":
                    self.pos += 1
                    if self.pos < n and b[self.pos] in b"\n" and e == 13:
                        self.pos += 1
                else:
                    out.append(e)
                    self.pos += 1
            elif c == 0x28:
                depth += 1
                out.append(c)
                self.pos += 1
            elif c == 0x29:
                depth -= 1
                self.pos += 1
                if depth == 0:
                    break
                out.append(c)
            else:
                out.append(c)
                self.pos += 1
        return ("STR", bytes(out))

    def read_hex_string(self):
        b, n = self.buf, len(self.buf)
        self.pos += 1
        out = bytearray()
        digits = []
        while self.pos < n and b[self.pos] != 0x3E:
            c = b[self.pos]
            if chr(c) in "0123456789abcdefABCDEF":
                digits.append(chr(c))
            self.pos += 1
        self.pos += 1
        if len(digits) % 2:
            digits.append("0")
        for i in range(0, len(digits), 2):
            out.append(int(digits[i] + digits[i + 1], 16))
        return ("STR", bytes(out))


NUMRE = re.compile(rb"^[+-]?(\d+\.?\d*|\.\d+)$")


class Parser(Lexer):
    def __init__(self, buf, pos=0, doc=None):
        super().__init__(buf, pos)
        self.doc = doc

    def obj(self, tok=None):
        if tok is None:
            tok = self.token()
        if tok is None:
            return None
        if tok == "<<":
            d = {}
            while True:
                k = self.token()
                if k is None or k == ">>":
                    break
                if not isinstance(k, Name):
                    continue
                d[str(k)] = self.obj()
            save = self.pos
            nx = self.token()
            if isinstance(nx, tuple) and nx[0] == "KW" and nx[1] == b"stream":
                b = self.buf
                if b[self.pos:self.pos + 2] == b"\r\n":
                    self.pos += 2
                elif self.pos < len(b) and b[self.pos] in b"\n\r":
                    self.pos += 1
                ln = d.get("Length")
                if isinstance(ln, Ref) and self.doc is not None:
                    ln = self.doc.resolve(ln)
                start = self.pos
                if isinstance(ln, int) and ln >= 0 and start + ln <= len(b):
                    raw = b[start:start + ln]
                    tail = b[start + ln:start + ln + 20]
                    if b"endstream" not in tail:
                        e = b.find(b"endstream", start)
                        raw = b[start:e] if e > 0 else raw
                    else:
                        self.pos = start + ln
                else:
                    e = b.find(b"endstream", start)
                    raw = b[start:e] if e > 0 else b[start:]
                    self.pos = e if e > 0 else len(b)
                e2 = b.find(b"endstream", self.pos)
                self.pos = (e2 + 9) if e2 > 0 else len(b)
                if raw.endswith(b"\r\n"):
                    pass
                return Stream(d, raw)
            self.pos = save
            return d
        if tok == "[":
            arr = []
            while True:
                t = self.token()
                if t is None or t == "]":
                    break
                arr.append(self.obj(t))
            return arr
        if isinstance(tok, Name):
            return tok
        if isinstance(tok, tuple):
            kind, val = tok
            if kind == "STR":
                return val
            if NUMRE.match(val):
                save = self.pos
                t2 = self.token()
                if isinstance(t2, tuple) and t2[0] == "KW" and NUMRE.match(t2[1]) and b"." not in val:
                    t3 = self.token()
                    if isinstance(t3, tuple) and t3[0] == "KW" and t3[1] == b"R":
                        return Ref(int(val), int(t2[1]))
                self.pos = save
                if b"." in val:
                    return float(val)
                return int(val)
            if val == b"true":
                return True
            if val == b"false":
                return False
            if val == b"null":
                return None
            return ("KW", val)
        return tok


class PDF:
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.buf = fh.read()
        self.objs = {}
        self.cache = {}
        self.trailer = {}
        self._scan()
        self._load_objstms()
        self._find_root()

    def _scan(self):
        for m in re.finditer(rb"(?<![0-9])(\d{1,7})\s+(\d{1,5})\s+obj\b", self.buf):
            self.objs[int(m.group(1))] = ("file", m.end())
        for m in re.finditer(rb"trailer", self.buf):
            p = Parser(self.buf, m.end(), self)
            t = p.obj()
            if isinstance(t, dict):
                for k, v in t.items():
                    self.trailer.setdefault(k, v)

    def _load_objstms(self):
        self.instm = {}
        for num in list(self.objs):
            try:
                o = self.get(num)
            except Exception:
                continue
            if isinstance(o, Stream) and o.dict.get("Type") == "ObjStm":
                try:
                    data = o.data()
                    n = self.resolve(o.dict.get("N", 0))
                    first = self.resolve(o.dict.get("First", 0))
                    hp = Parser(data[:first], 0, self)
                    pairs = []
                    for _ in range(n):
                        a = hp.obj()
                        b = hp.obj()
                        if a is None or b is None:
                            break
                        pairs.append((a, b))
                    for onum, off in pairs:
                        if onum not in self.objs:
                            self.instm[onum] = (data, first + off)
                except Exception:
                    continue

    def _find_root(self):
        root = self.trailer.get("Root")
        if root is None:
            for m in re.finditer(rb"/Type\s*/XRef", self.buf):
                s = self.buf.rfind(b"obj", 0, m.start())
                if s < 0:
                    continue
                p = Parser(self.buf, s + 3, self)
                d = p.obj()
                dd = d.dict if isinstance(d, Stream) else d
                if isinstance(dd, dict) and "Root" in dd:
                    root = dd["Root"]
                    for k, v in dd.items():
                        self.trailer.setdefault(k, v)
                    break
        if root is None:
            for num in list(self.objs) + list(getattr(self, "instm", {})):
                o = self.get(num)
                if isinstance(o, dict) and o.get("Type") == "Catalog":
                    root = Ref(num)
                    break
        self.root = self.resolve(root) if root is not None else None

    def get(self, num):
        if num in self.cache:
            return self.cache[num]
        self.cache[num] = None
        val = None
        if num in self.objs:
            _, pos = self.objs[num]
            val = Parser(self.buf, pos, self).obj()
        elif num in getattr(self, "instm", {}):
            data, off = self.instm[num]
            val = Parser(data, off, self).obj()
        self.cache[num] = val
        return val

    def resolve(self, o, depth=0):
        while isinstance(o, Ref) and depth < 32:
            o = self.get(o.num)
            depth += 1
        return o

    def d(self, dic, key, default=None):
        if not isinstance(dic, dict):
            return default
        v = dic.get(key, default)
        return self.resolve(v)

    def pages(self):
        out = []
        seen = set()

        def walk(node, inherited, depth=0):
            node = self.resolve(node)
            if not isinstance(node, dict) or depth > 64:
                return
            inh = dict(inherited)
            for k in ("Resources", "MediaBox", "CropBox", "Rotate"):
                if k in node:
                    inh[k] = node[k]
            t = node.get("Type")
            kids = self.d(node, "Kids")
            if t == "Page" or (kids is None and "Contents" in node):
                merged = dict(inh)
                merged.update(node)
                out.append(merged)
                return
            if isinstance(kids, list):
                for kid in kids:
                    key = kid.num if isinstance(kid, Ref) else id(kid)
                    if key in seen:
                        continue
                    seen.add(key)
                    walk(kid, inh, depth + 1)

        cat = self.root
        if isinstance(cat, dict):
            walk(cat.get("Pages"), {})
        if not out:
            for num in sorted(set(list(self.objs) + list(getattr(self, "instm", {})))):
                o = self.get(num)
                if isinstance(o, dict) and o.get("Type") == "Page":
                    out.append(o)
        return out
