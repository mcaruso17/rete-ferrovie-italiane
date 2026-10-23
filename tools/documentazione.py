"""La scheda dei documenti dell'aggiornamento 2025 del CdP-I: piattaforma/documenti.html,
pubblicata come documenti.html. Per ogni PDF (contratto, decreto, registrazione,
Relazione informativa e le sue appendici) due righe su cosa contiene, le pagine,
i CUP e gli interventi citati, e le tipologie di quegli interventi.

I conteggi sono quelli del testo, uguali per tutti i documenti: un CUP e' citato
se compare scritto nel PDF (cup-nel-testo.json), un intervento se compare il suo
codice (uno dei 223 delle Tabelle A e B 2025). Citato non vuol dire che il
documento ne dia importi: lo dicono le due righe di descrizione.
La lettura dei PDF e' lenta (l'Appendice 3 ha 400 pagine): i codici trovati
restano in data/documenti-agg2025.json e si rileggono solo se il file manca.

Uso:
  python3 documentazione.py ../data ../piattaforma/documenti.html
"""
import collections
import csv
import html
import json
import os
import re
import sys

from extract_stati import parole
from pdfmini import PDF
from pdftext import extract_page, group_lines

CARTELLA = "documenti/cdpi-agg2025/"
# (file, titolo, descrizione): l'ordine e' quello del pacchetto pubblicato dal MIT
DOCUMENTI = [
    ("CdP_2022-2026_Investimenti_Agg_ 2025.pdf", "Articolato e tabelle",
     "Il contratto vero e proprio: articolato e Tabelle A (in corso e programmatici), B (lotti costruttivi) "
     "e C (opere ultimate), con costo, risorse assegnate per fonte, fabbisogno e speso per intervento."),
    (CARTELLA + "260522_dm_firmato_approvazione_aggiornamento_202_cdp2022_2026_rfi_investimenti.pdf",
     "Decreto di approvazione",
     "Decreto del Ministro delle infrastrutture di concerto con il Ministro dell'economia (n. 112 del "
     "25/05/2026) che approva l'aggiornamento."),
    (CARTELLA + "registrazionefascicolo_220571.pdf", "Registrazione della Corte dei conti",
     "Attestazione dell'Ufficio di controllo della Corte dei conti che il decreto di approvazione e' stato "
     "ammesso alla registrazione."),
    (CARTELLA + "relazione_informativa_agg_2025_v04_clean.pdf", "Relazione informativa (Allegato 1)",
     "Racconta l'aggiornamento: quadro delle risorse, nuove esigenze, rimodulazioni, stato del portafoglio. "
     "Le appendici che seguono sono sue."),
    (CARTELLA + "appendice_1_delibere_cipess_per_progetto.pdf", "Appendice 1: delibere CIPESS per progetto",
     "Per le opere soggette a delibera, l'elenco delle delibere CIPE/CIPESS con data e tipologia "
     "(approvazione, assegnazione, presa d'atto)."),
    (CARTELLA + "appendice_2_lista_cup.pdf", "Appendice 2: dettaglio CUP dei programmi",
     "L'elenco dei CUP dei programmi pluriennali, uno per oggetto, che le Tabelle A e B non stampano. "
     "Senza importi."),
    (CARTELLA + "appendice_3_schede_intervento.pdf", "Appendice 3: schede intervento",
     "Una scheda per intervento: CUP opera per opera con stato e date dell'iter, avanzamento dei programmi "
     "e piano della spesa (costo, risorse, impegni, pagamenti). Senza ripartizione per fonte."),
    (CARTELLA + "appendice_4delta_costi.pdf", "Appendice 4: evoluzione del portafoglio",
     "Per ogni intervento la differenza di costo a vita intera fra 2024 e 2025, scomposta per causa "
     "(variazioni, nuove esigenze, ultimati, riclassifiche), con la motivazione di RFI."),
    (CARTELLA + "appendice_4dossier_delta_costo.pdf", "Appendice 4: dossier ex ante",
     "Dossier sui progetti con forte aumento di costo: obiettivi, storia, descrizione, costo a vita "
     "intera e cause dell'aumento."),
    (CARTELLA + "appendice_5variazione_risorse.pdf", "Appendice 5: variazione delle risorse",
     "Per ogni intervento le coperture per fonte fra 2024 e 2025: risorse precedenti, nuove risorse, "
     "definanziamenti e rimodulazioni."),
    (CARTELLA + "appendice_6_agg_relazione_interventi_dl_43_2013.pdf", "Appendice 6: interventi DL 43/2013",
     "Stato degli interventi finanziati dall'art. 7-ter del DL 43/2013 (aree terremotate del 2012, "
     "Piombino, Expo)."),
    (CARTELLA + "appendice_7_distribuzione_territoriale.pdf", "Appendice 7: distribuzione territoriale",
     "Gli investimenti in corso per regione: riepilogo con le quote ripartite e l'elenco degli interventi "
     "regione per regione."),
    (CARTELLA + "appendice_8_quadro_riepilogativo_delle_opere_incluse_nel_pis.pdf",
     "Appendice 8: opere del Programma infrastrutture strategiche",
     "Le opere della legge obiettivo (PIS) con stato di attuazione, commissariamento, PNRR e delibere."),
    (CARTELLA + "appendice_9_elenco_opere_pnrr_e_pnc.pdf", "Appendice 9: opere PNRR e PNC",
     "Le opere finanziate dal PNRR e dal Piano nazionale complementare, per misura, con le risorse "
     "PNRR, nazionali e UE."),
    (CARTELLA + "appendice_10_docfap_e_quadro_esigenziale.pdf", "Appendice 10: quadro esigenziale e DocFAP",
     "Nota metodologica sul nuovo codice appalti ed elenco degli studi di fattibilita' delle alternative "
     "progettuali. Senza CUP."),
    (CARTELLA + "appendice_11_allegato_indicatori_di_sostenibilit.pdf", "Appendice 11: sviluppo sostenibile",
     "I contratti MIT-RFI e gli obiettivi di sviluppo sostenibile: differenze territoriali, traffico, "
     "emissioni, indicatori. Testo, senza CUP."),
    (CARTELLA + "appendice_12_rimodulazioni.pdf", "Appendice 12: rimodulazioni",
     "Le risorse spostate fra interventi nel 2025, per tipologia di rimodulazione: chi cede e chi riceve."),
]
RE_TOKEN = re.compile(r"[A-Z0-9_]+")


def leggi_codici(percorso, codici):
    """{codice: [pagine]} dei codici intervento scritti nel PDF, e le pagine."""
    doc = PDF(percorso)
    trovati, n = collections.defaultdict(set), 0
    for n, pg in enumerate(doc.pages(), 1):
        for l in group_lines(extract_page(doc, pg)):
            it = l[1] if isinstance(l, tuple) else l
            for _, t, _ in parole(it):
                for tok in RE_TOKEN.findall(t):
                    if tok in codici:
                        trovati[tok].add(n)
    return {c: sorted(p) for c, p in trovati.items()}, n


def main():
    d, out = sys.argv[1], sys.argv[2]
    radice = os.path.join(d, "..")
    interv = {r["codice_intervento"]: r for r in csv.DictReader(open(os.path.join(d, "base-interventi-agg2025.csv"), encoding="utf-8"))}
    perimetro = {r["cup"]: r["perimetro"] for r in csv.DictReader(open(os.path.join(d, "base-cup-agg2025.csv"), encoding="utf-8"))}
    registro = {r["cup"]: r["stato"] for r in csv.DictReader(open(os.path.join(d, "cup-registro.csv"), encoding="utf-8"))}
    nel_testo = json.load(open(os.path.join(d, "cup-nel-testo.json"), encoding="utf-8"))
    per_doc = collections.defaultdict(set)
    for cup, posti in nel_testo.items():
        for f, _ in posti:
            per_doc[f].add(cup)

    cache = os.path.join(d, "documenti-agg2025.json")
    if os.path.exists(cache):
        letti = json.load(open(cache, encoding="utf-8"))
    else:
        letti = {}
        for f, _, _ in DOCUMENTI:
            cod, pagine = leggi_codici(os.path.join(radice, f), set(interv))
            letti[f] = {"pagine": pagine, "codici": cod}
            print("  letto %s: %d pagine, %d interventi" % (f, pagine, len(cod)))
        json.dump(letti, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    righe = []
    for f, titolo, descr in DOCUMENTI:
        cups = per_doc.get(f, set())
        cod = letti[f]["codici"]
        tip = collections.Counter(
            "B" if interv[c]["tabella"].startswith("B") else interv[c]["tipologia_programma"][:1] for c in cod)
        cat = collections.Counter(
            "corso" if perimetro.get(c) in ("Tabelle A e B", "Appendice 2", "Altri documenti dell'aggiornamento")
            else "app3" if perimetro.get(c) == "Solo Appendice 3"
            else "ultimate" if registro.get(c) == "concluso" else "altri" for c in cups)
        righe.append({"file": f, "titolo": titolo, "descr": descr, "pagine": letti[f]["pagine"],
                      "n_cup": len(cups), "cat": cat, "n_int": len(cod), "tip": tip})
    open(out, "w", encoding="utf-8").write(pagina(righe, len(interv)))
    print("documenti.html: %d documenti; %s" % (len(righe), ", ".join(
        "%s %d CUP %d interventi" % (r["titolo"].split(":")[0], r["n_cup"], r["n_int"]) for r in righe)))


ETICHETTE_TIP = [("a", "a programmi"), ("b", "b in esecuzione"), ("c", "c prioritari"),
                 ("d", "d in programma"), ("B", "Tab. B lotti")]


def pagina(righe, n_tot):
    e = html.escape
    def link(f):
        # sul sito i PDF stanno in data/ (quelli della radice) o in data/cdpi-agg2025/
        return "data/" + (f[len("documenti/"):] if f.startswith("documenti/") else f).replace(" ", "%20")
    def cup_txt(r):
        if not r["n_cup"]:
            return "<span class='zero'>nessuno</span>"
        parti = [("corso", "del portafoglio in corso"), ("ultimate", "di opere ultimate"),
                 ("app3", "solo nelle schede"), ("altri", "altri")]
        return "<b>%s</b><span class='det'>%s</span>" % (
            format(r["n_cup"], ",").replace(",", "."),
            "<br>".join("%d %s" % (r["cat"][k], t) for k, t in parti if r["cat"][k]))
    def int_txt(r):
        if not r["n_int"]:
            return "<span class='zero'>nessuno</span>"
        return "<b>%d</b><span class='det'>%s</span>" % (
            r["n_int"], " ".join("<span class='tip t%s' title='%s'>%s %d</span>" % (k, e(t), k, r["tip"][k])
                                 for k, t in ETICHETTE_TIP if r["tip"][k]))
    corpo = "\n".join(
        "<tr><td><a href='%s' target='_blank' rel='noopener'><b>%s</b></a><p>%s</p></td>"
        "<td class='n'>%d</td><td class='n'>%s</td><td class='n'>%s</td></tr>" % (
            link(r["file"]), e(r["titolo"]), e(r["descr"]), r["pagine"], cup_txt(r), int_txt(r)) for r in righe)
    return MODELLO.replace("%%RIGHE%%", corpo).replace("%%NTOT%%", str(n_tot))


MODELLO = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Documenti CdP-I 2025</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&display=swap">
<style>
/* Generata da tools/documentazione.py: non modificare a mano. Stessa grafica di assegnazioni.html. */
:root{color-scheme:light;--bg:#fff;--panel:#f5f6f8;--line:#dde1e7;--ink:#17202b;--ink-2:#4a5565;--ink-3:#6b7585;--link:#0b5bb8;
 --ta:#2a78d6;--tb:#1baf7a;--tc:#eb6834;--td:#8a63d2;--tB:#3d4b5e;
 --f:"Titillium Web","Segoe UI",system-ui,-apple-system,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--f);font-size:16px;line-height:1.45}
a{color:var(--link)}
.wrap{max-width:1100px;margin:0 auto;padding:18px 16px 32px}
h1{font-size:1.5rem;margin:0 0 4px;line-height:1.2}
.intro{color:var(--ink-2);margin:0 0 14px;max-width:880px}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;vertical-align:top;padding:9px 8px;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--ink-2);font-size:.9rem;border-bottom:2px solid var(--line)}
td p{margin:2px 0 0;color:var(--ink-2);font-size:.93rem}
td.n,th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
td.n b{font-size:1.05rem}
.det{display:block;color:var(--ink-3);font-size:.82rem;line-height:1.35}
.zero{color:var(--ink-3)}
.tip{display:inline-block;margin:2px 0 0 3px;padding:0 6px;border-radius:999px;font-size:.78rem;color:#fff}
.ta{background:var(--ta)}.tb{background:var(--tb)}.tc{background:var(--tc)}.td{background:var(--td)}.tB{background:var(--tB)}
.leg{margin:12px 0 0;color:var(--ink-2);font-size:.88rem}
.note{margin-top:18px;color:var(--ink-2);font-size:.9rem;max-width:880px}
@media (max-width:700px){
 thead{display:none}
 table,tbody{display:block}
 tr{display:grid;grid-template-columns:1fr 1fr 1fr;border-bottom:1px solid var(--line);padding:8px 0}
 td{border:0;padding:4px 6px}
 td:first-child{grid-column:1/-1}
 td.n{text-align:left;white-space:normal}
 td.n::before{display:block;content:attr(data-l);color:var(--ink-3);font-size:.78rem}
}
</style>
</head>
<body>
<div class="wrap">
<h1>Documenti del CdP-I 2022-2026, aggiornamento 2025</h1>
<p class="intro">Il pacchetto pubblicato dal MIT (portale Trasparenza, atti di programmazione): contratto, atti di approvazione, Relazione informativa e le sue dodici appendici. Per ogni documento: cosa contiene, quanti CUP e quanti interventi vi sono citati, e di quali tipologie.</p>
<table>
<thead><tr><th>Documento</th><th class="n">Pagine</th><th class="n">CUP citati</th><th class="n">Interventi citati (su %%NTOT%%)</th></tr></thead>
<tbody>
%%RIGHE%%
</tbody>
</table>
<p class="leg">Tipologie: <span class="tip ta">a</span> programmi pluriennali <span class="tip tb">b</span> interventi in esecuzione <span class="tip tc">c</span> interventi prioritari <span class="tip td">d</span> interventi in programma <span class="tip tB">B</span> Tabella B, lotti costruttivi</p>
<p class="note"><b>Come si contano.</b> Un CUP e' citato se compare scritto nel documento; un intervento se compare il suo codice. "Del portafoglio in corso" sono i 990 CUP delle Tabelle A e B, dell'Appendice 2 e del Brennero; "solo nelle schede" i 6 che compaiono solo nell'Appendice 3. Citato non vuol dire che il documento ne dia gli importi: lo dice la descrizione. Le Appendici 10 e 11 non hanno CUP; l'Appendice 5 e la 12 identificano gli interventi solo per codice.</p>
</div>
<script>
// etichette delle celle per la vista a schede su telefono
document.querySelectorAll("tbody tr").forEach(tr=>{const l=["","Pagine","CUP citati","Interventi citati"];tr.querySelectorAll("td").forEach((td,i)=>td.dataset.l=l[i])});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
