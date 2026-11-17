#!/bin/sh
# Rebuild antenna_top_cap_v2d.kicad_pcb from the V2c board: rename, place, route. Run from antenna_top_cap_v2d/.
set -e
KPY=${KPY:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3}
FPDIR=${FPDIR:-/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints}
TMP=$(mktemp -d)
sed 's/antenna_top_cap_v2c/antenna_top_cap_v2d/g' ../antenna_top_cap_v2c/antenna_top_cap_v2c.kicad_pcb > "$TMP/base.kicad_pcb"
cp antenna_top_cap_v2d.kicad_pro "$TMP/base.kicad_pro"
kicad-cli sch export netlist --format kicadxml -o "$TMP/net.xml" antenna_top_cap_v2d.kicad_sch >/dev/null
"$KPY" tools/place_charger.py "$TMP/base.kicad_pcb" "$TMP/net.xml" "$FPDIR" antenna_top_cap_v2d.kicad_pcb
"$KPY" tools/route_charger.py antenna_top_cap_v2d.kicad_pcb
rm -rf "$TMP"
