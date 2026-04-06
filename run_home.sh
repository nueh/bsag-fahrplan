#!/bin/bash
# Generiert JSON-Dateien für die home.html-Anzeige (Arensburgstraße & Kurfürstenallee)
# In Crontab eintragen (jede Minute):
#   * * * * * /pfad/zu/bsag-fahrplan/run_home.sh

DIR="$(cd "$(dirname "$0")" && pwd)"

python3 "$DIR/run_hafas.py" -q "HB Arensburgstraße" -f "$DIR/arensburg.json"
python3 "$DIR/run_hafas.py" -q "HB Kurfürstenallee" -f "$DIR/kurfuerst.json"
