"""Compone il documento HTML completo per l'hosting statico.

`piattaforma/index.html` e' il sorgente della piattaforma cosi' com'e' pubblicata
come Artifact, dove l'intestazione del documento viene aggiunta dalla piattaforma
stessa. Un hosting statico non fa nulla del genere: senza <head> la pagina resta
senza viewport (illeggibile da telefono), senza lingua e senza anteprima quando
il link viene condiviso. Questo script aggiunge quell'involucro, tenendo un solo
sorgente invece di due copie da riallineare a mano.
"""
import sys, re, html

SORGENTE, DESTINAZIONE = sys.argv[1], sys.argv[2]
SITO = sys.argv[3] if len(sys.argv) > 3 else \
    "https://mcaruso17.github.io/rete-ferrovie-italiane/"

DESCRIZIONE = ("I sei Contratti di Programma MIT-RFI dal 2017 al 2025 letti riga "
               "per riga: costo, risorse assegnate e fabbisogno residuo di ogni "
               "intervento, opere ultimate e capitoli di bilancio.")

frammento = open(SORGENTE, encoding="utf-8").read()

m = re.search(r"<title>(.*?)</title>", frammento, re.S)
titolo = html.unescape(m.group(1)).strip() if m else "Binario Contabile"
if m:
    frammento = frammento[:m.start()] + frammento[m.end():]

# favicon come SVG inline: nessun file da servire a parte
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E"
           "%F0%9F%9A%86%3C/text%3E%3C/svg%3E")

# lo stesso azzeramento che la piattaforma Artifact applica alle sue pagine,
# perche' il documento si comporti allo stesso modo ospitato altrove
RESET = """
    :root { color-scheme: light;
      padding-top: env(safe-area-inset-top, 0px);
      padding-bottom: env(safe-area-inset-bottom, 0px); }
    body { margin: 0; font: 14px/1.5 system-ui, sans-serif; background: #f7f7f5; }
    img { max-width: 100%; }
    [hidden] { display: none !important; }
"""

doc = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{titolo}</title>
<meta name="description" content="{descr}">
<link rel="canonical" href="{sito}">
<link rel="icon" href="{favicon}">
<meta property="og:type" content="website">
<meta property="og:title" content="{titolo}">
<meta property="og:description" content="{descr}">
<meta property="og:url" content="{sito}">
<meta property="og:locale" content="it_IT">
<meta name="twitter:card" content="summary">
<style>{reset}</style>
</head>
<body>
{corpo}
</body>
</html>
""".format(titolo=html.escape(titolo), descr=html.escape(DESCRIZIONE),
           sito=html.escape(SITO), favicon=FAVICON, reset=RESET,
           corpo=frammento.strip())

open(DESTINAZIONE, "w", encoding="utf-8").write(doc)
print("%s -> %s (%.0f KB)" % (SORGENTE, DESTINAZIONE, len(doc) / 1024))
