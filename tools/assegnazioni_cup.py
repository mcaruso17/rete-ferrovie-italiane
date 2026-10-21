"""Le assegnazioni dell'ultimo aggiornamento Investimenti: un file per CUP e
uno per intervento.

assegnazioni-interventi-agg2025.csv, una riga per intervento delle Tabelle A
e B: tipologia, classe tipologica, costo, movimenti dell'anno (finanziato
precedente, riduzioni, rimodulazioni, incrementi), assegnate per fonte,
fabbisogno per priorita', speso, numero e lista dei CUP. Sono gli importi
scritti nel contratto.

assegnazioni-cup-agg2025.csv, una riga per CUP (piu' una per ciascuno dei
cinque interventi senza CUP). Un CUP puo' stare sotto piu' interventi: le fasi
di uno stesso progetto (0049A e 0049B), un'opera che e' anche in un programma
(P111 e P194), due programmi (P221 e P222). Fino a tre interventi per CUP,
nelle colonne intervento_1..3 con i loro importi (importi dell'intervento
intero, come nel contratto). Le colonne *_per_cup_mln sono la quota del CUP:
per ogni suo intervento, l'importo diviso per il numero di CUP di
quell'intervento, sommato sugli interventi. E' una convenzione chiesta
dall'utente, non un dato del contratto (le schede dell'Appendice 3 mostrano
CUP dello stesso programma con importi molto diversi: in NA026 da 0,2 a 1.129
mln). Sommate su tutte le righe, le quote ridanno i totali degli interventi.

I CUP vengono dalle tabelle e, per i programmi, dall'Appendice 2 alla
Relazione Informativa (un CUP per oggetto, senza importi). In un caso il CUP
viene da altri documenti dello stesso aggiornamento: CUP_FUORI_TABELLA.

Stato attuativo e fase finanziata vengono da extract_stati.py, opera per
opera (le righe sotto l'intervento). Nel file degli interventi: le sigle di
tutte le opere, la piu' indietro e la piu' avanti, e uno stato di sintesi
(quello comune a tutte le opere, "piu' stati" se differiscono, "non indicato"
per i programmi, che non hanno opere). stati-opere-agg2025.csv ha una riga per
opera. Ordine delle fasi: FAP, PROG, ITER, AN, RE, ES.

Lo stato per CUP viene dall'Appendice 3 (schede intervento,
extract_appendice3.py), l'unico documento che lega il CUP alla singola opera:
le Tabelle A e B stampano i CUP sotto il codice dell'intervento senza dire a
quale opera vanno (P101: un CUP, due opere in RE e ITER). Per i progetti la
scheda da' opera, CUP, stato e date dell'iter; per i programmi sottoprogetto,
CUP, costo, risorse, contabilizzato e stato. La fase finanziata resta un dato
della Tabella A: arriva al CUP abbinando l'opera della scheda a quella della
tabella per nome (o per posizione, se le due liste hanno la stessa lunghezza).
Dove la scheda non ha il CUP, lo stato del CUP e' quello dell'intervento solo
se tutte le sue opere sono nello stesso stato.

Uso:
  python3 assegnazioni_cup.py ../data/cdp-rfi-dataset.json ../data/appendice-cup-agg2025.json \
          ../data/assegnazioni-cup-agg2025.csv ../data/assegnazioni-interventi-agg2025.csv \
          ../data/cup-nel-testo.json ../data/stati-opere-agg2025.json ../data/stati-opere-agg2025.csv \
          ../data/appendice3-agg2025.json ../data ../data/cup-altri-agg2025.csv

Il nono argomento e' la cartella con le altre appendici estratte
(appendiceN-agg2025.json): appendici_cup.py le riduce a colonne per CUP e per
intervento. Il decimo e' il file dei CUP scritti nei documenti
dell'aggiornamento ma fuori dalle Tabelle A e B e dall'Appendice 2 (quasi tutti
opere ultimate della Tabella C, poi CUP dei Servizi nell'Appendice 9 e qualche
CUP che c'e' solo in un'appendice): non hanno assegnazioni nel contratto in
corso, e stanno a parte per non toccare il conteggio e le quote del file
principale. Lo stato viene dal registro dei CUP (cup-registro.csv, accanto).
"""
import csv
import json
import os
import re
import sys
import unicodedata

import appendici_cup
from schema import ALB_CLASSI_TIP, ALB_TABELLE, CLASSI

MAX_INT = 3
FASI = ["FAP", "PROG", "ITER", "AN", "RE", "ES"]
NOMI_FASI = {"FAP": "Valutazione di fattibilita' delle alternative progettuali", "PROG": "Progettazione",
             "ITER": "Iter autorizzativo", "AN": "Attivita' negoziali", "RE": "Realizzazione", "ES": "Esercizio"}
# lo stato come lo scrive l'Appendice 3, ricondotto alle sigle delle Tabelle A
# e B. I programmi usano tre voci sole; "In ultimazione" sono lavori in corso
# di completamento, quindi RE (il testo originale resta nella colonna accanto)
SIGLA_A3 = {"Valutazione di fattibilita'": "FAP", "Progettazione": "PROG", "Iter autorizzativo": "ITER",
            "Attivita' negoziali": "AN", "Realizzazione": "RE", "In ultimazione": "RE", "Esercizio": "ES"}
DATE_ITER = ["prog_preliminare_inizio", "prog_preliminare_fine", "prog_definitivo_inizio",
             "prog_definitivo_fine", "prog_esecutivo_inizio", "prog_esecutivo_fine",
             "attivita_negoziali_inizio", "attivita_negoziali_fine", "esecuzione_inizio",
             "esecuzione_fine", "funzionalita"]
ORIGINE_FUORI = "Altri documenti dell'aggiornamento (non stampato in tabella)"
# CUP che la tabella dell'ultimo aggiornamento non stampa ma che gli altri
# documenti dello stesso aggiornamento attribuiscono all'intervento. A004
# (Galleria di base del Brennero): la Tabella B 2025 (pp. 82 e 127) salta la
# riga del CUP, che c'era nelle Tabelle B 2021, 2022 e 2024; lo stesso CUP sta
# nell'Appendice 1 (delibere CIPESS, p. 2, anche nel titolo della delibera
# 37/2023), nell'Appendice 8 (p. 2) e nella Relazione informativa (pp. 14 e
# 16). Si accetta solo se cup-nel-testo.json lo trova davvero in un documento
# dell'aggiornamento e l'intervento non ha gia' CUP in tabella.
CUP_FUORI_TABELLA = {"A004": "I41J05000020005"}
# gli importi che seguono il CUP; i movimenti dell'anno e le priorita' del
# fabbisogno restano nel file degli interventi, altrimenti per tre interventi
# il file dei CUP passerebbe le ottanta colonne
IMPORTI = ["costo_totale", "risorse_assegnate", "mef", "fsc_pac", "mit", "pnrr", "altro",
           "fabbisogno_totale", "speso"]

COL_INT = [
    "documento", "codice_intervento", "descrizione_intervento", "pagina_pdf", "tabella",
    "tipologia_programma", "lettera_nel_pdf", "programma", "classe_tipologica",
    "n_opere", "stato_sintesi", "stati_attuativi_opere", "stato_meno_avanzato", "stato_piu_avanzato",
    "fasi_finanziate_opere", "n_cup", "cup", "cup_condivisi_con_altri_interventi",
    "costo_totale_mln", "finanziato_precedente_mln", "riduzioni_mln", "rimodulazioni_mln",
    "incrementi_mln", "risorse_assegnate_mln", "mef_mln", "fsc_pac_mln", "mit_mln",
    "pnrr_mln", "altro_mln", "fabbisogno_totale_mln", "fabbisogno_priorita1_mln",
    "fabbisogno_priorita2_mln", "fabbisogno_completamento_mln", "speso_mln", "controllo",
] + appendici_cup.COL_INT
COL_OPERE = [
    "documento", "codice_intervento", "descrizione_intervento", "tabella", "tipologia_programma",
    "classe_tipologica", "descrizione_opera", "fase_finanziata", "fase_finanziata_nome",
    "fase_finanziata_parziale", "project_review", "stato_attuativo", "stato_attuativo_nome",
    "paniere_pnrr", "nuovo_inserimento", "pagina_pdf", "cup_opera_appendice3",
    "stato_attuativo_appendice3", "pagina_appendice_3", "costo_totale_opera_mln",
    "risorse_assegnate_opera_mln", "speso_opera_mln", "n_opere_intervento",
]
COL_CUP = (
    ["documento", "cup", "oggetto_cup", "pagina_appendice_2", "n_interventi",
     "cup_su_piu_interventi", "tipo_condivisione", "tabella", "tipologia_programma",
     "programma", "classe_tipologica", "classificazione_uguale_fra_interventi",
     "stato_attuativo_cup", "stato_attuativo_cup_testo", "fonte_stato_cup", "fase_finanziata_cup",
     "opere_cup", "schede_appendice_3", "pagina_appendice_3", "costo_cup_appendice3_mln",
     "risorse_cup_appendice3_mln", "contabilizzato_cup_appendice3_mln"]
    + ["iter_" + d for d in DATE_ITER]
    + [c % k for k in range(1, MAX_INT + 1) for c in (
        "intervento_%d", "descrizione_intervento_%d", "origine_cup_intervento_%d",
        "pagina_pdf_intervento_%d", "n_cup_intervento_%d", "stato_sintesi_intervento_%d",
        "stati_attuativi_intervento_%d")]
    + ["%s_intervento_%d_mln" % (n, k) for k in range(1, MAX_INT + 1) for n in IMPORTI]
    + ["ripartizione_per_cup"] + ["%s_per_cup_mln" % n for n in IMPORTI]
    + appendici_cup.COL_CUP
    + ["%s_intervento_%d" % (c, k) for k in range(1, MAX_INT + 1) for c in appendici_cup.COL_INT_BREVI]
)


def r2(x):
    return "" if x is None else round(x, 2)


def controllo(s):
    """Le due identita' della riga di Tabella A, come le verifica validate.py:
    fonti = risorse assegnate, costo = risorse assegnate + fabbisogno."""
    if not s.get("fonti"):
        # Tabella B dei contratti che non stampano gli zeri: le colonne vuote
        # spostano fonti e fabbisogni e normalize.py non li legge
        return "fonti e fabbisogno per priorita' non leggibili"
    fin, cos = s.get("finanziato"), s.get("costo")
    fonti = s.get("fonti") or {}
    fab = s.get("fabbisogni") or {}
    note = []
    if fin is None or abs(fin - sum(v or 0 for v in fonti.values())) >= 0.1:
        note.append("fonti diverse dalle risorse assegnate")
    if cos is None or fin is None or abs(cos - fin - sum(v or 0 for v in fab.values())) >= 0.1:
        # succede per gli interventi la cui stima si ferma all'arco di Piano
        note.append("costo diverso da risorse + fabbisogno")
    return "; ".join(note) or "ok"


def ultimo_doc(D):
    return max(D["documenti"], key=lambda d: D["documenti"][d]["ordine"])


def sintesi_stati(opere):
    """Le sigle delle opere di un intervento, in ordine di fase."""
    st = sorted({o["stato_attuativo"] for o in opere if o["stato_attuativo"]}, key=FASI.index)
    fa = sorted({o["fase_finanziata"] for o in opere if o["fase_finanziata"]}, key=FASI.index)
    if not opere:
        # i programmi (classe a) non hanno opere; tre interventi in esecuzione
        # nemmeno (0119, 0263 e P111, che e' "per memoria")
        sint = "non indicato"
    elif len(st) == 1:
        sint = st[0]
    else:
        sint = "piu' stati"
    return {"n_opere": len(opere), "stato_sintesi": sint, "stati_attuativi_opere": "|".join(st),
            "stato_meno_avanzato": st[0] if st else "", "stato_piu_avanzato": st[-1] if st else "",
            "fasi_finanziate_opere": "|".join(fa)}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def sigla_a3(testo):
    t = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    return next((v for k, v in SIGLA_A3.items() if t.startswith(k.replace("'", ""))), "")


def abbina_opere(schede, stati):
    """Opera della scheda (Appendice 3) -> opera della Tabella A, per nome; se
    il nome non basta e le due liste hanno la stessa lunghezza, per posizione.
    Su 237 abbinamenti lo stato coincide in 234: le tre differenze (P248,
    P251, 0298) vengono dalle date diverse dei due documenti."""
    out = {}
    for cod, s in schede.items():
        tab = stati["interventi"].get(cod, {}).get("opere", [])
        for i, o in enumerate(s["opere"]):
            n = norm(o["opera"])
            m = [t for t in tab if norm(t["descrizione"]) == n] or \
                [t for t in tab if norm(t["descrizione"])[:25] == n[:25]]
            if not m and len(tab) == len(s["opere"]):
                m = [tab[i]]
            if not m:
                # la scheda NA026 raccoglie le opere dei sette interventi di
                # Tabella B (0281, 0325, 0361, 0362A/B, A004, I135), che non
                # hanno scheda propria: si cerca lo stesso nome fra tutte le opere
                m = [t for v in stati["interventi"].values() for t in v["opere"] if norm(t["descrizione"]) == n]
                m = m if len(m) == 1 else []
            if m:
                out[(cod, i)] = m[0]
    return out


def base_codice(c):
    # 0049A e 0049B, P238A e P238B: fasi o lotti dello stesso intervento
    return re.sub(r"[A-Z]$", "", c)


def main():
    D = json.load(open(sys.argv[1]))
    app2 = json.load(open(sys.argv[2]))
    out_cup, out_int = sys.argv[3], sys.argv[4]
    nel_testo = json.load(open(sys.argv[5]))
    stati = json.load(open(sys.argv[6]))
    out_opere = sys.argv[7]
    a3 = json.load(open(sys.argv[8]))
    app_int = appendici_cup.per_intervento(sys.argv[9])
    schede = a3["schede"]
    abbinate = abbina_opere(schede, stati)
    # dal CUP alle righe dell'Appendice 3 che lo citano (opere dei progetti e
    # sottoprogetti dei programmi; i subtotali non hanno CUP)
    a3_cup = {}
    for cod, s in schede.items():
        for i, o in enumerate(s["opere"]):
            if o["cup"]:
                tab = abbinate.get((cod, i))
                a3_cup.setdefault(o["cup"], []).append(
                    {"scheda": cod, "nome": o["opera"], "stato": o["stato"], "pagina": o["pagina"],
                     "date": o["date"], "fase": tab["fase_finanziata"] if tab else ""})
        for r in s["avanzamento"]:
            if r["cup"]:
                a3_cup.setdefault(r["cup"], []).append(
                    {"scheda": cod, "nome": r["nome"], "stato": r["stato"], "pagina": r["pagina"],
                     "costo": r["costo"], "risorse": r["risorse"], "contabilizzato": r["contabilizzato"]})
    if stati["doc"] != ultimo_doc(D):
        sys.exit("gli stati sono di %s, l'ultimo aggiornamento e' %s" % (stati["doc"], ultimo_doc(D)))
    ultimo = max(D["documenti"], key=lambda d: D["documenti"][d]["ordine"])
    if app2.get("doc") not in (None, ultimo):
        sys.exit("l'Appendice 2 e' di %s, l'ultimo aggiornamento e' %s" % (app2.get("doc"), ultimo))
    per_cod = {}
    for r in app2["righe"]:
        per_cod.setdefault(r["codice"], []).append(r)

    interventi, tot = [], {"costo": 0.0, "fin": 0.0, "fab": 0.0}
    for p in D["progetti"]:
        s = next((s for s in p["storico"] if s["doc"] == ultimo), None)
        if s is None:
            continue
        cod = p["codice"]
        cups = [(c, "Tabella " + s["tabella"], "", "") for c in (s.get("cups") or [])]
        visti = {c for c, *_ in cups}
        for a in per_cod.get(cod, []):
            if a["cup"] not in visti:
                visti.add(a["cup"])
                cups.append((a["cup"], "Appendice 2", a.get("descr") or "", a.get("p") or ""))
        if cod in CUP_FUORI_TABELLA and not cups:
            c = CUP_FUORI_TABELLA[cod]
            dove = [(f.split("/")[-1], pag) for f, pag in nel_testo.get(c, [])
                    if f.startswith("documenti/cdpi-" + ultimo + "/")]
            if not dove:
                sys.exit("%s: il CUP %s non risulta in nessun documento di %s" % (cod, c, ultimo))
            # nell'oggetto le pagine in cui compare, per poterlo verificare
            cups.append((c, ORIGINE_FUORI, "; ".join("%s p. %s" % d for d in dove), ""))
        t, cl, pn = s["tabella"], s.get("classe"), p.get("programma_num")
        prog, ct = ALB_CLASSI_TIP.get(pn or "", ("", ""))
        fonti = s.get("fonti") or {}
        fab = s.get("fabbisogni") or {}
        tp = (cl + " - " + CLASSI[cl]) if t == "A" and cl in CLASSI else ("Lotti costruttivi" if t == "B" else "")
        if s.get("classe_doc") and t == "A":
            # la tipologia come la stampa il PDF di questo aggiornamento: dal 2024
            # "Interventi in programma" ha la lettera d (normalize.py la chiama e
            # per confrontare i contratti; qui si legge un contratto solo)
            tp = s["classe_doc"] + tp[1:]
        si = sintesi_stati(stati["interventi"].get(cod, {}).get("opere", []))
        interventi.append({**si,
            "documento": ultimo, "codice_intervento": cod, "descrizione_intervento": p["descrizione"],
            "pagina_pdf": s["pagina"], "tabella": t + " - " + ALB_TABELLE.get(t, ""),
            "tipologia_programma": tp, "lettera_nel_pdf": s.get("classe_doc") or "",
            "programma": prog, "classe_tipologica": (pn + " - " + ct) if pn and ct else "",
            "n_cup": len(cups), "_cups": cups,
            "costo_totale_mln": r2(s.get("costo")),
            "finanziato_precedente_mln": r2(s.get("finanziato_precedente")),
            "riduzioni_mln": r2(s.get("riduzioni")), "rimodulazioni_mln": r2(s.get("rimodulazioni")),
            "incrementi_mln": r2(s.get("incrementi")), "risorse_assegnate_mln": r2(s.get("finanziato")),
            "mef_mln": r2(fonti.get("f_mef")), "fsc_pac_mln": r2(fonti.get("f_fsc_pac")),
            "mit_mln": r2(fonti.get("f_mit")), "pnrr_mln": r2(fonti.get("f_pnrr")),
            "altro_mln": r2(fonti.get("f_altro")),
            "fabbisogno_totale_mln": r2(s.get("da_finanziare")),
            "fabbisogno_priorita1_mln": r2(fab.get("fab_priorita1")),
            "fabbisogno_priorita2_mln": r2(fab.get("fab_priorita2")),
            "fabbisogno_completamento_mln": r2(fab.get("fab_completamento")),
            "speso_mln": r2(s.get("avanzamento")), "controllo": controllo(s),
        })
        if t == "A":
            tot["costo"] += s.get("costo") or 0
            tot["fin"] += s.get("finanziato") or 0
            tot["fab"] += s.get("da_finanziare") or 0

    for it in interventi:
        it.update(app_int.get(it["codice_intervento"], {}))
        # il nome dell'intervento dall'Appendice 4: nel dataset la descrizione
        # delle Tabelle A e B ha attaccate le opere stampate sotto (159 su 223,
        # "Potenziamento linea Empoli-Siena Raddoppio Empoli-Granaiolo ... ITER")
        nome = it.pop("_nome", "")
        if nome:
            it["descrizione_intervento"] = re.sub(r"\s+", " ", nome).strip()
    app_cup = appendici_cup.per_cup(sys.argv[9], nel_testo, ultimo)
    # dal CUP agli interventi: le tabelle prima dell'Appendice 2, poi per codice
    per_cup = {}
    for it in interventi:
        for c, orig, ogg, pag in it["_cups"]:
            per_cup.setdefault(c, []).append((it, orig, ogg, pag))
    for c in per_cup:
        per_cup[c].sort(key=lambda x: (x[1] == "Appendice 2", x[0]["codice_intervento"]))
        if len(per_cup[c]) > MAX_INT:
            sys.exit("il CUP %s e' sotto %d interventi: il file ne prevede %d" % (c, len(per_cup[c]), MAX_INT))
    for it in interventi:
        it["cup"] = "|".join(c for c, *_ in it["_cups"])
        it["cup_condivisi_con_altri_interventi"] = "|".join(
            c + " (" + ",".join(x[0]["codice_intervento"] for x in per_cup[c] if x[0] is not it) + ")"
            for c, *_ in it["_cups"] if len(per_cup[c]) > 1)

    def riga(cup, voci):
        """voci: [(intervento, origine, oggetto, pagina)], una per intervento."""
        r = {k: "" for k in COL_CUP}
        it0 = voci[0][0]
        r.update({"documento": ultimo, "cup": cup, "n_interventi": len(voci),
                  "cup_su_piu_interventi": "si" if len(voci) > 1 else "no",
                  "oggetto_cup": next((o for _, _, o, _ in voci if o), ""),
                  "pagina_appendice_2": next((p for _, _, _, p in voci if p), ""),
                  "tabella": it0["tabella"], "tipologia_programma": it0["tipologia_programma"],
                  "programma": it0["programma"], "classe_tipologica": it0["classe_tipologica"]})
        if len(voci) > 1:
            cod = [v[0]["codice_intervento"] for v in voci]
            orig = [v[1] for v in voci]
            r["tipo_condivisione"] = (
                "fasi o lotti dello stesso intervento" if len({base_codice(x) for x in cod}) == 1
                else "in piu' programmi (Appendice 2)" if all(o == "Appendice 2" for o in orig)
                else "opera in tabella e anche in un programma (Appendice 2)" if "Appendice 2" in orig
                else "interventi diversi in tabella")
            r["classificazione_uguale_fra_interventi"] = "si" if len(
                {(v[0]["tipologia_programma"], v[0]["classe_tipologica"]) for v in voci}) == 1 else "no"
        a = a3_cup.get(cup, []) if cup else []
        if a:
            sig = sorted({sigla_a3(x["stato"]) for x in a if sigla_a3(x["stato"])}, key=FASI.index)
            fasi = sorted({x["fase"] for x in a if x.get("fase")}, key=FASI.index)
            r.update({"stato_attuativo_cup": sig[0] if len(sig) == 1 else "piu' stati" if sig else "",
                      "stato_attuativo_cup_testo": " | ".join(dict.fromkeys(x["stato"] for x in a)),
                      "fonte_stato_cup": "Appendice 3 (schede intervento)",
                      "fase_finanziata_cup": fasi[0] if len(fasi) == 1 else "|".join(fasi),
                      "opere_cup": " | ".join(dict.fromkeys(x["nome"] for x in a)),
                      "schede_appendice_3": "|".join(dict.fromkeys(x["scheda"] for x in a)),
                      "pagina_appendice_3": "|".join(dict.fromkeys(str(x["pagina"]) for x in a))})
            if any("costo" in x for x in a):
                for n in ("costo", "risorse", "contabilizzato"):
                    r[n + "_cup_appendice3_mln"] = round(sum(x[n] for x in a if n in x), 2)
            date = {tuple(sorted(x["date"].items())) for x in a if "date" in x}
            if len(date) == 1:
                # le date dell'iter solo se tutte le opere del CUP hanno le stesse
                r.update({"iter_" + k: v for k, v in date.pop()})
        elif cup and len(voci) == 1 and voci[0][0]["n_cup"] == 1 and voci[0][0]["n_opere"]:
            # unico CUP dell'intervento: vale per tutte le sue opere (A004,
            # Brennero, che nella scheda NA026 ha i lotti senza CUP)
            it = voci[0][0]
            r.update({"stato_attuativo_cup": it["stato_sintesi"],
                      "stato_attuativo_cup_testo": it["stati_attuativi_opere"],
                      "fase_finanziata_cup": it["fasi_finanziate_opere"],
                      "fonte_stato_cup": "Tabella %s: unico CUP dell'intervento, stati delle sue opere"
                                         % it["tabella"][:1]})
        elif cup and len({v[0]["stato_sintesi"] for v in voci}) == 1 and voci[0][0]["stato_sintesi"] in FASI:
            r.update({"stato_attuativo_cup": voci[0][0]["stato_sintesi"],
                      "fonte_stato_cup": "Tabella %s: stato comune a tutte le opere dell'intervento"
                                         % voci[0][0]["tabella"][:1]})
        r.update(app_cup.get(cup, {}) if cup else {})
        for k, (it, _, _, _) in enumerate(voci, 1):
            for c in appendici_cup.COL_INT_BREVI:
                r["%s_intervento_%d" % (c, k)] = it.get(c, "")
        quota = {n: 0.0 for n in IMPORTI}
        parti = []
        for k, (it, orig, _, _) in enumerate(voci, 1):
            n = max(1, it["n_cup"])
            r.update({"intervento_%d" % k: it["codice_intervento"],
                      "descrizione_intervento_%d" % k: it["descrizione_intervento"],
                      "origine_cup_intervento_%d" % k: orig, "pagina_pdf_intervento_%d" % k: it["pagina_pdf"],
                      "n_cup_intervento_%d" % k: it["n_cup"],
                      "stato_sintesi_intervento_%d" % k: it["stato_sintesi"],
                      "stati_attuativi_intervento_%d" % k: it["stati_attuativi_opere"]})
            for nome in IMPORTI:
                v = it[nome + "_mln"]
                r["%s_intervento_%d_mln" % (nome, k)] = v
                quota[nome] += (v or 0) / n
            parti.append("%s / %d CUP" % (it["codice_intervento"], n) if n > 1 else
                         "%s intero" % it["codice_intervento"])
        for nome in IMPORTI:
            r[nome + "_per_cup_mln"] = round(quota[nome], 4)
        unico = len(voci) == 1 and voci[0][0]["n_cup"] <= 1
        r["ripartizione_per_cup"] = ("nessun CUP: importi dell'intervento" if not cup else
                                     "coincide con l'intervento (un solo CUP)" if unico else
                                     " + ".join(parti) + " (convenzione, non nel contratto)")
        return r

    righe = [riga(c, voci) for c, voci in per_cup.items()]
    righe += [riga("", [(it, "nessun CUP nel contratto", "", "")]) for it in interventi if not it["_cups"]]
    righe.sort(key=lambda r: (r["tabella"], r["classe_tipologica"], r["intervento_1"], r["cup"]))

    with open(out_cup, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COL_CUP)
        w.writeheader()
        w.writerows(righe)
    opere = []
    per_int = {it["codice_intervento"]: it for it in interventi}
    a3_opera = {}
    for (cod, i), tab in abbinate.items():
        o = schede[cod]["opere"][i]
        a3_opera[id(tab)] = {"cup_opera_appendice3": o["cup"], "stato_attuativo_appendice3": o["stato"],
                             "pagina_appendice_3": o["pagina"]}
    for cod, v in stati["interventi"].items():
        it = per_int[cod]
        for o in v["opere"]:
            imp = o["importi"]
            opere.append({
                "documento": ultimo, "codice_intervento": cod, "descrizione_intervento": it["descrizione_intervento"],
                "tabella": it["tabella"], "tipologia_programma": it["tipologia_programma"],
                "classe_tipologica": it["classe_tipologica"], "descrizione_opera": o["descrizione"],
                "fase_finanziata": o["fase_finanziata"], "fase_finanziata_nome": NOMI_FASI.get(o["fase_finanziata"], ""),
                "fase_finanziata_parziale": "si" if o["fase_parziale"] else "no",
                "project_review": "si" if o["project_review"] else "no",
                "stato_attuativo": o["stato_attuativo"], "stato_attuativo_nome": NOMI_FASI.get(o["stato_attuativo"], ""),
                "paniere_pnrr": "si" if o["paniere_pnrr"] else "no",
                "nuovo_inserimento": "si" if o["nuovo_inserimento"] else "no",
                "pagina_pdf": o["pagina"], **a3_opera.get(id(o), {}),
                # importi per opera: li stampa solo la Tabella B
                "costo_totale_opera_mln": r2(imp.get("costo_totale")),
                "risorse_assegnate_opera_mln": r2(imp.get("finanziato_totale")),
                "speso_opera_mln": r2(imp.get("avanzamento")),
                "n_opere_intervento": len(v["opere"]),
            })
    with open(out_opere, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COL_OPERE)
        w.writeheader()
        w.writerows(opere)
    with open(out_int, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COL_INT, extrasaction="ignore")
        w.writeheader()
        w.writerows(interventi)

    # controlli: gli interventi tornano con gli aggregati della Tabella A, e le
    # quote per CUP sommate su tutte le righe ridanno i totali degli interventi
    agg = D["aggregati"][ultimo]
    for a, b, n in ((tot["costo"], agg["costo"], "costo"), (tot["fin"], agg["finanziato"], "assegnate"),
                    (tot["fab"], agg["da_finanziare"], "fabbisogno")):
        if abs(a - b) > 0.5:
            sys.exit("Tabella A, %s: %.2f contro %.2f degli aggregati" % (n, a, b))
    for nome in IMPORTI:
        a = sum(r[nome + "_per_cup_mln"] for r in righe)
        b = sum(it[nome + "_mln"] or 0 for it in interventi)
        if abs(a - b) > 0.5:
            sys.exit("quote per CUP di %s: %.2f contro %.2f degli interventi" % (nome, a, b))
    # le appendici 4 e 5 tornano con la tabella: costo e risorse del 2025
    for it in interventi:
        c = it["codice_intervento"]
        if it.get("costo_agg2024_mln") is not None and it["costo_totale_mln"] is not None and \
                abs(it["costo_agg2024_mln"] + it["variazione_costo_2024_2025_mln"] - it["costo_totale_mln"]) > 0.05:
            sys.exit("Appendice 4, %s: costo 2024 + variazioni diverso dal costo in tabella" % c)
        if it.get("risorse_agg2024_mln") is not None and \
                abs(it["risorse_agg2024_mln"] + it["variazione_risorse_2024_2025_mln"] - (it["risorse_assegnate_mln"] or 0)) > 0.05:
            sys.exit("Appendice 5, %s: risorse 2024 + variazioni diverse dalle assegnate in tabella" % c)
    # i sottoprogetti di ogni programma sommano al costo dell'intervento
    for cod, s in schede.items():
        foglie = sum(x["costo"] for x in s["avanzamento"] if not x["subtotale"])
        if s["avanzamento"] and abs(foglie - (per_int[cod]["costo_totale_mln"] or 0)) > 0.5:
            sys.exit("Appendice 3, %s: sottoprogetti %.2f contro il costo %.2f della tabella"
                     % (cod, foglie, per_int[cod]["costo_totale_mln"]))
    con_cup = [r for r in righe if r["cup"]]
    fuori = sorted(set(a3_cup) - {r["cup"] for r in con_cup})
    print("  stato per CUP: %d dall'Appendice 3, %d dallo stato comune dell'intervento, %d senza; "
          "CUP dell'Appendice 3 assenti da tabelle e Appendice 2: %s" % (
              sum(1 for r in con_cup if r["fonte_stato_cup"].startswith("Appendice 3")),
              sum(1 for r in con_cup if r["fonte_stato_cup"].startswith("Tabella")),
              sum(1 for r in con_cup if not r["stato_attuativo_cup"]), ", ".join(fuori) or "nessuno"))
    print("  stato attuativo dei CUP: " + ", ".join("%s %d" % (k, sum(1 for r in con_cup if r["stato_attuativo_cup"] == k))
                                                   for k in FASI + ["piu' stati", ""]))
    # i CUP dei documenti dell'aggiornamento fuori dalle tabelle e dall'Appendice 2
    out_altri = sys.argv[10]
    reg = {r["cup"]: r for r in csv.DictReader(open(os.path.join(sys.argv[9], "cup-registro.csv"), encoding="utf-8"))}
    in_file = {r["cup"] for r in con_cup}
    a3_solo = {x["cup"]: (cod, x.get("opera") or x.get("nome"), x["stato"], x["pagina"])
               for cod, s in a3["schede"].items() for x in s["opere"] + s["avanzamento"] if x["cup"]}
    altri = []
    for c, v in sorted(app_cup.items()):
        if c in in_file or "citato_in_documenti_agg2025" not in v:
            continue
        g = reg.get(c, {})
        r = {"documento": ultimo, "cup": c, "stato_registro": g.get("stato", "non nel registro dei CUP"),
             "parte": g.get("parte", ""), "fonte_registro": g.get("fonte_principale", ""),
             "descrizione": g.get("descrizione", ""), "opere_ultimate_voce": g.get("opere_ultimate_voce", ""),
             "opere_ultimate_edizione": g.get("opere_ultimate_edizione", ""),
             "data_messa_in_esercizio": g.get("data_messa_in_esercizio", ""),
             "interventi_contratti_precedenti": g.get("interventi_contratti_precedenti", ""),
             # J58E22000260001: l'Appendice 2 lo da' al programma A2012, che nelle
             # Tabelle A e B 2025 non c'e'; l'Appendice 3 lo mette sotto A2001B
             "programma_appendice_2": g.get("programmi_appendice_2", ""), **v}
        if c in a3_solo:
            cod, nome, st, pag = a3_solo[c]
            r.update({"scheda_appendice_3": cod, "opera_appendice_3": nome, "stato_attuativo_appendice_3": st,
                      "pagina_appendice_3": pag})
            if not r["descrizione"]:
                r["descrizione"] = nome
        if not r["descrizione"]:
            r["descrizione"] = v.get("pnrr_pnc_voce") or v.get("pis_descrizione") or v.get("dl43_intervento") or ""
        altri.append(r)
    col_altri = (["documento", "cup", "stato_registro", "parte", "fonte_registro", "descrizione",
                  "opere_ultimate_voce", "opere_ultimate_edizione", "data_messa_in_esercizio",
                  "interventi_contratti_precedenti", "programma_appendice_2", "scheda_appendice_3", "opera_appendice_3",
                  "stato_attuativo_appendice_3", "pagina_appendice_3"] + appendici_cup.COL_CUP)
    with open(out_altri, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=col_altri, extrasaction="ignore")
        w.writeheader()
        w.writerows(altri)
    print("%s: %d CUP dei documenti dell'aggiornamento fuori da Tabelle A, B e Appendice 2 (%s)" % (
        out_altri, len(altri), ", ".join("%s %d" % (s, sum(1 for r in altri if r["stato_registro"] == s))
                                         for s in sorted({r["stato_registro"] for r in altri}))))
    cond = [r for r in righe if r["cup_su_piu_interventi"] == "si"]
    print("%s: %d righe, %d CUP distinti, %d su piu' interventi, %d interventi senza CUP" % (
        out_cup, len(righe), sum(1 for r in righe if r["cup"]), len(cond),
        sum(1 for r in righe if not r["cup"])))
    print("  tipi di condivisione: " + ", ".join("%s %d" % (t, sum(1 for r in cond if r["tipo_condivisione"] == t))
                                                   for t in sorted({r["tipo_condivisione"] for r in cond})))
    print("%s: %d opere; stato di sintesi degli interventi: %s" % (out_opere, len(opere), ", ".join(
        "%s %d" % (k, sum(1 for it in interventi if it["stato_sintesi"] == k))
        for k in FASI + ["piu' stati", "non indicato"])))
    print("%s: %d interventi; Tabella A costo %.2f, assegnate %.2f, fabbisogno %.2f, uguali agli aggregati; "
          "quote per CUP ok" % (out_int, len(interventi), tot["costo"], tot["fin"], tot["fab"]))


if __name__ == "__main__":
    main()
