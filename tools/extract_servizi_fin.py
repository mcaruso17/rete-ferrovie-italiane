"""Estrae dai Contratti di Programma parte Servizi le tabelle finanziarie.

Tre allegati, ciascuno con il suo mestiere:

- **4a**, quadro delle proiezioni degli impieghi per competenza: quanto si
  prevede di spendere ogni anno per la gestione della rete (conto esercizio) e
  per la manutenzione straordinaria (conto impianti). Solo nel contratto base:
  gli atti successivi aggiornano questi valori nel testo degli articoli, non in
  una tabella;
- **4b**, fonti delle risorse per cassa: le leggi che finanziano il contratto,
  con il capitolo del bilancio dello Stato e il profilo annuo. E' l'equivalente
  Servizi della Tavola 2 degli Investimenti, e c'e' in ogni edizione leggibile;
- **4c**, dettaglio delle assegnazioni dai fondi straordinari (prosecuzione
  opere, adeguamento prezzi, PON, DL Alluvioni, enti locali): l'unico punto in
  cui la parte Servizi scende al singolo CUP;
- **12**, le opere PNRR: si tengono solo le righe attribuite al CdP-Servizi.

Tutto si valida contro i totali stampati. Il 4b ne ha su due assi: ogni riga
dichiara il totale 2022-2026 e il totale complessivo, e ogni sezione dichiara
il totale di colonna. Una colonna assegnata male rompe almeno uno dei due.

Uso:
  python3 extract_servizi_fin.py ../CdP_Servizi_2022-2026.pdf cdps2022 out.json

L'atto integrativo 2025 porta gli allegati come immagini scansionate: senza
riconoscimento ottico non c'e' testo da leggere, e il risultato vuoto va
dichiarato, non riempito. Le sue modifiche sono comunque riassorbite nel 4b
ripubblicato per intero dall'atto 2026.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdfmini import PDF                        # noqa: E402
from pdftext import extract_page, group_lines   # noqa: E402
from tables import raw_cells                    # noqa: E402

RIGO = re.compile(r"^\d[a-z]?$")
# gli importi hanno sempre la virgola decimale; gli spazi dentro il numero
# ("7 .024,51", "2 6,53") sono un artefatto dell'impaginazione del PDF
_IMPORTO = re.compile(r"^\(?-?[\d.]*\d,\d+\)?$")


class _Importo:
    def match(self, t):
        return _IMPORTO.match(t.replace(" ", ""))


IMPORTO = _Importo()
CAPITOLO = re.compile(r"^(\d{4}|n\.a\.)$")
CUP = re.compile(r"^[A-Z]\d{2}[A-Z]\d{11}$")
ANNI = ["2022", "2023", "2024", "2025", "2026"]
# arrotondamento: valori stampati a due decimali, fino a sette per riga
TOLL = 0.03


def num(t):
    t = t.replace(" ", "")
    neg = t.startswith("(") or t.startswith("-")
    t = t.strip("()-").replace(".", "").replace(",", ".")
    v = float(t)
    return -v if neg else v


def celle(ln):
    out = []
    for x0, x1, t, _i in raw_cells(ln):
        t = t.strip()
        if not t:
            continue
        # "4" e ",15" in due celle vicine sono lo stesso numero spezzato
        # dall'impaginazione (4c dell'atto 2024, riga PON)
        if out and t.startswith(",") and re.match(r"^-?[\d.]+$", out[-1][2]) \
                and x0 - out[-1][1] < 15:
            out[-1] = (out[-1][0], x1, out[-1][2] + t)
            continue
        out.append((x0, x1, t))
    return out


def testa(doc, pg, n=3):
    try:
        return " ".join("".join(t.text for t in ln)
                        for ln in group_lines(extract_page(doc, pg))[:n])
    except Exception:
        return ""


# --------------------------------------------------------------- 4a e 4b
def ancore(righe, i):
    """Le colonne di una tabella 4a/4b, dalla riga di intestazione "rigo".

    Le colonne si riconoscono dal bordo destro delle etichette, perche' gli
    importi sono allineati a destra: il bordo sinistro dipende dalla lunghezza
    del numero, quello destro no. Le etichette stanno su tre righe (Totale /
    2022-2026 / complessivo), quindi si guarda anche la riga sotto e sopra.
    """
    col = {}
    for x0, x1, t in celle(righe[i]):
        if t in ANNI:
            col[t] = x1
        elif t.lower() == "oltre":
            col["oltre"] = x1
    for j in (i - 1, i + 1, i + 2):
        if 0 <= j < len(righe):
            for x0, x1, t in celle(righe[j]):
                if t == "2022-2026":
                    col["tot"] = x1
                elif t.lower() == "complessivo":
                    col["compl"] = x1
                elif t == "2021":
                    col["pm"] = x1
    return col


def leggi_prospetto(doc, pg, pagina):
    righe = group_lines(extract_page(doc, pg))
    out = []
    col, sezione = None, ""
    rigo_x = desc_x = None
    pendente, ultima = [], None
    for i, ln in enumerate(righe):
        cs = celle(ln)
        if not cs:
            continue
        if cs[0][2].lower() == "rigo":
            col = ancore(righe, i)
            # le pagine non hanno tutte la stessa larghezza (l'atto 2024 e'
            # impaginato su un foglio piu' largo): le posizioni si prendono
            # dall'intestazione, non da numeri fissi
            rigo_x, desc_x = cs[0][0], cs[1][0] if len(cs) > 1 else cs[0][1]
            sezione = " ".join(t for _a, _b, t in cs[1:] if t not in ANNI
                               and t.lower() != "oltre")
            pendente, ultima = [], None
            continue
        if col is None:
            continue
        if RIGO.match(cs[0][2]) and cs[0][0] < desc_x - 2:
            testo, cap, valori = [], None, {}
            for x0, x1, t in cs[1:]:
                if CAPITOLO.match(t) and not valori:
                    cap = t
                elif IMPORTO.match(t):
                    k = min(col, key=lambda c: abs(col[c] - x1))
                    valori[k] = round(valori.get(k, 0) + num(t), 2)
                else:
                    testo.append(t)
            r = {"rigo": cs[0][2], "sezione": sezione,
                 "voce": " ".join(pendente + testo).strip(), "capitolo": cap,
                 "valori": valori, "pagina": pagina, "_pre": bool(pendente)}
            out.append(r)
            pendente, ultima = [], r
            continue
        # righe di solo testo: pezzi di descrizione che vanno a capo. La cella
        # con il rigo e' centrata verticalmente sul blocco, quindi un pezzo
        # prima del rigo e' suo, e uno dopo e' suo solo se il blocco era gia'
        # cominciato sopra; altrimenti e' l'inizio del successivo
        if any(IMPORTO.match(t) for _a, _b, t in cs):
            continue
        if cs[0][0] > desc_x + 8:   # intestazioni di colonna, non descrizioni
            continue
        t = " ".join(t for _a, _b, t in cs)
        if t.startswith("(*)") or t.lower().startswith(("fonti per cassa",
                                                        "quadro delle")):
            pendente, ultima = [], None
            continue
        if ultima is not None and ultima["_pre"] and not ultima.get("_post"):
            ultima["voce"] = (ultima["voce"] + " " + t).strip()
            ultima["_post"] = True
        else:
            pendente.append(t)
    for r in out:
        r.pop("_pre", None)
        r.pop("_post", None)
    return out


def controlla_prospetto(righe, nome):
    """Riga per riga e colonna per colonna contro i totali stampati."""
    esiti, note = [], []
    for r in righe:
        v = r["valori"]
        anni = [v.get(a, 0) for a in ANNI]
        if "tot" in v:
            ok = abs(sum(anni) - v["tot"]) <= TOLL
            esiti.append(ok)
            if not ok:
                note.append("%s rigo %s: anni %.2f contro totale %.2f"
                            % (nome, r["rigo"], sum(anni), v["tot"]))
        if "compl" in v:
            s = v.get("pm", 0) + v.get("tot", sum(anni)) + v.get("oltre", 0)
            ok = abs(s - v["compl"]) <= TOLL
            esiti.append(ok)
            if not ok:
                note.append("%s rigo %s: %.2f contro complessivo %.2f"
                            % (nome, r["rigo"], s, v["compl"]))
    # totali di sezione: il rigo "1" somma gli "1x", e cosi' via
    per = {r["rigo"]: r for r in righe}
    for tot in ("1", "2", "5"):
        if tot not in per:
            continue
        figli = [r for r in righe if r["rigo"][0] == tot and len(r["rigo"]) == 2]
        if not figli:
            continue
        for k, atteso in per[tot]["valori"].items():
            s = sum(f["valori"].get(k, 0) for f in figli)
            ok = abs(s - atteso) <= TOLL * max(1, len(figli)) / 2
            esiti.append(ok)
            if not ok:
                note.append("%s rigo %s colonna %s: righe %.2f contro stampato %.2f"
                            % (nome, tot, k, s, atteso))
    if "3" in per and "1" in per and "2" in per:
        for k, atteso in per["3"]["valori"].items():
            s = per["1"]["valori"].get(k, 0) + per["2"]["valori"].get(k, 0)
            ok = abs(s - atteso) <= TOLL
            esiti.append(ok)
            if not ok:
                note.append("%s rigo 3 colonna %s: 1+2 = %.2f contro %.2f"
                            % (nome, k, s, atteso))
    return esiti, note


# ------------------------------------------------------------------- 4c
def leggi_4c(doc, pg, pagina):
    """Le assegnazioni per CUP, raggruppate per decreto.

    Le colonne di contesto (fonte, atto integrativo, lettera, riferimento
    normativo) sono celle unite, centrate verticalmente sul gruppo: si
    raccolgono come testo del gruppo, che si chiude a ogni riga "Totale". La
    fonte e l'atto si leggono dalle righe di chiusura, che li scrivono per
    esteso quando ci sono, e altrimenti dal testo del gruppo.
    """
    righe = [celle(ln) for ln in group_lines(extract_page(doc, pg))]
    col, cup_x1 = {}, None
    for cs in righe:
        for x0, x1, t in cs:
            if t.startswith("CdP-S 2016"):
                col["prec"] = x1
            elif t.startswith("CdP-S 2022"):
                col["corr"] = x1
            elif t == "Totale" and x0 > 600:
                col["tot"] = x1
            elif CUP.match(t) and cup_x1 is None:
                cup_x1 = x1
    if len(col) < 3 or cup_x1 is None:
        return [], [], col
    inizio_importi = min(col.values()) - 60

    def colonna(x1):
        return min(col, key=lambda c: abs(col[c] - x1))

    out, chiusi = [], []
    gruppo, contesto, descr = [], [], []

    def chiudi():
        """Distribuisce testo e contesto del gruppo alle sue righe.

        Con un solo decreto nel gruppo il contesto vale per tutte le righe. Con
        piu' decreti nello stesso gruppo (enti locali: Regione Siciliana e
        Provincia di Bolzano, senza un totale in mezzo) ogni pezzo va alla riga
        CUP piu' vicina, perche' le celle unite sono centrate sulla propria.
        """
        def vicina(i):
            return min(gruppo, key=lambda r: abs(r["_i"] - i))
        rif = [t for _i, t in contesto if RIFERIMENTO_INIZIO.match(t)]
        for r in gruppo:
            r["_ctx"] = []
        for i, t in contesto:
            if len(rif) > 1:
                vicina(i)["_ctx"].append(t)
            else:
                for r in gruppo:
                    r["_ctx"].append(t)
        for i, t in descr:
            r = vicina(i)
            if len(gruppo) == 1 or not r["_d_riga"]:
                r["_extra"].append((i, t))
        for r in gruppo:
            pezzi = sorted(r.pop("_extra") + [(r["_i"], r["descrizione"])])
            r["descrizione"] = " ".join(t for _i, t in pezzi if t).strip()
            r["_ctx"] = " ".join(r["_ctx"])
        out.extend(gruppo)

    for i, cs in enumerate(righe):
        if not cs:
            continue
        cup = next((c for c in cs if CUP.match(c[2])), None)
        if cup:
            testo, v = [], {}
            for x0, x1, t in cs:
                if t == cup[2]:
                    continue
                if IMPORTO.match(t) and x0 > cup_x1:
                    v[colonna(x1)] = num(t)
                elif x0 > cup_x1:
                    testo.append(t)
                else:
                    contesto.append((i, t))
            gruppo.append({"cup": cup[2], "descrizione": " ".join(testo),
                           "prec": v.get("prec", 0.0), "corr": v.get("corr", 0.0),
                           "totale": v.get("tot"), "pagina": pagina,
                           "_i": i, "_d_riga": bool(testo), "_extra": []})
            continue
        nums = [(x1, num(t)) for _a, x1, t in cs if IMPORTO.match(t)]
        testo = " ".join(t for _a, _b, t in cs if not IMPORTO.match(t))
        # la riga di totale del decreto puo' portare in margine altri pezzi di
        # celle unite ("Terzo Atto", una "x" di spunta): conta che ci sia la
        # cella "Totale" da sola, e il resto torna al contesto
        if nums and any(t == "Totale" for _a, _b, t in cs):
            contesto.extend((i, t) for _a, _b, t in cs
                            if t != "Totale" and not IMPORTO.match(t))
            chiudi()
            chiusi.append({"righe": gruppo,
                           "stampato": {colonna(x1): n for x1, n in nums}})
            gruppo, contesto, descr = [], [], []
            continue
        m = re.search(r"Totale complessivo (.+)", testo)
        if m and nums:
            # PON, DL Alluvioni ed enti locali non hanno una riga "Totale" per
            # decreto: il gruppo lo chiude il totale della fonte
            if gruppo:
                chiudi()
                gruppo, contesto, descr = [], [], []
            fonte = re.sub(r"\s+", " ", m.group(1)).strip()
            for r in out:
                r.setdefault("fonte", fonte)
            chiusi.append({"righe": [r for r in out if r["fonte"] == fonte],
                           "stampato": {colonna(x1): n for x1, n in nums}})
            continue
        m = re.search(r"nel (\w+) Atto Integrativo", testo)
        if m:
            for r in out:
                r.setdefault("_atto", m.group(1))
            continue
        if testo.startswith("Importo totale"):
            if nums:
                chiusi.append({"importo_totale": nums[-1][1]})
            continue
        for x0, x1, t in cs:
            if IMPORTO.match(t):
                continue
            if x0 > cup_x1 and x1 < inizio_importi + 60:
                descr.append((i, t))
            else:
                contesto.append((i, t))
    for r in out:
        ctx = r.pop("_ctx", "")
        for k in ("_i", "_d_riga"):
            r.pop(k, None)
        m = re.search(r"(Primo|Secondo|Terzo|Quarto)\s+Atto", ctx)
        r["atto"] = (r.pop("_atto", None) or (m.group(1) if m else "")).lower()
        r["riferimento"] = riferimento(ctx)
        r.setdefault("fonte", "")
        # "materi ali": spazio spurio dentro una parola, nel titolo della fonte
        r["fonte"] = r["fonte"].replace("materi ali", "materiali").replace("pubbl iche", "pubbliche")
    return out, chiusi, col


RIFERIMENTO_INIZIO = re.compile(r"^(Decreto|Presa d.atto|Disciplinare|Convenzione|Legge)\b")
_RIF = [
    re.compile(r"Decreto (?:MIT|direttoriale)[^()]*?del \d{1,2} \w+ \d{4}"),
    re.compile(r"Presa d.atto prot\. n\. \d+ del \d{1,2} \w+ \d{4}"),
    re.compile(r"Legge \d+/\d{4} di conversione del DL \d+/\d{4}"),
]


def riferimento(ctx):
    """L'atto che dispone l'assegnazione, ripulito dai pezzi di celle vicine."""
    # le colonne unite accanto (lettera delle premesse, articolo, atto
    # integrativo) si intercalano nel testo: si tolgono prima di cercare
    ctx = re.sub(r"\b(?:lettera \w\)|Art\. 2 co\. ?1|CdP-Servizi|2022-2026|"
                 r"Integrativo al|(?:Primo|Secondo|Terzo|Quarto) Atto|[A-Z](?: e [A-Z])?)(?=\s|$)",
                 " ", ctx)
    ctx = re.sub(r"\s+", " ", ctx)
    for p in _RIF:
        m = p.search(ctx)
        if m:
            return m.group(0)
    # disciplinari e convenzioni vanno a capo prima della data
    m = re.search(r"((?:Disciplinare|Convenzione) (?:sottoscritt[oa] )?(?:fra|tra) .+? del)\b", ctx)
    if m:
        d = re.search(r"\d{2}/\d{2}/\d{4}", ctx[m.end():])
        return m.group(1) + (" " + d.group(0) if d else "")
    return ""



# ------------------------------------------------------------------- 12
def leggi_12(doc, pg, pagina):
    """Righe PNRR attribuite al CdP-Servizi."""
    out = []
    for ln in group_lines(extract_page(doc, pg)):
        cs = celle(ln)
        tutto = " ".join(t for _a, _b, t in cs)
        if "CdP-Servizi" not in tutto.replace(" ", "") and "CdP-Servizi" not in tutto:
            continue
        cup = next((c for c in cs if CUP.match(c[2])), None)
        if not cup:
            continue
        nums = [num(t) for _a, _b, t in cs if IMPORTO.match(t)]
        testo = [t for x0, _b, t in cs if x0 < cup[0] and not IMPORTO.match(t)
                 and t != "CdP-Servizi"]
        misura = testo[0] if testo and re.match(r"^M\d|^\d\.\d", testo[0]) else ""
        nome = " ".join(testo[1:] if misura else testo)
        # l'atto 2024 pubblica l'elenco PNRR intero in milioni arrotondati
        # all'unita', con colonne diverse: senza i sei importi a due decimali
        # la riga non si puo' controllare, e si usa l'edizione 2026
        if len(nums) < 6:
            continue
        out.append({"cup": cup[2], "misura": misura, "intervento": nome,
                    "importi": nums, "pagina": pagina})
    return out


# ------------------------------------------------------------------ main
def main():
    pdf, doc_id, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    doc = PDF(pdf)
    pagine = doc.pages()
    dati = {"documento": doc_id, "impieghi": [], "fonti": [], "assegnazioni": [],
            "pnrr": [], "pagine": {}, "note": []}
    chiusi_4c = []
    senza_testo = 0
    for i, pg in enumerate(pagine):
        t = testa(doc, pg)
        if not t:
            senza_testo += 1
            continue
        p = i + 1
        if re.search(r"Allegato 4\s*a\b", t) and "impieghi" in testa(doc, pg, 6):
            dati["impieghi"].extend(leggi_prospetto(doc, pg, p))
            dati["pagine"].setdefault("4a", []).append(p)
        elif re.search(r"Allegato 4\s*b\b", t):
            dati["fonti"].extend(leggi_prospetto(doc, pg, p))
            dati["pagine"].setdefault("4b", []).append(p)
        elif re.search(r"Allegato 4\s*c\b", t):
            r, ch, _c = leggi_4c(doc, pg, p)
            dati["assegnazioni"].extend(r)
            chiusi_4c.extend(ch)
            dati["pagine"].setdefault("4c", []).append(p)
        elif re.search(r"Allegato 12\b", t) or (dati["pagine"].get("12") and
                                                 "PNRR" in testa(doc, pg, 8)):
            r = leggi_12(doc, pg, p)
            if r:
                dati["pnrr"].extend(r)
                dati["pagine"].setdefault("12", []).append(p)

    # ------------------------------------------------------ i controlli
    esiti, note = [], []
    for nome, righe in (("4a", dati["impieghi"]), ("4b", dati["fonti"])):
        # il 4b ha due prospetti con numerazione propria (1-3 e 4-5): si
        # controllano insieme perche' i righi non si ripetono
        e, n = controlla_prospetto(righe, nome)
        esiti += e
        note += n
    for g in chiusi_4c:
        if "importo_totale" in g:
            # Il totale generale dell'atto 2026 (150,83) non e' la somma dei
            # suoi totali di fonte (8,55 + 20,69 + 4,15 + 0,80 + 113,60 =
            # 147,79), che invece tornano con le righe e con le voci del 4b.
            # E' un'incoerenza della fonte, non della lettura: si dichiara.
            s = sum(r["totale"] or 0 for r in dati["assegnazioni"])
            if abs(s - g["importo_totale"]) > 0.05:
                dati["note"].append(
                    "4c: il totale generale stampato (%.2f) non e' la somma delle "
                    "righe (%.2f), che invece torna con i totali di fonte: incoerenza della fonte"
                    % (g["importo_totale"], s))
            continue
        for k, atteso in g["stampato"].items():
            s = sum((r["totale"] if k == "tot" else r[k]) or 0 for r in g["righe"])
            ok = abs(s - atteso) <= 0.011 * max(1, len(g["righe"]))
            esiti.append(ok)
            if not ok:
                note.append("4c gruppo %s colonna %s: righe %.3f contro %.3f"
                            % (g["righe"][0]["cup"] if g["righe"] else "?", k, s, atteso))
    for r in dati["assegnazioni"]:
        if r["totale"] is not None:
            ok = abs(r["prec"] + r["corr"] - r["totale"]) <= 0.011
            esiti.append(ok)
            if not ok:
                note.append("4c %s: %.3f + %.3f contro %.3f"
                            % (r["cup"], r["prec"], r["corr"], r["totale"]))
    for r in dati["pnrr"]:
        im = r["importi"]
        # totale PNRR, di cui in essere, di cui nuovi, altri nazionali, UE,
        # totale risorse: il primo e' la somma dei due "di cui", l'ultimo la
        # somma del primo e degli altri finanziamenti
        if len(im) >= 6:
            ok = (abs(im[1] + im[2] - im[0]) <= TOLL and
                  abs(im[0] + im[3] + im[4] - im[-1]) <= TOLL)
            esiti.append(ok)
            if not ok:
                note.append("12 %s: importi incoerenti %s" % (r["cup"], im))
    fonte_incoerente = dati["note"]
    dati["note"] = note + fonte_incoerente
    dati["controlli"] = {"fatti": len(esiti), "tornano": sum(esiti)}
    dati["pagine_senza_testo"] = senza_testo
    json.dump(dati, open(dest, "w"), ensure_ascii=False, indent=1)

    print("%-44s 4a %2d righe  4b %2d righe  4c %3d CUP  PNRR-S %2d"
          % (os.path.basename(pdf), len(dati["impieghi"]), len(dati["fonti"]),
             len(dati["assegnazioni"]), len(dati["pnrr"])))
    tot = next((r for r in dati["fonti"] if r["rigo"] == "3"), None)
    if tot:
        print("   totale fonti 2022-2026 %.2f, complessivo %.2f mln"
              % (tot["valori"].get("tot", 0), tot["valori"].get("compl", 0)))
    if not dati["fonti"] and senza_testo:
        print("   nessun 4b leggibile: %d pagine senza testo (scansioni)" % senza_testo)
    for n in note:
        print("   NON TORNA: " + n)
    for n in fonte_incoerente:
        print("   (" + n + ")")
    if esiti:
        print("   ESITO: %d controlli, %d tornano" % (len(esiti), sum(esiti)))


if __name__ == "__main__":
    main()
