#!/usr/bin/env python3
"""Add the V2d charger + SWD footprints to the board from the schematic netlist (run with KiCad's Python).

Usage: place_charger.py <base V2c-derived board> <netlist.xml> <kicad footprints dir> <out board>
Starts from the base board every run, so reruns are idempotent.
"""
import sys
import xml.etree.ElementTree as ET

import pcbnew

BASE, NETLIST, FPDIR, BOARD = sys.argv[1:5]
mm = pcbnew.FromMM

# ref: (x, y, orientation deg, side)  side F = inner face, B = outer face
PLACE = {
    "U201": (157.5, 85.8, 0, "F"),
    "L201": (163.4, 81.8, 270, "F"),
    "C202": (159.3, 81.3, 270, "F"),
    "C201": (154.6, 81.2, 180, "F"),
    "C204": (162.4, 87.8, 270, "F"),
    "C205": (164.45, 87.8, 270, "F"),
    "C206": (166.5, 87.8, 270, "F"),
    "C207": (162.0, 91.3, 270, "F"),
    "F201": (165.4, 91.6, 0, "F"),
    "C208": (167.3, 83.3, 180, "F"),
    "C209": (158.9, 90.1, 270, "F"),
    "R201": (157.6, 89.6, 270, "F"),
    "R202": (156.55, 89.6, 270, "F"),
    "R203": (154.3, 86.54, 90, "F"),
    "R204": (153.5, 88.6, 270, "F"),
    "R205": (152.45, 89.6, 270, "F"),
    "J203": (166.6, 95.45, 180, "B"),
    "D202": (157.2, 82.4, 0, "B"),
    "R207": (160.3, 82.4, 180, "B"),
    "R206": (163.6, 81.6, 0, "B"),
    "D201": (166.9, 81.6, 180, "B"),
    "J201": (205.5, 95.6, 0, "F"),
    "J202": (205.5, 102.2, 0, "B"),
}

root = ET.parse(NETLIST).getroot()
comps = {}
for c in root.iter("comp"):
    comps[c.get("ref")] = c
pinnet = {}
for n in root.iter("net"):
    for node in n.iter("node"):
        pinnet[(node.get("ref"), node.get("pin"))] = n.get("name")

b = pcbnew.LoadBoard(BASE)
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)


def net(name):
    ni = b.FindNet(name)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
    return ni


for ref, (x, y, rot, side) in PLACE.items():
    c = comps[ref]
    lib, name = c.findtext("footprint").split(":")
    fp = IO.FootprintLoad(f"{FPDIR}/{lib}.pretty", name)
    fp.SetReference(ref)
    b.Add(fp)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetValue(c.findtext("value"))
    fields = {f.get("name"): f.text or "" for f in c.iter("field")}
    fields["Datasheet"] = c.findtext("datasheet") or fields.get("Datasheet", "")
    fields["Description"] = c.findtext("description") or fields.get("Description", "")
    for fname in ("LCSC", "MPN", "Description", "Datasheet"):
        if fields.get(fname):
            fld = fp.GetField(fname) if fp.HasField(fname) else None
            if fld is None:
                fld = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal() if hasattr(fp, "GetNextFieldOrdinal") else 0, fname)
                fp.Add(fld)
            fld.SetText(fields[fname])
            fld.SetVisible(False)
    sp = c.find("sheetpath").get("tstamps")
    fp.SetPath(pcbnew.KIID_PATH(sp + c.findtext("tstamps")))
    if fp.IsFlipped() != (side == "B"):
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    fp.SetOrientationDegrees(rot)
    for p in fp.Pads():
        nn = pinnet.get((ref, p.GetNumber()))
        p.SetNet(net(nn) if nn else b.FindNet(""))
    fp.Reference().SetVisible(ref.startswith("J"))

j12 = b.FindFootprintByReference("J12")
for p in j12.Pads():
    if p.GetNumber() in ("A4", "A9", "B4", "B9"):
        p.SetNet(net(pinnet[("J12", p.GetNumber())]))

b.Save(BOARD)
print("placed", len(PLACE))
