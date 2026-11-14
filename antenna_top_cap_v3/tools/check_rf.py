#!/usr/bin/env python3
"""Check the V3 RF copper against the turnstile it was copied from (run with KiCad's Python).

usage: check_rf.py <v3 board> <turnstile board>
Fails if any RF segment (layer, width, end points relative to the board centre) differs from the turnstile,
if the RF nets' lengths differ, if the delay line is not a quarter wave, or if /UHF does not join RF1 to U301.
"""
import sys

import pcbnew

V3, TURN = sys.argv[1:3]
PAIRS = {"/RF/UHF_A": "/UHF-SHORT", "/RF/UHF_B": "/UHF-SHORT+1{slash}4WAVE", "/RF/UHF_0": "/UHF_0",
         "/RF/UHF_90": "/UHF_90", "/RF/UHF_180": "/UHF_180", "/RF/UHF_270": "/UHF_270"}


def segs(path, names):
    b = pcbnew.LoadBoard(path)
    c = b.GetBoardEdgesBoundingBox().GetCenter()
    rel = lambda q: (round(pcbnew.ToMM(q.x - c.x), 3), round(pcbnew.ToMM(q.y - c.y), 3))
    out = {}
    for t in [x for x in b.Tracks()]:
        if t.GetNetname() in names and t.GetClass() != "PCB_VIA":
            e = tuple(sorted([rel(t.GetStart()), rel(t.GetEnd())]))
            out.setdefault(names[t.GetNetname()], set()).add((b.GetLayerName(t.GetLayer()), round(pcbnew.ToMM(t.GetWidth()), 4)) + e)
    return out, b


def lengths(path):
    b = pcbnew.LoadBoard(path)
    out = {}
    for t in [x for x in b.Tracks()]:
        if t.GetClass() != "PCB_VIA":
            out[t.GetNetname()] = out.get(t.GetNetname(), 0) + pcbnew.ToMM(t.GetLength())
    return out


a, b = lengths(V3), lengths(TURN)
ok = True
s3, b3 = segs(V3, {k: k for k in PAIRS})
st, _ = segs(TURN, {v: k for k, v in PAIRS.items()})
for n in PAIRS:
    d = s3.get(n, set()) ^ st.get(n, set())
    ok &= not d
    print(f"{n:14s} {len(s3.get(n, ())):3d} segments, {len(d)} differ from the turnstile (layer, width, ends)")
uhf = {(f.GetReference(), p.GetNumber()) for f in [x for x in b3.Footprints()] for p in f.Pads() if p.GetNetname() == "/UHF"}
ok &= uhf == {("RF1", "5"), ("U301", "1")}
print("/UHF pads", sorted(uhf))
for n3, nt in PAIRS.items():
    d = a.get(n3, 0) - b.get(nt, 0)
    ok &= abs(d) < 0.01
    print(f"{n3:14s} {a.get(n3, 0):8.2f} mm  turnstile {b.get(nt, 0):8.2f} mm  diff {d:+.3f}")
dl = a["/RF/UHF_B"] - a["/RF/UHF_A"]
eeff = 3.32  # JLC04161H-7628, 0.3424 mm trace on 0.2104 mm prepreg (RF review 2026-11-14)
deg = dl / (299792.458 / 437.0 / eeff ** 0.5) * 360  # lambda_g in mm
print(f"delay line {dl:.2f} mm = {deg:.1f} deg at 437 MHz (e_eff {eeff})")
feeds = [a[n] for n in ("/RF/UHF_0", "/RF/UHF_90", "/RF/UHF_180", "/RF/UHF_270")]
print(f"element feed spread {max(feeds) - min(feeds):.3f} mm")
ok &= abs(deg - 90) < 2 and max(feeds) - min(feeds) < 0.05
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
