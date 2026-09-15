"""Mappatura delle colonne di Tabella A per ciascun Contratto di Programma.

Le posizioni sono state ricavate dai bordi destri delle colonne stampate e
verificate con le identita' contabili del documento:
  finanziato_totale = somma delle fonti
  finanziato_totale = finanziato_precedente + riduzioni + rimodulazioni + incrementi
  costo_totale      = finanziato_totale + somma dei fabbisogni residui
Il report di validazione (validate.py) misura quante righe le rispettano.
"""

DOCS = {
    "cdp2017": {
        "titolo": "CdP 2017-2021 (contratto base)",
        "file": "CdP_2017-2021_Investimenti.pdf",
        "periodo": "2017-2021", "anno": 2017, "ordine": 1,
        "precedente": "CdP-I 2016",
        "avanz_al": None,
    },
    "agg2021": {
        "titolo": "CdP 2017-2021 - aggiornamento 2020-2021",
        "file": "CdP_2017-2021_Investimenti_Agg2020-2021.pdf",
        "periodo": "2017-2021", "anno": 2021, "ordine": 2,
        "precedente": "CdP-I agg. 2018-2019",
        "avanz_al": "03-2021",
    },
    "cdp2022": {
        "titolo": "CdP 2022-2026 (contratto base)",
        "file": "CdP_2022-2026_Investimenti.pdf",
        "periodo": "2022-2026", "anno": 2022, "ordine": 3,
        "precedente": "CdP-I agg. 2020-2021",
        "avanz_al": "05-2022",
    },
    "agg2023": {
        "titolo": "CdP 2022-2026 - aggiornamento 2023",
        "file": "CdP_2022-2026_Investimenti_Agg2023.pdf",
        "periodo": "2022-2026", "anno": 2023, "ordine": 4,
        "precedente": "CdP-I 2022-2026",
        "avanz_al": "03-2023",
    },
    "agg2024": {
        "titolo": "CdP 2022-2026 - aggiornamento 2024",
        "file": "CdP_2022-2026_Investimenti_Agg2024.pdf",
        "periodo": "2022-2026", "anno": 2024, "ordine": 5,
        "precedente": "CdP-I agg. 2023",
        "avanz_al": "03-2024",
    },
    "agg2025": {
        "titolo": "CdP 2022-2026 - aggiornamento 2025",
        "file": "CdP_2022-2026_Investimenti_Agg_ 2025.pdf",
        "periodo": "2022-2026", "anno": 2025, "ordine": 6,
        "precedente": "CdP-I agg. 2024",
        "avanz_al": "03-2025",
    },
}

# indice colonna -> campo. I fabbisogni portano l'orizzonte temporale stampato.
TABELLA_A = {
    "cdp2017": {
        "ncols": 17,
        "map": {
            0: "opere_costo", 1: "costo_totale", 2: "finanziato_precedente",
            3: "riduzioni_rimodulazioni", 4: "incrementi",
            5: "finanziato_totale",
            6: "f_mef", 7: "f_fsc", 8: "f_mit", 9: "f_ue", 10: "f_altro",
            11: "fab_2018", 12: "fab_2019", 13: "fab_2020", 14: "fab_2021",
            15: "fab_2022_2026", 16: "fab_oltre_2026",
        },
        "fabbisogni": ["fab_2018", "fab_2019", "fab_2020", "fab_2021",
                       "fab_2022_2026", "fab_oltre_2026"],
        "fonti": ["f_mef", "f_fsc", "f_mit", "f_ue", "f_altro"],
        "breve": ["fab_2018", "fab_2019", "fab_2020", "fab_2021"],
        "medio": ["fab_2022_2026"], "lungo": ["fab_oltre_2026"],
    },
    "agg2021": {
        "ncols": 15,
        "map": {
            0: "costo_totale", 1: "finanziato_precedente", 2: "avanzamento",
            3: "riduzioni", 4: "rimodulazioni", 5: "incrementi",
            6: "finanziato_totale",
            7: "f_mef", 8: "f_fsc_pac", 9: "f_mit", 10: "f_pnrr", 11: "f_altro",
            12: "fab_2017_2021", 13: "fab_2022_2026", 14: "fab_oltre_2026",
        },
        "fabbisogni": ["fab_2017_2021", "fab_2022_2026", "fab_oltre_2026"],
        "fonti": ["f_mef", "f_fsc_pac", "f_mit", "f_pnrr", "f_altro"],
        "breve": ["fab_2017_2021"], "medio": ["fab_2022_2026"],
        "lungo": ["fab_oltre_2026"],
    },
    "cdp2022": {
        "ncols": 16,
        "map": {
            0: "costo_totale", 1: "finanziato_precedente", 2: "avanzamento",
            3: "riduzioni", 4: "rimodulazioni", 5: "incrementi",
            6: "finanziato_totale",
            7: "f_mef", 8: "f_fsc_pac", 9: "f_mit", 10: "f_pnrr", 11: "f_altro",
            12: "fab_2023", 13: "fab_2024_2026", 14: "fab_2027_2031",
            15: "fab_oltre_2031",
        },
        "fabbisogni": ["fab_2023", "fab_2024_2026", "fab_2027_2031",
                       "fab_oltre_2031"],
        "fonti": ["f_mef", "f_fsc_pac", "f_mit", "f_pnrr", "f_altro"],
        "breve": ["fab_2023", "fab_2024_2026"], "medio": ["fab_2027_2031"],
        "lungo": ["fab_oltre_2031"],
    },
    "agg2024": {
        "ncols": 15,
        "map": {
            0: "costo_totale", 1: "finanziato_precedente", 2: "avanzamento",
            3: "riduzioni", 4: "rimodulazioni", 5: "incrementi",
            6: "finanziato_totale",
            7: "f_mef", 8: "f_fsc_pac", 9: "f_mit", 10: "f_pnrr", 11: "f_altro",
            12: "fab_priorita1", 13: "fab_priorita2", 14: "fab_completamento",
        },
        "fabbisogni": ["fab_priorita1", "fab_priorita2", "fab_completamento"],
        "fonti": ["f_mef", "f_fsc_pac", "f_mit", "f_pnrr", "f_altro"],
        "breve": ["fab_priorita1"], "medio": ["fab_priorita2"],
        "lungo": ["fab_completamento"],
    },
    "agg2025": {
        "ncols": 15,
        "map": {
            0: "costo_totale", 1: "finanziato_precedente", 2: "avanzamento",
            3: "riduzioni", 4: "rimodulazioni", 5: "incrementi",
            6: "finanziato_totale",
            7: "f_mef", 8: "f_fsc_pac", 9: "f_mit", 10: "f_pnrr", 11: "f_altro",
            12: "fab_priorita1", 13: "fab_priorita2", 14: "fab_completamento",
        },
        "fabbisogni": ["fab_priorita1", "fab_priorita2", "fab_completamento"],
        "fonti": ["f_mef", "f_fsc_pac", "f_mit", "f_pnrr", "f_altro"],
        "breve": ["fab_priorita1"], "medio": ["fab_priorita2"],
        "lungo": ["fab_completamento"],
    },
}

ETICHETTE = {
    "costo_totale": "Costo totale intervento",
    "opere_costo": "Costo opere / consuntivo",
    "finanziato_precedente": "Finanziato nel CdP precedente (proforma)",
    "avanzamento": "Avanzamento lavori (consuntivo)",
    "riduzioni": "Riduzioni", "rimodulazioni": "Rimodulazioni",
    "riduzioni_rimodulazioni": "Riduzioni e rimodulazioni",
    "incrementi": "Incrementi",
    "finanziato_totale": "Risorse assegnate (Sezione 1, opere in corso finanziate)",
    "f_mef": "Stato - MEF", "f_fsc": "Stato - FSC", "f_fsc_pac": "Stato - FSC/PAC",
    "f_mit": "Stato - MIT/MIMS", "f_pnrr": "PNRR nuovi progetti",
    "f_ue": "UE (inclusa quota nazionale)",
    "f_altro": "Altro (PON-FSR, CEF, EE.LL., ...)",
}

STATO_ATTUATIVO = {
    "FAP": "Valutazione fattibilità alternative progettuali",
    "SF": "Studio/progetto di fattibilità",
    "PFTE": "Progetto di fattibilità tecnico-economica",
    "PP": "Progettazione preliminare",
    "PD": "Progettazione definitiva",
    "PE": "Progettazione esecutiva",
    "AN": "Attività negoziali",
    "RE": "Realizzazione",
    "ES": "Esercizio",
    "PRV": "Project review",
}


# I nomi dei programmi cambiano formulazione tra un Contratto e l'altro e sulla
# pagina sono troncati alla prima riga. Qui sono ricondotti alla numerazione
# ufficiale della Tavola 1bis, conservando a parte la dicitura originale.
PROGRAMMI = {
    "Programmi prioritari ferrovie - Sicurezza, adeguamento a nuovi":
        ("01", "Sicurezza e resilienza al climate change"),
    "Programmi prioritari ferrovie - Sicurezza, ambiente ed":
        ("01", "Sicurezza e resilienza al climate change"),
    "Programmi prioritari ferrovie - Sviluppo tecnologico":
        ("02", "Sviluppo tecnologico"),
    "Programmi prioritari ferrovie - Tecnologie per la circolazione e":
        ("02", "Sviluppo tecnologico"),
    "Programmi prioritari ferrovie - Accessibilità stazioni":
        ("03", "Accessibilità stazioni"),
    "Programmi prioritari ferrovie - Valorizzazione turistica delle":
        ("04", "Valorizzazione turistica ferrovie minori"),
    "Programmi prioritari ferrovie - Valorizzazione delle reti regionali":
        ("05", "Valorizzazione reti regionali"),
    "Programmi città metropolitane":
        ("06", "Città metropolitane"),
    "Programma porti e interporti - Ultimo/penultimo miglio":
        ("07", "Porti e interporti, ultimo miglio"),
    "Programma aeroporti - Accessibilità su ferro":
        ("08", "Aeroporti, accessibilità su ferro"),
    "Interventi prioritari ferrovie - direttrici di interesse nazionale":
        ("09", "Direttrici di interesse nazionale"),
    "Sviluppo infrastrutturale Rete AV/AC Torino-Milano-":
        ("10", "Rete AV/AC Torino-Milano-Napoli"),
}

CLASSI = {
    "a": "Programmi pluriennali di interventi",
    "b": "Interventi in esecuzione",
    "c": "Interventi prioritari",
    "d": "Interventi in progettazione",
    "e": "Interventi in programma",
}
