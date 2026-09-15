"""Lettura minimale della tabella cmap di font TrueType/OpenType incorporati.

Serve come fallback quando il CMap ToUnicode del PDF non copre tutti i glifi
(tipico dei font sottoinsiemizzati: legature 'ti', 'fi', ...).
"""
import struct


def _tables(data):
    if len(data) < 12:
        return {}
    tag = data[:4]
    off = 0
    if tag == b"ttcf":
        off = struct.unpack(">I", data[12:16])[0]
    num = struct.unpack(">H", data[off + 4:off + 6])[0]
    out = {}
    for i in range(num):
        p = off + 12 + i * 16
        if p + 16 > len(data):
            break
        t, _cs, o, l = struct.unpack(">4sIII", data[p:p + 16])
        out[t] = (o, l)
    return out


def gid_to_unicode(data):
    """Ritorna {glyphID: carattere} invertendo la cmap del font."""
    try:
        tb = _tables(data)
        if b"cmap" not in tb:
            return {}
        co, _cl = tb[b"cmap"]
        n = struct.unpack(">H", data[co + 2:co + 4])[0]
        best = None
        for i in range(n):
            p = co + 4 + i * 8
            pid, eid, off = struct.unpack(">HHI", data[p:p + 8])
            rank = {(3, 10): 5, (3, 1): 4, (0, 4): 4, (0, 3): 3,
                    (0, 6): 3, (3, 0): 1, (1, 0): 0}.get((pid, eid), 2)
            if best is None or rank > best[0]:
                best = (rank, co + off, pid, eid)
        if best is None:
            return {}
        _r, so, pid, eid = best
        fmt = struct.unpack(">H", data[so:so + 2])[0]
        out = {}
        if fmt == 4:
            segx2 = struct.unpack(">H", data[so + 6:so + 8])[0]
            seg = segx2 // 2
            ends = struct.unpack(">%dH" % seg, data[so + 14:so + 14 + segx2])
            sp = so + 16 + segx2
            starts = struct.unpack(">%dH" % seg, data[sp:sp + segx2])
            dp = sp + segx2
            deltas = struct.unpack(">%dh" % seg, data[dp:dp + segx2])
            rp = dp + segx2
            ranges = struct.unpack(">%dH" % seg, data[rp:rp + segx2])
            for i in range(seg):
                s, e = starts[i], ends[i]
                if s == 0xFFFF:
                    continue
                for c in range(s, min(e, 0xFFFE) + 1):
                    if ranges[i] == 0:
                        g = (c + deltas[i]) & 0xFFFF
                    else:
                        gp = rp + i * 2 + ranges[i] + (c - s) * 2
                        if gp + 2 > len(data):
                            continue
                        g = struct.unpack(">H", data[gp:gp + 2])[0]
                        if g:
                            g = (g + deltas[i]) & 0xFFFF
                    if g and g not in out:
                        out[g] = chr(c)
        elif fmt == 12:
            ngroups = struct.unpack(">I", data[so + 12:so + 16])[0]
            for i in range(min(ngroups, 20000)):
                p = so + 16 + i * 12
                sc, ec, sg = struct.unpack(">III", data[p:p + 12])
                for k in range(min(ec - sc, 4000) + 1):
                    g = sg + k
                    if g not in out:
                        out[g] = chr(sc + k)
        elif fmt == 6:
            first, cnt = struct.unpack(">HH", data[so + 6:so + 10])
            gl = struct.unpack(">%dH" % cnt, data[so + 10:so + 10 + cnt * 2])
            for k, g in enumerate(gl):
                if g and g not in out:
                    out[g] = chr(first + k)
        elif fmt == 0:
            for c in range(256):
                g = data[so + 6 + c]
                if g and g not in out:
                    out[g] = chr(c)
        if pid == 3 and eid == 0:
            fixed = {}
            for g, ch in out.items():
                o = ord(ch)
                if 0xF000 <= o <= 0xF0FF:
                    ch = chr(o - 0xF000)
                fixed[g] = ch
            out = fixed
        return out
    except Exception:
        return {}


def post_names(data):
    """Nomi dei glifi dalla tabella 'post' 2.0, se presente."""
    try:
        tb = _tables(data)
        if b"post" not in tb:
            return {}
        po, pl = tb[b"post"]
        ver = struct.unpack(">I", data[po:po + 4])[0]
        if ver != 0x00020000:
            return {}
        n = struct.unpack(">H", data[po + 32:po + 34])[0]
        idx = struct.unpack(">%dH" % n, data[po + 34:po + 34 + n * 2])
        p = po + 34 + n * 2
        names = []
        end = po + pl
        while p < end and p < len(data):
            ln = data[p]
            names.append(data[p + 1:p + 1 + ln].decode("latin-1"))
            p += 1 + ln
        out = {}
        for g, ix in enumerate(idx):
            if ix >= 258:
                k = ix - 258
                if k < len(names):
                    out[g] = names[k]
        return out
    except Exception:
        return {}
