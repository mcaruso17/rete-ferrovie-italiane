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
# il contratto 2017-2021 alterna due formati nella stessa colonna:
# 31/12/2016 con le barre e 30.11.2014 con i punti
DATE = re.compile(r"^\d{2}[/.]\d{2}[/.]\d{4}$")
T2ROW = re.compile(r"^(\d{1,3})(-\d{1,3})?$")
PG = re.compile(r"^Pg\s?\.?\s?(\d{1,3})$", re.I)
CAP = re.compile(r"^\d{4}$")


# le categorie cambiano sigla fra i cicli contrattuali: A00/A02/A03/04 nel
# 2017-2021, E.1-E.5 nel 2022-2026, piu' la riga della rete AV/AC
CATEG = re.compile(r"^(E\.\d|A\d{2}(/\d{2})?|A5000_\d|TOTALE)$", re.I)
PEZZO = re.compile(r"^[-\u2010\u2013.,\d ]+$")


def sintesi_ultimate(doc, pages, doc_id):
    """Prospetto di sintesi della Tabella C: totali cumulati per categoria.

    Sta sulla prima pagina del dettaglio, sopra l'elenco delle singole opere,
    e non ha la colonna della data: e' l'unico punto in cui compare il totale
    complessivo delle opere concluse, non solo quelle dell'ultimo anno.
    """
    out = []
    for pi in sorted(pages):
        lines = group_lines(extract_page(doc, pages[pi]))
        # gli anni compaiono anche nel titolo della pagina: si prendono
        # dalla riga d'intestazione delle colonne, in ordine crescente
        anni = []
        for l in lines[:12]:
            t = norm(" ".join(c[2] for c in raw_cells(l)))
            trovati = re.findall(r"31\.12\.(\d{4})", t)
            if len(trovati) >= 2:
                anni = sorted(set(trovati))
                break
        for l in lines:
            cs = raw_cells(l)
            if not cs:
                continue
            testa = cs[0][2].strip()
            etichetta = testa if CATEG.match(testa) else None
            if etichetta is None and len(cs) > 1 and CATEG.match(cs[1][2].strip()):
                etichetta = cs[1][2].strip()
            if etichetta is None:
                continue
            # le righe del dettaglio portano data e CUP: non sono di sintesi.
            # Nel contratto 2017-2021 le sigle di categoria (A00, A03/04)
            # aprono anche le righe di dettaglio, quindi il titolo da solo
            # non basta a distinguerle
            if any(DATE.match(c[2]) for c in cs):
                continue
            if any(CUP.match(c[2].replace(" ", "")) for c in cs):
                continue
            # gli importi sono composti a pezzi ("1" + ".247,52"): i pezzi
            # della stessa colonna distano pochi punti, le colonne circa otto
            pezzi = [(g[0].x, g[-1].x + g[-1].w, atom_text(g))
                     for g in atoms(l, gap=1.4, rel=0.22)]
            pezzi = [p for p in pezzi if p[2] and PEZZO.match(p[2])]
            colonne, cur = [], []
            for x0, x1, tx in pezzi:
                if cur and x0 - cur[-1][1] > 6:
                    colonne.append(cur)
                    cur = []
                cur.append((x0, x1, tx))
            if cur:
                colonne.append(cur)
            valori = []
            for c in colonne:
                v = to_float("".join(t for _a, _b, t in c).replace(" ", ""))
                if v is not None:
                    valori.append(v)
            # il prospetto ha due colonne di stock piu' la variazione, e la
            # variazione e' la differenza fra le due: e' il controllo che
            # distingue una riga di sintesi da una riga di dettaglio in cui
            # la data e' finita fra i numeri
            if not 2 <= len(valori) <= 3:
                continue
            if len(valori) == 3 and abs(valori[2] - (valori[1] - valori[0])) > 0.05:
                continue
            descr = " ".join(c[2] for c in cs
                             if c[2].strip() != etichetta and not PEZZO.match(c[2]))
            if etichetta.upper() == "TOTALE":
                descr = ""
            elif not descr.strip():
                # nel contratto 2017-2021 la descrizione va a capo sopra la
                # riga dei numeri: si recupera dalla riga di solo testo vicina
                idx = lines.index(l)
                for j in (idx - 1, idx + 1):
                    if not 0 <= j < len(lines):
                        continue
                    vicina = raw_cells(lines[j])
                    if vicina and not any(PEZZO.match(c[2]) for c in vicina):
                        t = " ".join(c[2] for c in vicina)
                        if 8 < len(t) < 90:
                            descr = t
                            break
            out.append({"doc": doc_id, "page": pi + 1,
                        "categoria": etichetta, "voce": norm(descr),
                        "anni": anni, "valori": valori})
    return out


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
            npp = next((t for t in txt[1:4]
                        if re.match(r"^[A-Z]?\d{3,4}$", t)), None)
            # non si usa is_num: nelle pagine di prosecuzione gli importi
            # negativi sono scritti con il segno staccato dalla cifra
            # ("-        0,02"), che il riconoscitore stretto scarterebbe
            nums = [(c[0], to_float(c[2])) for c in cs
                    if not DATE.match(c[2]) and to_float(c[2]) is not None]
            # alcune opere non hanno una data di messa in esercizio: la colonna
            # riporta "n.a." e la riga va tenuta lo stesso. Per distinguerla da
            # una riga di sintesi basta il CUP o il codice NPP, che il prospetto
            # per categoria non ha
            if not nums or not (cup or npp):
                continue
            costo = nums[-1][1]
            descr = max((t for t in txt
                         if not is_num(t) and not DATE.match(t)
                         and not CUP.match(t.replace(" ", ""))),
                        key=len, default="")
            riga = txt[0] if txt and len(txt[0]) <= 6 else None
            out.append({"doc": doc_id, "page": pi + 1, "riga": riga,
                        "cup": cup, "npp": npp, "descr": norm(descr),
                        "costo": costo,
                        "data_esercizio": dt.replace(".", "/") if dt else None})
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
            visto_riga = False
            for grp in atoms(l, gap=1.4, rel=0.22):
                tx = atom_text(grp)
                if not tx:
                    continue
                # il numero di riga si scarta una volta sola: lo stesso numero
                # puo' ricomparire come importo in una colonna d'anno (la riga
                # 15 del CdP 2022 vale 15 mln nel 2023)
                if tx == t0 and not visto_riga:
                    visto_riga = True
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
                # nella Tavola 2 il trattino e' uno zero stampato: le righe
                # tutte a trattini sono capitoli senza cassa in quegli anni e
                # vanno tenute, altrimenti le somme che il prospetto dichiara
                # restano senza i loro addendi
                if s in ("-", "\u2010", "\u2013"):
                    nums.append(0.0)
                else:
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
    res = {"opere_ultimate": [], "sintesi_ultimate": [], "tavola2": [],
           "tavola1": []}
    if "C_DET" in byk:
        res["opere_ultimate"] = opere_ultimate(doc, byk["C_DET"], doc_id)
    # il prospetto di sintesi sta su una pagina a se', intitolata "TABELLA C",
    # oppure in testa al dettaglio: si cerca in entrambi i posti
    pagine_c = {}
    pagine_c.update(byk.get("C", {}))
    pagine_c.update(byk.get("C_DET", {}))
    if pagine_c:
        res["sintesi_ultimate"] = sintesi_ultimate(doc, pagine_c, doc_id)
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
    print("%-9s opere=%4d sintesiC=%2d Tavola2=%3d (cap/pg=%2d) Tavola1=%2d"
          % (doc_id, len(r["opere_ultimate"]), len(r["sintesi_ultimate"]),
             len(r["tavola2"]),
             sum(1 for x in r["tavola2"] if x["capitolo"] or x["pg"]),
             len(r["tavola1"])))
