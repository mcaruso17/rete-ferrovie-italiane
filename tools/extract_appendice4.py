"""Evoluzione del portafoglio rispetto al precedente aggiornamento: Appendice 4
alla Relazione Informativa dell'aggiornamento Investimenti ("delta costi"), e
il dossier ex ante dei progetti con un aumento di costo rilevante.

La tabella, per ogni intervento delle Tabelle A e B, scompone la differenza di
costo a vita intera fra l'aggiornamento precedente e questo:
  costo prec. + ultimati + riclassifiche + variazioni di costo/perimetro
  + nuove esigenze + adeguamenti tariffari = costo attuale
con le variazioni totali, quelle al netto di ultimati, riclassifiche e
adeguamenti tariffari (la crescita "vera"), il segno di nuovo inserimento e la
motivazione scritta da RFI. A p. 1 lo stesso per programma e tabella.

Il dossier (un PDF a parte) ha una sezione per progetto, che si apre con
"Progetto <codice>:" e il CUP: se ne tiene la pagina d'inizio.

Uso:
  python3 extract_appendice4.py tabella.pdf dossier.pdf agg2025 ../data/appendice4-agg2025.json
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF                        # noqa: E402
from pdftext import extract_page, group_lines  # noqa: E402
from tables import raw_cells                   # noqa: E402

NUM = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")
CODICE = re.compile(r"^[A-Z]{0,2}\d{3,4}(?:_?[A-Z0-9])?$")
VOCI = ["costo_prec", "ultimati", "riclassifiche", "variazioni_costo", "nuove_esigenze",
        "adeguamenti_tariffari", "costo", "variazioni_totali", "variazioni_nette"]
# colonne della pagina (punti): codice, descrizione, numeri, motivazione
X_DESCR, X_NUMERI, X_MOTIVO = 38, 240, 677


def num(t):
    return float(t.replace(".", "").replace(",", "."))


def celle(doc, pg):
    return [[(a, b, t.strip()) for a, b, t, _i in raw_cells(ln) if t.strip()]
            for ln in group_lines(extract_page(doc, pg))]


def unisci(a, b):
    if not a:
        return b
    return a[:-1] + b if a.endswith("-") and not a.endswith(" -") else a + " " + b


def tabella(pdf):
    doc = PDF(pdf)
    pagine = doc.pages()
    riepilogo = []
    for L in celle(doc, pagine[0]):
        testi = [t for _a, _b, t in L]
        nums = [t for t in testi if NUM.match(t)]
        if len(nums) == 9:
            etich = " ".join(t for t in testi if not NUM.match(t))
            m = re.match(r"^(A|B|C|\d{2})\s+(.*)$", etich)
            riepilogo.append({"voce": m.group(1) if m else "", "n": m.group(2) if m else etich,
                              **dict(zip(VOCI, map(num, nums)))})
    righe, totali = [], {}
    tab = prog = None
    for n, pg in enumerate(pagine[1:], 2):
        cur = None
        for L in celle(doc, pg):
            testo = " ".join(t for _a, _b, t in L)
            m = re.match(r"^TABELLA ([ABC])\b", testo)
            if m:
                tab = m.group(1)
                continue
            m = re.match(r"^(A\d{2})-", testo)
            if m and not CODICE.match(L[0][2]):
                prog = m.group(1)
                continue
            if testo.startswith("Nota bene"):
                break
            nums = [t for _a, _b, t in L if NUM.match(t)]
            if testo.startswith("Totale"):
                cur = None
                if len(nums) == 9:
                    totali[prog if tab == "A" else tab] = dict(zip(VOCI, map(num, nums)))
                continue
            if CODICE.match(L[0][2]) and L[0][0] < X_DESCR:
                cur = {"c": L[0][2], "tab": tab, "prog": prog if tab == "A" else None,
                       "n": "", "mot": "", "nuovo": False, "p": n}
                righe.append(cur)
                L = L[1:]
            if cur is None:
                continue
            for a, _b, t in L:
                if a >= X_MOTIVO:
                    cur["mot"] = unisci(cur["mot"], t)
                elif a >= X_NUMERI and NUM.match(t):
                    continue
                elif t == "X":
                    cur["nuovo"] = True
                elif a < X_NUMERI:
                    cur["n"] = unisci(cur["n"], t)
            if len(nums) == 9 and "costo" not in cur:
                cur.update(zip(VOCI, map(num, nums)))
    return riepilogo, righe, totali


COD = r"[A-Z]{0,2}\d{3,4}(?:_?[A-Z0-9])?"


def dossier(pdf, righe):
    """Le sezioni del dossier e le righe del contratto a cui si riferiscono:
    i codici del frontespizio ("Progetto 0136", "Righe ... 0313A e 0313B") e
    quelli della prima "riga ..." della premessa, tenendo solo quelli della
    tabella; se non ce n'e' nessuno, le righe il cui nome contiene la prima
    parola lunga del titolo (Venafro)."""
    doc = PDF(pdf)
    noti = {r["c"]: r["n"] for r in righe}
    pagine = doc.pages()
    testi = [" ".join(" ".join(t for _a, _b, t in x) for x in celle(doc, pg)) for pg in pagine]
    inizi = [i for i, t in enumerate(testi) if re.match(r"^\s*DOSSIER\b", t)]
    out = []
    for k, i in enumerate(inizi):
        fine = inizi[k + 1] - 1 if k + 1 < len(inizi) else len(pagine) - 1
        fronte = re.sub(r"\s+", " ", testi[i]).strip()
        titolo = re.sub(r"^DOSSIER (EX ANTE|DI VALUTAZIONE)\s*", "", fronte)
        titolo = re.split(r"\(|Data:|\b[Rr]igh?[ae] Contratto", titolo)[0].strip()
        codici = re.findall(r"Progetto\s+(%s)\b" % COD, fronte)
        for m in re.finditer(r"\b[Rr]igh?[ae]\b[^()]{0,60}", fronte):
            codici += re.findall(r"\b(%s)\b" % COD, m.group(0))
        resto = " ".join(testi[i + 1:fine + 1])
        m = re.search(r"\b[Rr]igh?[ae]\s+(%s)(?:\s*(?:,|e)\s*(%s))?" % (COD, COD), resto)
        if m:
            codici += [c for c in m.groups() if c]
        codici = [c for c in dict.fromkeys(codici) if c in noti]
        if not codici:
            parola = next((w for w in re.findall(r"[A-Z][a-z]{4,}", titolo) if w not in ("Potenziamento", "Raddoppio", "Progetto", "Nuova", "Velocizzazione")), "")
            codici = [c for c, n in noti.items() if parola and parola in n]
        cup = re.findall(r"\b([A-Z]\d{2}[A-Z]\d{11})\b", fronte)
        out.append({"titolo": re.sub(r"^Progetto\s+%s:?\s*" % COD, "", titolo), "c": codici, "cup": cup,
                    "p": i + 1, "fine": fine + 1})
    return out


def main():
    pdf, pdf_dossier, doc_id, dest = sys.argv[1:5]
    riepilogo, righe, totali = tabella(pdf)
    dos = dossier(pdf_dossier, righe)
    out = {"doc": doc_id, "documento": os.path.basename(pdf), "dossier_documento": os.path.basename(pdf_dossier),
           "voci": VOCI, "riepilogo": riepilogo, "righe": righe, "totali": totali, "dossier": dos}
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    # controlli: righe complete, somma delle componenti, somme per programma
    senza = [r["c"] for r in righe if "costo" not in r]
    sbilanciate = [r["c"] for r in righe if "costo" in r and abs(sum(r[v] for v in VOCI[:6]) - r["costo"]) > 0.02]
    scarti = {}
    for k, t in totali.items():
        s = sum(r["costo"] for r in righe if "costo" in r and (r["prog"] if r["tab"] == "A" else r["tab"]) == k)
        if abs(s - t["costo"]) > 0.05:
            scarti[k] = round(s - t["costo"], 2)
    print("appendice 4 %s: %d righe (%d nuovi inserimenti), %d totali di gruppo, %d dossier; "
          "senza numeri %s; componenti che non sommano %s; scarti sui totali %s"
          % (doc_id, len(righe), sum(r["nuovo"] for r in righe), len(totali), len(dos), senza, sbilanciate, scarti))


if __name__ == "__main__":
    main()
