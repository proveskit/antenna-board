#!/bin/sh
# Rebuild antenna_top_cap_v3.kicad_pcb from the V2d board and the turnstile board. Run from antenna_top_cap_v3/.
set -e
KPY=${KPY:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3}
FPDIR=${FPDIR:-/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints}
TURN_REV=${TURN_REV:-3ed57c5}  # Turnstile-Test-Board, PragunB 2026-05-17
TMP=$(mktemp -d)
git show "$TURN_REV:proves_canted_turnstile/proves_canted_turnstile.kicad_pcb" > "$TMP/turnstile.kicad_pcb"
sed 's/antenna_top_cap_v2d/antenna_top_cap_v3/g' ../antenna_top_cap_v2d/antenna_top_cap_v2d.kicad_pcb > "$TMP/base.kicad_pcb"
cp antenna_top_cap_v3.kicad_pro "$TMP/base.kicad_pro"  # pcbnew saves the loaded board's project settings next to the output
cp antenna_top_cap_v3.kicad_dru "$TMP/base.kicad_dru"
kicad-cli sch export netlist --format kicadxml -o "$TMP/net.xml" antenna_top_cap_v3.kicad_sch >/dev/null
"$KPY" tools/build_v3.py "$TMP/base.kicad_pcb" "$TMP/turnstile.kicad_pcb" "$TMP/net.xml" "$FPDIR" antenna_top_cap_v3.kicad_pcb
rm -rf "$TMP"
