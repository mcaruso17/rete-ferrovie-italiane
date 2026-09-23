#!/bin/sh
# Ricostruisce dati e sito dai PDF. Da eseguire dalla cartella tools/.
set -e
mkdir -p raw extra
for spec in \
  "../CdP_2017-2021_Investimenti.pdf|cdp2017" \
  "../CdP_2017-2021_Investimenti_Agg2020-2021.pdf|agg2021" \
  "../CdP_2022-2026_Investimenti.pdf|cdp2022" \
  "../CdP_2022-2026_Investimenti_Agg2023.pdf|agg2023" \
  "../CdP_2022-2026_Investimenti_Agg2024.pdf|agg2024" \
  "../CdP_2022-2026_Investimenti_Agg_ 2025.pdf|agg2025"; do
  f="${spec%|*}"; id="${spec#*|}"
  python3 extract.py "$f" "$id" "raw/$id.json"
  python3 extract_extra.py "$f" "$id" "extra/$id.json"
done
python3 normalize.py raw extra ../data/cdp-rfi-dataset.json

# i dati devono tornare con i totali stampati nei PDF prima di finire nel sito
python3 validate.py ../data/cdp-rfi-dataset.json | tee ../data/validazione.txt

python3 build_app.py ../data/cdp-rfi-dataset.json /tmp/app-base.json

# geografia: confini regionali ISTAT e attribuzione dedotta dai nomi
GEO=${GEO:-/home/user/openpolis/geojson-italy/geojson}
if [ -d "$GEO" ]; then
  python3 build_mappa.py "$GEO/limits_IT_regions.geojson" ../data/mappa-regioni.json 0.012 0.004
  python3 geo.py "$GEO/limits_IT_municipalities.geojson" "$GEO/limits_IT_provinces.geojson" \
    /tmp/app-base.json ../data/mappa-regioni.json /tmp/app-geo.json
  # i comuni nominati nei titoli delle opere, sulla stessa proiezione
  python3 comuni.py "$GEO/limits_IT_municipalities.geojson" "$GEO/limits_IT_provinces.geojson" \
    /tmp/app-geo.json ../data/mappa-regioni.json /tmp/app-comuni.json
  # la rete vera, sulla stessa proiezione. La geometria e' versionata: qui non
  # si legge nessun PBF, quindi resta tutto nella libreria standard
  if [ -f ../data/rete-ferroviaria.geojson ]; then
    python3 build_rete.py ../data/rete-ferroviaria.geojson ../data/mappa-regioni.json \
      /tmp/app-comuni.json /tmp/app-rete.json
    # l'aggancio intervento-linea: una deduzione, non un dato dei contratti.
    # Viene dopo comuni.py perche' usa i comuni nominati come seconda prova.
    python3 aggancio.py ../data/linee-ferroviarie.geojson ../data/mappa-regioni.json \
      /tmp/app-rete.json ../data/cdp-rfi-app.json
  else
    echo "data/rete-ferroviaria.geojson assente: pagina Rete ferroviaria non aggiornata" >&2
    cp /tmp/app-comuni.json ../data/cdp-rfi-app.json
  fi
else
  echo "confini ISTAT assenti in $GEO: mappa, regioni e comuni non aggiornati" >&2
  cp /tmp/app-base.json ../data/cdp-rfi-app.json
fi
# i CSV dei comuni leggono l'app appena costruita, quindi vengono dopo
python3 export_csv.py ../data/cdp-rfi-dataset.json ../data

# la piattaforma e' un file unico con i dati incorporati
python3 inject_data.py ../piattaforma/index.html ../data/cdp-rfi-app.json
echo "fatto"
