"""Le appendici alla Relazione Informativa dell'aggiornamento 2025 portate sul
CUP e sull'intervento, per i file delle assegnazioni (assegnazioni_cup.py).

Ogni appendice e' estratta dal suo script (extract_appendiceN.py) in
data/appendiceN-agg2025.json; qui si leggono e si riducono a colonne:

- per CUP: Appendice 1 (delibere CIPESS), 3 (piano della spesa delle opere del
  CUP: costo, risorse, impegni, pagamenti), 6 (DL 43/2013), 8 (opere della
  legge obiettivo), 9 (PNRR e PNC), e i documenti dell'aggiornamento in cui il
  CUP e' scritto (cup-nel-testo.json);
- per intervento: Appendice 4 (variazione del costo 2024-2025), 5
  (variazione delle risorse per fonte), 7 (regioni), 12 (rimodulazioni) e la
  somma PNRR/PNC dell'Appendice 9 per riferimento CdP.

Gli importi sono quelli scritti: quando un CUP sta su piu' righe di una stessa
appendice (J41H01000080008, tre tratte della Napoli-Bari nell'Appendice 9) si
sommano e il testo elenca le righe.
"""
import json
import os
import re
import unicodedata

NOMI_DOC = {
    "CdP_2022-2026_Investimenti_Agg_ 2025.pdf": "CdP-I agg. 2025",
    "relazione_informativa_agg_2025_v04_clean.pdf": "Relazione informativa",
}


def carica(cartella, n):
    p = os.path.join(cartella, "appendice%s-agg2025.json" % n)
    return json.load(open(p))


def r2(x):
    return "" if x is None else round(x, 2)


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def unici(v):
    return list(dict.fromkeys(x for x in v if x))


def nome_doc(f):
    f = f.split("/")[-1]
    if f in NOMI_DOC:
        return NOMI_DOC[f]
    m = re.match(r"appendice_(\d+)", f)
    return ("Appendice " + m.group(1) + (" (dossier)" if "dossier" in f else "")) if m else f


COL_CUP = [
    "citato_in_documenti_agg2025",
    # Appendice 3, piano della spesa (progetti): somma delle opere del CUP
    "spesa_opere_cup_costo_mln", "spesa_opere_cup_risorse_mln", "spesa_opere_cup_fabbisogno_mln",
    "spesa_opere_cup_ogv_lavori_mln", "spesa_opere_cup_ogv_somme_a_disposizione_mln",
    "spesa_opere_cup_impegni_mln", "spesa_opere_cup_pagamenti_mln", "spesa_opere_cup_nota",
    # Appendice 9
    "pnrr_pnc_sezione", "pnrr_pnc_misura", "pnrr_clp", "pnrr_pnc_voce", "pnrr_pnc_rif_cdp",
    "pnrr_totale_mln", "pnrr_progetti_in_essere_mln", "pnrr_nuovi_progetti_mln",
    "pnrr_altri_finanziamenti_nazionali_mln", "pnrr_altri_finanziamenti_ue_mln",
    "pnrr_totale_risorse_disponibili_mln", "pnc_totale_mln", "pagina_appendice_9",
    # Appendice 1
    "cipess_n_delibere", "cipess_delibere", "cipess_ultima_delibera", "cipess_n_approvazioni_progettuali",
    "cipess_n_assegnazioni_risorse", "cipess_n_vincoli_esproprio_rinnovo", "cipess_n_raccomandazioni",
    "cipess_npp", "cipess_note", "pagina_appendice_1",
    # Appendice 8
    "pis_descrizione", "pis_pnrr", "pis_commissariato", "pis_stato_attuazione", "pis_conclusi",
    "pis_in_corso_di_realizzazione", "pis_in_progettazione", "pis_cipess", "pis_note", "pagina_appendice_8",
    # Appendice 6
    "dl43_intervento", "dl43_cup_sulla_stessa_riga", "dl43_costo_totale_mln", "dl43_risorse_mln",
    "dl43_risorse_stato_dl43_2013_mln", "dl43_risorse_altro_mln", "dl43_contabilizzato_al_2023_mln",
    "dl43_contabilizzazioni_2024_mln", "dl43_contabilizzazioni_2025_e_oltre_mln",
]

# per intervento: nel file degli interventi tutte, nel file dei CUP le prime
# cinque per ciascuno dei suoi interventi (_intervento_k)
COL_INT_BREVI = ["regioni_appendice7", "variazione_costo_2024_2025_mln", "motivazione_variazione_costo",
                 "variazione_risorse_2024_2025_mln", "rimodulazioni_2025_netto_mln"]
COL_INT = COL_INT_BREVI + [
    "costo_agg2024_mln", "costo_ultimati_mln", "costo_riclassifiche_mln", "costo_variazioni_costo_perimetro_mln",
    "costo_nuove_esigenze_mln", "costo_adeguamenti_tariffari_mln",
    "risorse_agg2024_mln", "risorse_ultimati_mln", "risorse_riclassifiche_errata_corrige_mln",
    "risorse_riduzioni_mln", "incrementi_mef_legge_bilancio_2025_dl_superbonus_mln", "incrementi_mef_altro_mln",
    "incrementi_mit_prosecuzione_opere_olimpiadi_mln", "incrementi_fsc_ue_altro_mln", "incrementi_pnrr_mln",
    "rimodulazioni_mef_mln", "rimodulazioni_altro_mln", "nuovo_inserimento_2025",
    "rimodulazioni_2025_beneficiari_mln", "rimodulazioni_2025_cedenti_mln", "rimodulazioni_2025_tipologie",
    "pnrr_totale_appendice9_mln", "pnc_totale_appendice9_mln",
]


def per_cup(cartella, nel_testo, ultimo):
    """{cup: {colonna: valore}} dalle appendici che scrivono il CUP."""
    out = {}

    def riga(c):
        return out.setdefault(c, {})

    # documenti dell'aggiornamento in cui il CUP e' scritto, con le pagine
    for c, dove in nel_testo.items():
        pag = {}
        for f, p in dove:
            if f.startswith("documenti/cdpi-" + ultimo + "/") or "Agg_ 2025" in f:
                pag.setdefault(nome_doc(f), []).append(p)
        if pag:
            riga(c)["citato_in_documenti_agg2025"] = "; ".join(
                "%s p. %s" % (d, ", ".join(map(str, sorted(set(p))))) for d, p in pag.items())

    # Appendice 3: piano della spesa per opera, sommato sulle opere del CUP.
    # Solo se ogni opera del CUP ha la sua riga nel piano della spesa
    a3 = carica(cartella, 3)["schede"]
    opere_cup = {}
    for cod, s in a3.items():
        spesa = {norm(r["nome"]): r for r in s.get("spesa", [])}
        for o in s["opere"]:
            if o["cup"]:
                opere_cup.setdefault(o["cup"], []).append((cod, o["opera"], spesa.get(norm(o["opera"]))))
    for c, l in opere_cup.items():
        if all(x[2] for x in l):
            r = riga(c)
            for k in ("costo", "risorse", "fabbisogno", "ogv_lavori", "ogv_somme_a_disposizione", "impegni", "pagamenti"):
                r["spesa_opere_cup_%s_mln" % k] = r2(sum(x[2][k] for x in l))
            r["spesa_opere_cup_nota"] = ("%d opere" % len(l)) if len(l) > 1 else "una opera"
        else:
            riga(c)["spesa_opere_cup_nota"] = "opere senza riga nel piano della spesa: " + "; ".join(
                x[1] for x in l if not x[2])

    # Appendice 9
    for r in carica(cartella, 9)["righe"]:
        o = riga(r["cup"])
        for k, v in (("pnrr_pnc_sezione", r["sezione"]), ("pnrr_pnc_misura", r["misura"]), ("pnrr_clp", r["clp"]),
                     ("pnrr_pnc_voce", r["intervento"]), ("pnrr_pnc_rif_cdp", r["rif_cdp"]),
                     ("pagina_appendice_9", str(r["pagina"]))):
            o.setdefault("_" + k, []).append(v)
        for k, src in (("pnrr_totale_mln", ["pnrr_totale"]), ("pnrr_progetti_in_essere_mln", ["pnrr_progetti_in_essere"]),
                       ("pnrr_nuovi_progetti_mln", ["pnrr_nuovi_progetti_cdpi", "pnrr_nuovi_progetti_cdps", "pnrr_nuovi_progetti"]),
                       ("pnrr_altri_finanziamenti_nazionali_mln", ["altri_finanziamenti_nazionali"]),
                       ("pnrr_altri_finanziamenti_ue_mln", ["altri_finanziamenti_ue"]),
                       ("pnrr_totale_risorse_disponibili_mln", ["totale_risorse_disponibili"]),
                       ("pnc_totale_mln", ["pnc_totale"])):
            v = [r[s] for s in src if r.get(s) is not None]
            if v:
                o[k] = r2((o.get(k) or 0) + sum(v))

    # Appendice 1: una riga per delibera
    for d in carica(cartella, 1)["delibere"]:
        o = riga(d["cup"])
        o.setdefault("_delibere", []).append(d)
    for c, o in out.items():
        dl = o.pop("_delibere", None)
        if dl:
            dl.sort(key=lambda d: d["data"][6:] + d["data"][3:5] + d["data"][:2])
            o["cipess_n_delibere"] = len(dl)
            o["cipess_delibere"] = "; ".join("%s/%s del %s" % (d["numero"], d["data"][6:], d["data"]) for d in dl)
            u = dl[-1]
            o["cipess_ultima_delibera"] = "%s/%s del %s: %s" % (u["numero"], u["data"][6:], u["data"], u["titolo_delibera"])
            for k, t in (("cipess_n_approvazioni_progettuali", "approvazione_progettuale"),
                         ("cipess_n_assegnazioni_risorse", "assegnazione_risorse"),
                         ("cipess_n_vincoli_esproprio_rinnovo", "vincolo_esproprio_rinnovo"),
                         ("cipess_n_raccomandazioni", "raccomandazioni")):
                o[k] = sum(1 for d in dl if d[t])
            o["cipess_npp"] = "|".join(unici(d["npp"] for d in dl))
            o["cipess_note"] = "; ".join(unici(d["note"] for d in dl))
            o["pagina_appendice_1"] = "|".join(unici(str(d["pagina"]) for d in dl))
        for k in ("pnrr_pnc_sezione", "pnrr_pnc_misura", "pnrr_clp", "pnrr_pnc_voce", "pnrr_pnc_rif_cdp",
                  "pagina_appendice_9"):
            v = o.pop("_" + k, None)
            if v is not None:
                o[k] = " | ".join(unici(v))

    # Appendice 8
    for p in carica(cartella, 8)["opere"]:
        o = riga(p["cup"])
        o.update({"pis_descrizione": p["descrizione"], "pis_pnrr": p["pnrr"], "pis_commissariato": p["commissariato"],
                  "pis_stato_attuazione": p["stato_attuazione"], "pis_conclusi": p["conclusi"],
                  "pis_in_corso_di_realizzazione": p["in_corso_di_realizzazione"],
                  "pis_in_progettazione": p["in_progettazione"], "pis_cipess": p["cipess"], "pis_note": p["note"],
                  "pagina_appendice_8": p["pagina"]})

    # Appendice 6: gli importi sono della riga; con due CUP sulla stessa riga
    # si ripetono su entrambi e la colonna lo dice
    for r in carica(cartella, 6)["righe"]:
        for c in r["cup"]:
            o = riga(c)
            o.update({"dl43_intervento": r["intervento"],
                      "dl43_cup_sulla_stessa_riga": "|".join(x for x in r["cup"] if x != c),
                      "dl43_costo_totale_mln": r["costo_totale"], "dl43_risorse_mln": r["risorse"],
                      "dl43_risorse_stato_dl43_2013_mln": r["risorse_stato_dl43_2013"],
                      "dl43_risorse_altro_mln": r["risorse_altro"],
                      "dl43_contabilizzato_al_2023_mln": r["contabilizzato_al_2023"],
                      "dl43_contabilizzazioni_2024_mln": r["contabilizzazioni_2024"],
                      "dl43_contabilizzazioni_2025_e_oltre_mln": r["contabilizzazioni_2025_e_oltre"]})
    return out


def per_intervento(cartella):
    """{codice: {colonna: valore}} dalle appendici per intervento."""
    out = {}

    def riga(c):
        return out.setdefault(c, {})

    a4 = carica(cartella, 4)
    for r in a4["righe"]:
        riga(r["c"]).update({
            "costo_agg2024_mln": r["costo_prec"], "costo_ultimati_mln": r["ultimati"],
            "costo_riclassifiche_mln": r["riclassifiche"], "costo_variazioni_costo_perimetro_mln": r["variazioni_costo"],
            "costo_nuove_esigenze_mln": r["nuove_esigenze"], "costo_adeguamenti_tariffari_mln": r["adeguamenti_tariffari"],
            "variazione_costo_2024_2025_mln": r["variazioni_totali"], "motivazione_variazione_costo": r.get("mot") or ""})
    a5 = carica(cartella, 5)
    for r in a5["righe"]:
        o = riga(r["codice"])
        o.update({"risorse_agg2024_mln": r["risorse_agg2024"], "risorse_ultimati_mln": r["ultimati"],
                  "risorse_riclassifiche_errata_corrige_mln": r["riclassifiche_errata_corrige"],
                  "risorse_riduzioni_mln": r["riduzioni"],
                  "variazione_risorse_2024_2025_mln": r["totale_variazioni"],
                  "nuovo_inserimento_2025": "si" if r["nuovo_inserimento"] else "no"})
        for k in ("incrementi_mef_legge_bilancio_2025_dl_superbonus", "incrementi_mef_altro",
                  "incrementi_mit_prosecuzione_opere_olimpiadi", "incrementi_fsc_ue_altro", "incrementi_pnrr",
                  "rimodulazioni_mef", "rimodulazioni_altro"):
            o[k + "_mln"] = r[k]
    a7 = carica(cartella, 7)
    nomi = {r["istat"]: r["regione"] for r in a7["riepilogo"]}
    reg = {}
    for ist, l in a7["per_regione"].items():
        for x in l:
            reg.setdefault(x["c"], []).append(nomi.get(ist, ist))
    for x in a7["diffusi"]:
        reg.setdefault(x["c"], []).append("Intera rete (programma diffuso)")
    for c, l in reg.items():
        riga(c)["regioni_appendice7"] = "|".join(sorted(set(l)))
    for r in carica(cartella, 12)["righe"]:
        o = riga(r["codice"])
        for k, s in (("rimodulazioni_2025_netto_mln", "totale"), ("rimodulazioni_2025_beneficiari_mln", "beneficiari"),
                     ("rimodulazioni_2025_cedenti_mln", "cedenti")):
            o[k] = r2((o.get(k) or 0) + r[s])
        o["rimodulazioni_2025_tipologie"] = "|".join(unici((o.get("rimodulazioni_2025_tipologie") or "").split("|")
                                                            + [r["tipologia"]]))
    for r in carica(cartella, 9)["righe"]:
        if r["rif_cdp"] and r["rif_cdp"] != "CdP-Servizi":
            o = riga(r["rif_cdp"])
            if r.get("pnrr_totale") is not None:
                o["pnrr_totale_appendice9_mln"] = r2((o.get("pnrr_totale_appendice9_mln") or 0) + r["pnrr_totale"])
            if r.get("pnc_totale") is not None:
                o["pnc_totale_appendice9_mln"] = r2((o.get("pnc_totale_appendice9_mln") or 0) + r["pnc_totale"])
    return out
