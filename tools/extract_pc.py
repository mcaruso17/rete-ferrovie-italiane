"""Estrae dal PDF del Piano Commerciale RFI le schede dei progetti.

Nella sezione "Progetti per regione" ogni progetto ha una scheda di una
pagina, e la legenda del documento dice che la scheda "indica la riga del
Contratto di Programma 2022-2026 alla quale afferisce il finanziamento
dell'intervento": la riga "Rif. CdP-I: P210A - Collegamento Terni - Rieti...".
E' lo stesso legame dei servizi cartografici (aggancio_pc.py), ma con quello
che la mappa non ha: la descrizione del progetto, i benefici commerciali
attesi, l'anno di attivazione per fasi, la misura PNRR.

Come si legge una scheda. Il testo e' su due colonne, e l'estrattore di riga
le restituisce mescolate: ogni riga del PDF porta un pezzo della colonna
sinistra e uno della destra alla stessa altezza. Le colonne si separano per
ascissa (sinistra sotto 300 punti) e si rimettono in fila una dopo l'altra.
Nei benefici, l'etichetta (VELOCITA', CAPACITA'...) sta a sinistra e il testo
a destra; un'etichetta su due righe ("ACCESSIBILITA' / ALLA RETE") si ricuce.

Uso:
  python3 extract_pc.py PianoCommerciale.pdf cdp-rfi-dataset.json schede.json

Il dataset serve solo a dire quali codici citati esistono nella piattaforma.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF                        # noqa: E402
from pdftext import extract_page, group_lines   # noqa: E402
from tables import raw_cells                    # noqa: E402

RIF = re.compile(r"Rif\.?\s*CdP-?I\s*:\s*(.*)", re.I)
# codici CdP: 0362A, 0258_A, P240B, I107A, A2001B, 1674
CODICE = re.compile(r"\b(?:\d{4}|[A-Z]\d{3,4})(?:_?[A-Z])?\b")
ANNO = re.compile(r"(20\d\d|Oltre|fase|Fase|completamento|\*)")
COLONNA = 300          # ascissa che separa le due colonne
X_ANNO = 400           # la colonna dell'anno di attivazione, in alto a destra
# "8 km          Lunghezza linea": il riquadro dei principali numeri, con
# valore ed etichetta nella stessa cella separati da una fila di spazi
NUMERO = re.compile(r"^(\S.*?)\s{3,}(\S.*)$")


def celle(ln):
    # gli spazi interni si tengono: separano valore ed etichetta nel riquadro
    # dei numeri del progetto
    return [(x0, t.strip()) for x0, _x1, t, _i in raw_cells(ln) if t.strip()]


def ricuci(righe):
    """Righe di una colonna in un testo, con i trattini d'a capo tolti."""
    out = ""
    for r in righe:
        r = r.strip()
        if not r:
            continue
        if r.startswith("/ ") or r == "/":
            # il punto elenco del PDF e' una barra
            out += "\n- " + r[1:].strip()
        elif out.endswith("-") and r[:1].islower():
            out = out[:-1] + r
        else:
            out += (" " if out and not out.endswith("\n") else "") + r
    return re.sub(r"[ \t]+", " ", out).strip()


def leggi_scheda(doc, pg, pagina, codici):
    lns = group_lines(extract_page(doc, pg))
    righe = [(ln[0].y, celle(ln)) for ln in lns]
    righe = [(y, c) for y, c in righe if c]
    testi = [" ".join(t for _x, t in c) for _y, c in righe]
    if not any("Descrizione del progetto" in t for t in testi):
        return None
    i_rif = [i for i, t in enumerate(testi) if RIF.search(t)]
    i_desc = next(i for i, t in enumerate(testi) if "Descrizione del progetto" in t)
    # "Benefici commerciali" come prima cella a sinistra, sotto la descrizione.
    # In testata a destra puo' comparire "Benefici commerciali a completamento
    # del progetto": e' una didascalia, e prenderla per l'inizio dei benefici
    # svuotava la descrizione della Napoli-Bari
    i_ben = next((i for i, (_y, c) in enumerate(righe) if i > i_desc and c[0][0] < 100
                  and c[0][1].startswith("Benefici commerciali")), len(righe))
    testa_fine = i_rif[0] if i_rif else i_desc

    # testata: titolo a sinistra, anno e PNRR a destra
    titolo, anno, pnrr = [], [], ""
    for _y, r in righe[1:testa_fine]:    # la prima riga e' la barra di navigazione
        for x, t in r:
            if t.startswith("Benefici commerciali") or t == "PNRR":
                continue
            if t.startswith("Misura"):
                pnrr = t
            elif x >= X_ANNO:
                anno.append(t)
            elif x < 340:
                titolo.append(t)

    # riferimento CdP: ci possono essere piu' righe, e l'ultima puo' andare a
    # capo ("...linee af-" / "ferenti"): la continuazione e' la prima riga di
    # sinistra dopo il riferimento, se comincia in minuscolo
    rif = [RIF.search(testi[i]).group(1).strip() for i in i_rif]
    cod = []
    for r in rif:
        # i codici stanno prima del trattino che introduce la descrizione:
        # "0279A, 0284, 0279B - itinerario Napoli - Bari"
        testa = re.split(r"\s+-\s+|-(?=[A-Z][a-z])", r, maxsplit=1)[0]
        for c in CODICE.findall(testa):
            if c not in cod:
                cod.append(c)

    # descrizione: fra il riferimento e i benefici, su due colonne
    sx, dx, note = [], [], []
    for n, ((_y, r), t) in enumerate(zip(righe[testa_fine:i_ben], testi[testa_fine:i_ben])):
        if RIF.search(t):
            continue
        s = [c for x, c in r if x < COLONNA and c != "Descrizione del progetto"]
        d = [c for x, c in r if x >= COLONNA]
        if d and d[0].startswith("*"):
            note.append(" ".join(d))
            d = []
        if s and not sx and rif and rif[-1].endswith("-") and s[0][:1].islower():
            rif[-1] = rif[-1][:-1] + s[0]
            s = s[1:]
        if s:
            sx.append(" ".join(s))
        if d:
            dx.append(" ".join(d))
    descrizione = ricuci(sx + dx)

    # Benefici: etichetta a sinistra, testo a destra. L'etichetta e' centrata
    # in verticale sul suo blocco di testo, quindi sta a meta' delle righe,
    # non sulla prima: i blocchi si separano per interlinea (dentro un blocco
    # 12 punti, fra un blocco e l'altro di piu') e ogni etichetta va al blocco
    # che la contiene in altezza. Un'etichetta su due righe ("ACCESSIBILITA'"
    # / "ALLA RETE") finisce cosi' tutta sullo stesso blocco.
    testo_b, etich, numeri = [], [], []
    for y, r in righe[i_ben + 1:]:
        # il riquadro "I principali numeri del progetto" sta sotto i benefici:
        # valori a sinistra, titolo del riquadro a destra spezzato su tre righe
        r2 = []
        for x, c in r:
            m = NUMERO.match(c) if x < 120 else None
            if m:
                numeri.append({"k": m.group(2).strip(), "v": m.group(1).strip()})
            elif not (x > 400 and c in ("I principali", "numeri", "del progetto")):
                r2.append((x, c))
        r = r2
        if not r:
            continue
        t = " ".join(c for _x, c in r)
        if t.startswith("Il Piano Commerciale ed.") or (len(r) == 2 and r[0][1].isdigit()
                                                        and len(r[0][1]) <= 3):
            break
        for x, c in r:
            if x < 180 and c.isupper():
                etich.append((y, c))
        tx = " ".join(c for x, c in r if x >= 180)
        if tx:
            testo_b.append((y, tx))
    blocchi = []
    for y, tx in testo_b:
        if blocchi and blocchi[-1]["y1"] - y <= 16:
            blocchi[-1]["righe"].append(tx)
            blocchi[-1]["y1"] = y
        else:
            blocchi.append({"y0": y, "y1": y, "righe": [tx], "k": []})
    for y, c in etich:
        if not blocchi:
            break
        b = min(blocchi, key=lambda b: 0 if b["y1"] - 6 <= y <= b["y0"] + 6
                else min(abs(y - b["y0"]), abs(y - b["y1"])))
        b["k"].append(c)
    benefici = [{"k": " ".join(b["k"]), "t": ricuci(b["righe"])} for b in blocchi]

    regione = ""
    ult = righe[-1][1]
    if len(ult) == 2 and ult[0][1].isdigit():
        regione = ult[1][1]
    return {"pagina": pagina, "titolo": " ".join(titolo).strip(),
            "anno": " ".join(anno).replace(" *", "*").strip(), "pnrr": pnrr,
            "rif": "; ".join(r.rstrip(";").strip() for r in rif), "codici": cod,
            "noti": [c for c in cod if c in codici],
            "descrizione": descrizione, "note": note,
            "benefici": benefici, "numeri": numeri, "regione": regione}


def main():
    pdf, app, dest = sys.argv[1:4]
    codici = {p.get("codice") or p.get("c") for p in json.load(open(app, encoding="utf-8"))["progetti"]}
    doc = PDF(pdf)
    pagine = doc.pages()
    # la sezione Progetti comincia dove l'indice lo dice, "PROGETTI ... 375":
    # le schede prima di quella pagina non esistono, e cercarle altrove
    # troverebbe solo le pagine di legenda
    schede, senza_rif = [], 0
    for i in range(374, len(pagine)):
        try:
            s = leggi_scheda(doc, pagine[i], i + 1, codici)
        except Exception as e:           # una pagina illeggibile non ferma le altre
            print("  pagina %d non letta: %s" % (i + 1, e))
            continue
        if not s:
            continue
        schede.append(s)
        if not s["codici"]:
            senza_rif += 1

    # lo stesso progetto compare in ogni regione che attraversa: una scheda
    # sola, con l'elenco delle regioni e delle pagine
    uniche = {}
    for s in schede:
        k = (s["titolo"].lower(), tuple(sorted(s["codici"])))
        if k in uniche:
            u = uniche[k]
            if s["regione"] and s["regione"] not in u["regioni"]:
                u["regioni"].append(s["regione"])
            u["pagine"].append(s["pagina"])
        else:
            s["regioni"] = [s.pop("regione")] if s["regione"] else []
            s.pop("regione", None)
            s["pagine"] = [s.pop("pagina")]
            uniche[k] = s
    out = list(uniche.values())
    ignoti = sorted({c for s in out for c in s["codici"] if c not in codici})
    json.dump({"documento": os.path.basename(pdf), "schede": out},
              open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("piano commerciale (PDF): %d schede lette, %d progetti distinti, "
          "%d senza riferimento CdP" % (len(schede), len(out), senza_rif))
    noti = {c for s in out for c in s["noti"]}
    print("  codici CdP citati: %d, presenti nella piattaforma: %d"
          % (len({c for s in out for c in s["codici"]}), len(noti)))
    if ignoti:
        print("  citati ma assenti nella piattaforma: %s" % ", ".join(ignoti))


if __name__ == "__main__":
    main()
