"""La spesa dalla Relazione annuale al Parlamento sullo stato di attuazione dei
Contratti di Programma MIT-RFI al 31/12/2024 (Senato, Doc. CXCIX-bis n. 4,
documenti/parlamento/). I contratti danno l'avanzamento cumulato per intervento;
la relazione da' la spesa (contabilizzazioni) anno per anno.

Tre tabelle:
- Investimenti, contabilizzazioni per programma 2019-2024 (p. 125 del PDF). E'
  un'immagine: i valori sono trascritti qui, con i controlli sui totali;
- Servizi, manutenzione straordinaria per annualita' e anno di spesa (p. 38,
  testo);
- Servizi, manutenzione straordinaria per sottosistema, annualita' 2022-2024
  (p. 43) e programmi dell'annualita' 2024 (p. 42), testo.

Uso:
  python3 relazione_parlamento.py app-in.json app-out.json ../data
"""
import csv
import json
import os
import sys

FONTE = {"id": "rel-parl-2024", "file": "parlamento/relazione-parlamento-cdp-2024.pdf",
         "titolo": "Relazione al Parlamento sullo stato di attuazione al 31/12/2024 dei Contratti di Programma MIT-RFI",
         "rif": "Senato della Repubblica, XIX legislatura, Doc. CXCIX-bis n. 4",
         "url": "https://www.senato.it/service/PDF/PDFServer/DF/446732.pdf"}

# p. 125: valore della Sezione 1 (opere in corso finanziate), contabilizzato
# fino al 2018 e per anno 2019-2024, cumulato al 2024, avanzamento % dichiarato
ANNI = [2019, 2020, 2021, 2022, 2023, 2024]
INV = [
    # codice, nome, valore, al 2018, 2019..2024, al 2024, avanzamento %
    ("01", "Sicurezza, adeguamento a nuovi standard e resilienza al climate change", 9848, 3532, [907, 1098, 1225, 459, 349.15, 337], 7907, 80),
    ("02", "Sviluppo tecnologico", 10588, 2866, [387, 364, 420, 389, 529.45, 743], 5698, 54),
    ("03", "Accessibilità stazioni", 2244, 743, [173, 129, 142, 115, 184.90, 274], 1762, 79),
    ("04", "Valorizzazione turistica delle ferrovie minori", 355.41, 47.73, [9.00, 8.78, 14.74, 45.34, 64.90, 48.56], 239, 67),
    ("05", "Valorizzazione delle reti regionali", 6810, 826, [226, 169, 274, 347, 371.62, 493], 2706, 40),
    ("06", "Città metropolitane", 10181, 4729, [240, 208, 368, 419, 298.07, 447], 6710, 66),
    ("07", "Porti e interporti, ultimo/penultimo miglio", 1168, 48, [20, 26, 44, 46, 50.83, 54], 289, 25),
    ("08", "Aeroporti, accessibilità su ferro", 1019, 11, [6, 7, 5, 8, 23.64, 107], 168, 16),
    ("09", "Direttrici di interesse nazionale", 50240, 8592, [876, 1155, 1646, 1522, 2030.67, 2990], 18813, 37),
    ("B", "Investimenti realizzati per lotti costruttivi (Tabella B)", 15164, 2091, [888, 400, 761, 1213, 1509.83, 1967], 8829, 58),
    # le opere ultimate continuano a contabilizzare code di spesa: il totale
    # Investimenti della relazione le comprende
    ("C", "Opere ultimate (Tabella C)", 66169, 66363, [163, 87, 69, 40, 34.61, 55], 66689, 101),
]
# righe di totale della stessa tabella, per il controllo
TOT_CDPI = (173787, 89851, [3896, 3652, 4968, 4602, 5447.66, 7515.19], 119811, 69)
TOT_CDPS = (7380, 4773, [784, 716, 752.04, 1560, 2308.08, 2427], 13320, 180)
TOT_AB = [4679, 4368, 5720, 6162, 7755.75, 9942]

# p. 38: manutenzione straordinaria CdP-S, consuntivi per annualita' e anno di spesa
MS_ANN = [
    # contratto, annualita', importo contrattuale, {anno: speso}, cumulato al 2024
    ("2022-2026", "Prima annualità (2022)", 2225.63, {2022: 1380.84, 2023: 519.16, 2024: 142.26}, 2042.26),
    ("2022-2026", "Seconda annualità (2023)", 2902.86, {2023: 1719.21, 2024: 675.43}, 2394.64),
    ("2022-2026", "Terza annualità (2024)", 2850.00, {2024: 1576.79}, 1576.79),
]
MS_PREC = {"2012-2014": {"importo": 2880.00, "al_2024": 2871.42, 2024: 0.26},
           "2016-2021": {"importo": 4502.00, "al_2024": 4435.77, 2024: 33.01}}
# p. 43: per sottosistema e annualita' (pianificato, impegnato, contabilizzato)
MS_SOTTO = {
    "2022": {"Infrastruttura fisica": (1612.7, 1611.4, 1516.6), "Infrastruttura energetica": (206.4, 205.1, 162.0),
             "Infrastruttura tecnologica": (215.6, 213.4, 181.3), "Supporto manutenzione": (191.0, 186.5, 182.3)},
    "2023": {"Infrastruttura fisica": (2258.3, 2257.2, 1908.3), "Infrastruttura energetica": (211.1, 206.3, 123.3),
             "Infrastruttura tecnologica": (194.0, 191.6, 139.8), "Supporto manutenzione": (239.4, 238.7, 223.3)},
    "2024": {"Infrastruttura fisica": (2129.5, 2108.9, 1212.9), "Infrastruttura energetica": (264.6, 226.4, 63.1),
             "Infrastruttura tecnologica": (212.2, 211.3, 96.9), "Supporto manutenzione": (243.6, 234.7, 203.9)},
}
MS_SOTTO_TOT = {"2022": (2225.6, 2216.4, 2042.3), "2023": (2902.9, 2893.8, 2394.6), "2024": (2850.0, 2781.3, 1576.8)}
# p. 42: annualita' 2024 per programma (costo pianificato, disposto, contabilizzato)
MS_PROG_2024 = [
    ("Infrastruttura fisica", "Armamento", 1477, 1465, 959), ("Infrastruttura fisica", "Opere d'arte", 297, 291, 94),
    ("Infrastruttura fisica", "Sede", 195, 193, 97), ("Infrastruttura fisica", "Obblighi di legge", 47, 47, 12),
    ("Infrastruttura fisica", "Stazioni", 71, 71, 36), ("Infrastruttura fisica", "Mezzi d'opera", 20, 18, 10),
    ("Infrastruttura fisica", "Navigazione", 4, 4, 1), ("Infrastruttura fisica", "Altri asset", 20, 20, 5),
    ("Infrastruttura energetica", "Linea di contatto", 182, 154, 43), ("Infrastruttura energetica", "Luce e forza motrice", 31, 28, 11),
    ("Infrastruttura energetica", "Sottostazioni elettriche", 37, 30, 3), ("Infrastruttura energetica", "Obblighi di legge", 8, 8, 3),
    ("Infrastruttura energetica", "Mezzi d'opera", 6, 6, 3),
    ("Infrastruttura tecnologica", "Sicurezza e segnalamento", 152, 152, 71), ("Infrastruttura tecnologica", "Telecomunicazioni", 58, 58, 26),
    ("Infrastruttura tecnologica", "Obblighi di legge", 2, 1, 0),
    ("Supporto manutenzione", "Aumento di produttività", 215, 215, 192), ("Supporto manutenzione", "Acquisti a rimpiazzo", 28, 19, 12),
]


def controlla():
    """I valori trascritti devono rifare i totali della relazione (arrotondati
    al milione nella tabella stampata)."""
    errori = []
    for i, a in enumerate(ANNI):
        s = sum(r[4][i] for r in INV)
        if abs(s - TOT_CDPI[2][i]) > 6:
            errori.append("Investimenti %d: somma programmi %.2f, totale %.2f" % (a, s, TOT_CDPI[2][i]))
        if abs(TOT_CDPI[2][i] + TOT_CDPS[2][i] - TOT_AB[i]) > 2:
            errori.append("Totale A+B %d" % a)
    for r in INV:
        if r[0] != "C" and abs(r[3] + sum(r[4]) - r[5]) > 6:
            errori.append("cumulato %s: %.2f contro %.2f" % (r[0], r[3] + sum(r[4]), r[5]))
        if abs(r[5] / r[2] * 100 - r[6]) > 1.5:
            errori.append("avanzamento %s" % r[0])
    for k, v in MS_SOTTO.items():
        for j in range(3):
            if abs(sum(x[j] for x in v.values()) - MS_SOTTO_TOT[k][j]) > 0.3:
                errori.append("MS sottosistemi %s col %d" % (k, j))
    for j in range(3):
        if abs(sum(r[2 + j] for r in MS_PROG_2024) - MS_SOTTO_TOT["2024"][j]) > 6:
            errori.append("MS programmi 2024 col %d" % j)
    for r in MS_ANN:
        if abs(sum(r[3].values()) - r[4]) > 0.05:
            errori.append("MS annualita' " + r[1])
    return errori


def main():
    app_in, app_out, cartella = sys.argv[1:4]
    err = controlla()
    if err:
        sys.exit("relazione al Parlamento, valori che non tornano: " + "; ".join(err))
    A = json.load(open(app_in, encoding="utf-8"))
    ms_anni = {a: round(sum(r[3].get(a, 0) for r in MS_ANN), 2) for a in (2022, 2023, 2024)}
    A["relazione_parlamento"] = {
        **FONTE, "al": "31/12/2024", "anni": ANNI,
        "inv": [{"c": r[0], "n": r[1], "valore": r[2], "al2018": r[3], "spesa": r[4], "al2024": r[5], "avanz": r[6]} for r in INV],
        "tot_cdpi": {"valore": TOT_CDPI[0], "spesa": TOT_CDPI[2], "al2024": TOT_CDPI[3], "avanz": TOT_CDPI[4]},
        "tot_cdps": {"spesa": TOT_CDPS[2], "al2024": TOT_CDPS[3]},
        "pag_inv": 125, "pag_ms": [38, 42, 43],
        "ms": {"annualita": [{"contratto": r[0], "n": r[1], "importo": r[2], "spesa": r[3], "al2024": r[4]} for r in MS_ANN],
               "per_anno_2022_26": ms_anni, "precedenti": MS_PREC,
               "sottosistemi": MS_SOTTO, "sottosistemi_tot": MS_SOTTO_TOT,
               "programmi_2024": [{"s": r[0], "p": r[1], "pian": r[2], "disp": r[3], "cont": r[4]} for r in MS_PROG_2024]},
    }
    with open(os.path.join(cartella, "spesa-investimenti-programmi-2019-2024.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["programma", "descrizione", "valore_sezione1_mln", "contabilizzato_fino_al_2018_mln"] +
                    ["contabilizzato_%d_mln" % a for a in ANNI] + ["contabilizzato_al_2024_mln", "avanzamento_pct"])
        for r in INV:
            w.writerow([r[0], r[1], r[2], r[3]] + r[4] + [r[5], r[6]])
    with open(os.path.join(cartella, "manutenzione-straordinaria-2022-2024.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["annualita", "sottosistema", "pianificato_mln", "impegnato_mln", "contabilizzato_mln"])
        for k, v in MS_SOTTO.items():
            for s, x in v.items():
                w.writerow([k, s] + list(x))
    json.dump(A, open(app_out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("relazione al Parlamento 2024: spesa Investimenti %s; manutenzione straordinaria 2022-24 per anno %s; controlli ok"
          % (", ".join("%d %s" % (a, TOT_CDPI[2][i]) for i, a in enumerate(ANNI)), ms_anni))


if __name__ == "__main__":
    main()
