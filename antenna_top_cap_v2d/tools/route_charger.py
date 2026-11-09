#!/usr/bin/env python3
"""Route the V2d charger + SWD nets, update silk, refill zones (run with KiCad's Python after place_charger.py).

Usage: route_charger.py <board.kicad_pcb>
Every segment is listed here so a reviewer can rerun and diff it. Rerun place_charger.py first: it starts
from the V2c-derived base, so this script never sees its own earlier copper.
"""
import sys

import pcbnew

BOARD = sys.argv[1]
b = pcbnew.LoadBoard(BOARD)
mm = pcbnew.FromMM
CHG = "/Charger & SWD/"
LAYER = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu, "I2": pcbnew.In2_Cu}


def pad(ref, num):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            q = p.GetPosition()
            return (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))
    raise KeyError((ref, num))


def netinfo(name):
    n = b.FindNet(CHG + name) or b.FindNet(name)
    assert n is not None, name
    return n


def track(net, layer, width, *pts):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
        t.SetWidth(mm(width))
        t.SetLayer(LAYER[layer])
        t.SetNet(netinfo(net))
        b.Add(t)


def via(net, at, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(at[0]), mm(at[1])))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetWidth(mm(dia))
    v.SetDrill(mm(drill))
    v.SetNet(netinfo(net))
    b.Add(v)


U = lambda n: pad("U201", n)

# VBUS: J204 (charge-only USB-C, outer face) -> B trunk -> via up to the charger.
VD = (156.4, 79.5)
track("VBUS_CHG", "F", 0.25, U("23"), (156.75, 82.95), (156.4, 82.6))
track("VBUS_CHG", "F", 0.5, (156.4, 82.6), VD)
track("VBUS_CHG", "F", 0.5, (156.4, 81.2), pad("C201", "1"))
via("VBUS_CHG", VD, 0.8, 0.4)
track("VBUS_CHG", "B", 0.4, pad("J204", "A4"), (172.95, 72.3))
track("VBUS_CHG", "B", 1.0, (172.95, 72.3), (172.95, 79.5), VD)
track("VBUS_CHG", "B", 0.4, pad("J204", "A9"), (177.85, 76.0), (173.4, 76.0), (172.95, 76.45))
track("VBUS_CHG", "B", 0.3, (162.775, 79.5), pad("R206", "1"))

# J204 CC pull-downs on the inner face; GND pads to the shield like J12.
track("Net-(J204-CC1)", "B", 0.25, pad("J204", "A5"), (174.15, 71.9), (175.0, 71.9), (175.5, 72.4))
via("Net-(J204-CC1)", (175.5, 72.4))
track("Net-(J204-CC1)", "F", 0.25, (175.5, 72.4), pad("R208", "1"))
track("Net-(J204-CC2)", "B", 0.25, pad("J204", "B5"), (177.15, 72.05), (176.6, 72.6))
via("Net-(J204-CC2)", (176.6, 72.6))
track("Net-(J204-CC2)", "F", 0.25, (176.6, 72.6), (177.0, 73.0), pad("R209", "1"))
track("GND", "B", 0.25, pad("J204", "A1"), (171.08, 69.8))
track("GND", "B", 0.25, pad("J204", "A12"), (179.72, 69.8))

# D+ tied to D- around the top-left corner.
track("Net-(U201-D+)", "F", 0.15, U("24"), (156.25, 83.2), (155.0, 83.2), (155.0, 84.55), U("1"))

# PMID: pins -> C202 -> L201 pad 1.
track("PMID", "F", 0.25, U("22"), (157.25, 82.9), (157.75, 82.9), U("21"))
track("PMID", "F", 0.5, (157.5, 82.9), (157.5, 80.35), pad("C202", "1"), pad("L201", "1"))

# SW: pins -> L201 pad 2 -> C208 (bootstrap).
track("SW", "F", 0.25, U("18"), (160.2, 84.55), (160.2, 85.05), U("17"))
track("SW", "F", 0.5, (160.2, 84.8), (160.6, 84.8), (161.6, 83.8), pad("L201", "2"))
VSW = (161.0, 84.4)
via("SW", VSW)
track("SW", "B", 0.4, VSW, pad("C208", "2"))

# SYS: pins -> C204..C206.
track("SYS", "F", 0.25, U("16"), (160.2, 85.55), (160.2, 86.05), U("15"))
track("SYS", "F", 0.6, (160.2, 85.8), (161.4, 85.8), (161.75, 86.125), pad("C204", "1"), pad("C206", "1"))

# GND returns: SYS caps share pads, vias to In1; GND pins into the EP; C202 to pins 19/20.
track("GND", "F", 0.6, pad("C204", "2"), pad("C206", "2"))
for x in (162.6, 165.0, 167.1):
    track("GND", "F", 0.4, (x, 89.075), (x, 90.25))
    via("GND", (x, 90.25))
track("GND", "F", 0.3, U("19"), (158.75, 82.6))
track("GND", "F", 0.3, U("20"), (158.25, 83.0), (158.75, 83.0))
for n in ("19", "20"):
    track("GND", "F", 0.2, U(n), (U(n)[0], 84.7))
for n in ("3", "4", "5"):
    track("GND", "F", 0.2, U(n), (156.4, U(n)[1]))
for x in (156.85, 158.15):
    for y in (85.0, 86.7):
        via("GND", (x, y))
for ref, num in (("U201", "25"), ("C204", "2"), ("C205", "2"), ("C206", "2"), ("C202", "2")):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

# BAT: pins -> C207 -> F201 -> J203 (CHG LINK) -> Dir_Chrg_In (J203 pin 2 sits on the existing track).
track("CHG_BAT", "F", 0.25, U("14"), (160.2, 86.55), (160.2, 87.05), U("13"))
track("CHG_BAT", "F", 0.5, (160.2, 86.8), (161.0, 86.8), (161.0, 91.1), (165.0, 91.1), pad("F201", "1"))
VBAT = (162.0, 91.1)
via("CHG_BAT", VBAT)
track("CHG_BAT", "B", 0.5, VBAT, pad("C207", "1"))
VG7 = (166.2, 92.4)
track("GND", "B", 0.4, pad("C207", "2"), VG7)
via("GND", VG7)
track("CHG_FUSED", "F", 0.5, pad("F201", "2"), (167.8, 94.3), (167.3, 94.8), pad("J203", "1"))

# Programming pins.
track("Net-(U201-ILIM)", "F", 0.2, U("8"), (156.75, 88.6), (156.55, 88.8), pad("R202", "1"))
track("Net-(U201-ICHGSET)", "F", 0.2, U("10"), (157.75, 88.6), (157.6, 88.75), pad("R201", "1"))
track("Net-(U201-VSET)", "F", 0.2, U("6"), pad("R203", "1"))
track("GND", "F", 0.2, pad("R203", "2"), U("4"))
track("TS", "F", 0.2, U("7"), (156.25, 88.17), (155.8, 88.62), (155.8, 89.11), pad("R204", "2"), pad("R205", "1"))

# REGN: C209, then In2 to the TS divider top and to the STAT LED pull-up on the outer face.
VR1, VR2, VR3 = (159.9, 89.3), (161.7, 82.0), (153.3, 87.1)
track("REGN", "F", 0.25, U("11"), (158.25, 88.5), (158.9, 89.15), pad("C209", "1"), VR1)
for v in (VR1, VR2, VR3):
    via("REGN", v)
track("REGN", "I2", 0.2, VR1, (160.2, 89.0), (160.2, 83.0), VR2)
track("REGN", "I2", 0.2, VR1, VR3)
track("REGN", "F", 0.2, VR3, pad("R204", "1"))
track("REGN", "B", 0.25, VR2, pad("R207", "1"))

# BTST: pin -> via -> C208 on the outer face, directly under the SW pins (SW via VSW above).
VBT1 = (159.4, 87.95)
track("BTST", "F", 0.2, U("12"), (158.75, 87.95), VBT1)
via("BTST", VBT1, 0.46, 0.2)
track("BTST", "B", 0.25, VBT1, pad("C208", "1"))

# Status LEDs on the outer face.
VST = (153.8, 82.5)
track("CHG_STAT", "F", 0.2, U("2"), (153.8, 85.05), VST)
via("CHG_STAT", VST)
track("CHG_STAT", "B", 0.25, VST, pad("D202", "1"))
track("Net-(D202-A)", "B", 0.25, pad("D202", "2"), pad("R207", "2"))
track("Net-(D201-A)", "B", 0.25, pad("R206", "2"), pad("D201", "2"))
track("GND", "B", 0.3, pad("D201", "1"), (168.9, 81.6))
via("GND", (168.9, 81.6))

# SWD pass-through: J201 (inner) straight through to J202 (outer); GND via also lands on In1.
for n, x in (("1", 204.5), ("2", 205.5), ("3", 206.5)):
    net = {"1": "SWCLK", "2": "GND", "3": "SWDIO"}[n]
    track(net, "F", 0.25, pad("J201", n), (x, 98.6))
    via(net, (x, 98.6))
    track(net, "B", 0.25, (x, 98.6), pad("J202", n))



for r in ("J201", "J202", "J203"):
    b.FindFootprintByReference(r).Reference().SetVisible(False)


def silk(txt, at, layer, size=1.0):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(mm(at[0]), mm(at[1])))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    b.Add(t)


silk("J202 SWD", (205.5, 105.6), pcbnew.B_SilkS)
silk("J201 SWD from FC J22", (205.5, 92.4), pcbnew.F_SilkS, 0.8)
silk("CHG LINK", (162.2, 94.9), pcbnew.B_SilkS, 0.8)
silk("NO FLIGHT", (162.2, 96.1), pcbnew.B_SilkS, 0.8)
silk("USB", (166.9, 83.6), pcbnew.B_SilkS, 0.8)
silk("CHG", (157.2, 81.0), pcbnew.B_SilkS, 0.8)
for d in b.GetDrawings():
    if isinstance(d, pcbnew.PCB_TEXT) and "Antenna Board \nV2c" in d.GetText().replace("\n", "\\n"):
        d.SetText(d.GetText().replace("V2c", "V2d"))
    elif isinstance(d, pcbnew.PCB_TEXT) and "\nV2c\n" in d.GetText():
        d.SetText(d.GetText().replace("\nV2c\n", "\nV2d\n"))

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)
print("routed")
