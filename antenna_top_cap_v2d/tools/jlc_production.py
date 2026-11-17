#!/usr/bin/env python3
"""Write JLCPCB BOM + CPL the way kicad-jlcpcb-tools 2026.04.03 does (run with KiCad's Python).

Usage: jlc_production.py <board.kicad_pcb> <project.db> <corrections.csv> <out dir> <name>
Mirrors fabrication.py from that release: CPL position = pad bounding-box centre, Y negated,
bottom rotation = (180 - rot) % 360, then the first matching correction (reference, value,
footprint name; anchored match before unanchored) is added. BOM groups by LCSC number (value/footprint when there is none).
"""
import csv
import re
import sqlite3
import sys

import pcbnew

BOARD, DB, CORR, OUT, NAME = sys.argv[1:6]
b = pcbnew.LoadBoard(BOARD)
rows = {r[0]: r for r in sqlite3.connect(DB).execute(
    "select reference, value, footprint, lcsc, exclude_from_bom, exclude_from_pos from part_info")}
corrections = [(r[0], int(r[1])) for r in csv.reader(open(CORR)) if r and not r[0].startswith("#")]


def correction(fp):
    for name in (fp.GetReference(), fp.GetValue(), str(fp.GetFPID().GetLibItemName())):
        for regex, rot in corrections:
            if re.search(f"(?:{regex})$", name):
                return rot
        for regex, rot in corrections:
            if re.search(regex, name):
                return rot
    return 0


fps = sorted(b.GetFootprints(), key=lambda f: f.GetReference())
missing = [f.GetReference() for f in fps if f.GetReference() not in rows and not f.GetReference().startswith(("G", "#"))]
assert not missing, f"refs missing from project.db: {missing}"

with open(f"{OUT}/CPL-{NAME}.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
    for fp in fps:
        r = rows.get(fp.GetReference())
        if not r or r[5] == 1 or fp.IsDNP():
            continue
        pads = list(fp.Pads())
        bb = pads[0].GetBoundingBox()
        for p in pads:
            bb.Merge(p.GetBoundingBox())
        c = bb.GetCenter()
        bottom = fp.GetLayer() != pcbnew.F_Cu
        rot = fp.GetOrientationDegrees()
        if bottom:
            rot = (180 - rot) % 360
        rot = (rot + correction(fp)) % 360
        w.writerow([r[0], r[1], r[2], pcbnew.ToMM(c.x), -pcbnew.ToMM(c.y), rot, "bottom" if bottom else "top"])

groups = {}
for fp in fps:
    r = rows.get(fp.GetReference())
    if not r or r[4] == 1 or fp.IsDNP():
        continue
    # One BOM line per LCSC part: JLC's matcher unticks lines that repeat an LCSC number.
    key = r[3] or (r[1], r[2])
    groups.setdefault(key, {"val": r[1], "fp": r[2], "lcsc": r[3] or "", "refs": []})["refs"].append(r[0])
with open(f"{OUT}/BOM-{NAME}.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC", "Quantity"])
    for g in sorted(groups.values(), key=lambda g: g["refs"][0]):
        w.writerow([g["val"], ",".join(g["refs"]), g["fp"], g["lcsc"], len(g["refs"])])
print("wrote BOM and CPL for", NAME)
