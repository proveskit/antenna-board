#!/usr/bin/env python3
"""Fail if any harness, structure or user-facing part moved from where V2d has it (run with KiCad's Python).

usage: check_interface.py <v3 board> <v2d board>
These are the parts a cable, a structure cutout, a jumper shunt or the firmware's I2C map depends on.
"""
import sys

import pcbnew

LOCKED = ["J1", "J2", "J3", "J4", "J8", "J9", "J10", "J11", "J12", "J13", "J201", "J202", "J204",
          "TP1", "TP4", "TP5", "TP6", "U3", "U4", "U6", "Q2"]


def where(path):
    b = pcbnew.LoadBoard(path)
    c = b.GetBoardEdgesBoundingBox()
    out = {"_outline": (pcbnew.ToMM(c.GetWidth()), pcbnew.ToMM(c.GetHeight()), 0, "")}
    cx, cy = c.GetCenter().x, c.GetCenter().y
    for f in [x for x in b.Footprints()]:
        p = f.GetPosition()
        out[f.GetReference()] = (round(pcbnew.ToMM(p.x - cx), 3), round(pcbnew.ToMM(p.y - cy), 3),
                                 round(f.GetOrientationDegrees(), 1), b.GetLayerName(f.GetLayer()))
    return out


a, b = where(sys.argv[1]), where(sys.argv[2])
bad = [r for r in ["_outline"] + LOCKED if a.get(r) != b.get(r)]
for r in ["_outline"] + LOCKED:
    print(f"{r:9s} {'ok  ' if r not in bad else 'MOVED'} v3 {a.get(r)}  v2d {b.get(r)}")
print("PASS" if not bad else f"FAIL: {bad}")
sys.exit(1 if bad else 0)
