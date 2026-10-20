"""Appendice 5 alla Relazione Informativa dell'aggiornamento 2025: "Evoluzione
delle coperture finanziarie per fonte di finanziamento", Tabelle A e B.
Per ogni intervento le risorse assegnate nell'aggiornamento 2024, le
variazioni dell'anno per tipo e per fonte, e le risorse del 2025:

  agg. 2024 | ultimati | riclassifiche ed errata corrige | riduzioni |
  incrementi: MEF Legge di Bilancio 2025 e DL Superbonus, MEF altro, MIT
  Prosecuzione Opere Pubbliche e Olimpiadi, FSC UE e altro, PNRR nuovi
  progetti | rimodulazioni: MEF, altro | totale variazioni | agg. 2025

Il nome dell'intervento sta su una riga e i tredici numeri sulla riga sotto;
una "X" a sinistra dei numeri segna il nuovo inserimento. Le righe "Totale"
(programma, bacino, tabella) hanno nome e numeri sulla stessa riga.

Controlli: ogni riga torna (agg. 2024 + variazioni = agg. 2025) e le righe
sommano ai totali delle Tabelle A e B stampati.

Uso:
  python3 extract_appendice5.py ../documenti/cdpi-agg2025/appendice_5variazione_risorse.pdf \\
          ../data/appendice5-agg2025.json
"""
import json
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines
from tables import to_float

RE_NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
RE_COD = re.compile(r"^[A-Z0-9][A-Z0-9_.]{2,7}$")
NUMERI = ["risorse_agg2024", "ultimati", "riclassifiche_errata_corrige", "riduzioni",
          "incrementi_mef_legge_bilancio_2025_dl_superbonus", "incrementi_mef_altro",
          "incrementi_mit_prosecuzione_opere_olimpiadi", "incrementi_fsc_ue_altro", "incrementi_pnrr",
          "rimodulazioni_mef", "rimodulazioni_altro", "totale_variazioni", "risorse_agg2025"]


def main():
    pdf, out = sys.argv[1], sys.argv[2]
    doc = PDF(pdf)
    righe, totali, cur, tabella = [], {}, None, ""
    for n, pg in enumerate(doc.pages(), 1):
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            w = parole(it)
            if not w:
                continue
            testo = " ".join(t for x, t, _ in w if x < 320)
            nums = [t for x, t, _ in w if x > 350 and RE_NUM.match(t)]
            if testo.startswith("TABELLA "):
                tabella = testo.split()[1]
                continue
            if testo.startswith("Totale Tabella") and len(nums) == len(NUMERI):
                totali[testo.split()[2]] = dict(zip(NUMERI, map(to_float, nums)))
                continue
            if testo.startswith("Totale"):
                cur = None
                continue
            if w[0][0] < 25 and RE_COD.match(w[0][1]) and not nums:
                cur = {"codice": w[0][1], "descrizione": " ".join(t for x, t, _ in w[1:] if x < 320),
                       "tabella": tabella, "pagina": n}
                continue
            if cur and len(nums) == len(NUMERI) and not testo:
                cur.update(dict(zip(NUMERI, map(to_float, nums))))
                cur["nuovo_inserimento"] = any(t == "X" and 320 <= x < 360 for x, t, _ in w)
                righe.append(cur)
                cur = None
            elif cur and testo and not nums:
                cur["descrizione"] += " " + testo
    problemi = []
    for r in righe:
        if abs(r["risorse_agg2024"] + r["totale_variazioni"] - r["risorse_agg2025"]) > 0.02:
            problemi.append("%s: 2024 + variazioni diverso dal 2025" % r["codice"])
        if abs(sum(r[k] for k in NUMERI[1:-2]) - r["totale_variazioni"]) > 0.03:
            problemi.append("%s: le variazioni non sommano al totale" % r["codice"])
    for t in ("A", "B"):
        if t not in totali:
            problemi.append("Totale Tabella %s non trovato" % t)
            continue
        for k in NUMERI:
            s = round(sum(r[k] for r in righe if r["tabella"] == t), 2)
            if abs(s - totali[t][k]) > 0.1:
                problemi.append("Tabella %s, %s: righe %.2f, totale %.2f" % (t, k, s, totali[t][k]))
    json.dump({"doc": "agg2025", "fonte": pdf.split("/")[-1], "colonne": NUMERI, "righe": righe,
               "totali": totali}, open(out, "w"), ensure_ascii=False, indent=1)
    print("%s: %d interventi (A %d, B %d), %d nuovi inserimenti; controlli %s" % (
        out, len(righe), sum(1 for r in righe if r["tabella"] == "A"), sum(1 for r in righe if r["tabella"] == "B"),
        sum(1 for r in righe if r["nuovo_inserimento"]), "ok" if not problemi else "DIVERSI"))
    for p in problemi:
        print("  attenzione:", p)
    if problemi:
        sys.exit(1)


if __name__ == "__main__":
    main()
