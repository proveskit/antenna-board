#!/usr/bin/env python3
"""Check the V3 turnstile feed on the board itself (run with KiCad's Python).

usage: check_rf.py <v3 board> <netlist.xml>
Reads only the board and the schematic netlist, not tools/rf_plan.py, so a wrong plan cannot pass itself. Fails if:
- an RF net is not one unbranched F.Cu path of 0.3424 mm track between exactly the pads the schematic gives it,
- any RF corner is not 45 degrees, or any RF segment is off the 0/45/90 degree grid,
- UHF_A is not a quarter guided wave (90 +/- 2 deg at 437 MHz) longer than UHF_B,
- the four element feeds differ by more than 0.05 mm,
- the phase the hybrids and the delay line give the elements does not step 90 deg from AE1 to AE2 to AE3 to AE4.
"""
import math
import sys
import xml.etree.ElementTree as ET

import pcbnew

BOARD, NETLIST = sys.argv[1:3]
E_EFF, F_MHZ, WIDTH = 3.32, 437.0, 0.3424  # JLC04161H-7628 CPWG (RF review 2026-11-14)
LAMBDA_G = 299792.458 / F_MHZ / math.sqrt(E_EFF)
NETS = ["/UHF", "/RF/UHF_A", "/RF/UHF_B", "/RF/UHF_0", "/RF/UHF_90", "/RF/UHF_180", "/RF/UHF_270"]
HYBRIDS = ["U301", "U302", "U303"]
# MHC0410L03 datasheet table 2: input pin -> (isolated, direct -90 deg, coupled 0 deg)
PORTS = {"1": ("2", "3", "4"), "2": ("1", "4", "3"), "3": ("4", "1", "2"), "4": ("3", "2", "1")}

b = pcbnew.LoadBoard(BOARD)
root = ET.parse(NETLIST).getroot()
want = {n.get("name"): {(x.get("ref"), x.get("pin")) for x in n.iter("node")} for n in root.iter("net")}
pads = {}
for f in b.Footprints():
    for p in f.Pads():
        pads.setdefault(p.GetNetname(), []).append((f.GetReference(), p.GetNumber(), p))
ok = True


def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)


length = {}
for n in NETS:
    segs = [t for t in b.Tracks() if t.GetNetname() == n]
    got = {(r, num) for r, num, _ in pads.get(n, [])}
    if got != want.get(n):
        fail(f"{n} pads {sorted(got)} != schematic {sorted(want.get(n, []))}")
    if any(t.GetClass() != "PCB_TRACK" or t.GetLayer() != pcbnew.F_Cu or abs(pcbnew.ToMM(t.GetWidth()) - WIDTH) > 1e-4 for t in segs):
        fail(f"{n} has a via, an arc, a layer change or an off-width segment")
    ends = {}
    for t in segs:
        for q in (t.GetStart(), t.GetEnd()):
            ends.setdefault((q.x, q.y), []).append(t)
    tips = [q for q, ts in ends.items() if len(ts) == 1]
    if len(tips) != 2 or any(len(ts) > 2 for ts in ends.values()):
        fail(f"{n} is not one unbranched path ({len(tips)} free ends)")
    for q in tips:  # each free end must sit on a pad of this net
        if not any(p.HitTest(pcbnew.VECTOR2I(*q)) for _, _, p in pads.get(n, [])):
            fail(f"{n} ends off its pads at {q}")
    worst = 0
    for t in segs:
        d = t.GetEnd() - t.GetStart()
        a = math.degrees(math.atan2(d.y, d.x)) % 45
        worst = max(worst, min(a, 45 - a))
    for q, ts in ends.items():
        if len(ts) == 2:
            v = []
            for t in ts:
                o = t.GetEnd() if (t.GetStart().x, t.GetStart().y) == q else t.GetStart()
                v.append((o.x - q[0], o.y - q[1]))
            turn = 180 - abs(math.degrees(math.atan2(v[0][0] * v[1][1] - v[0][1] * v[1][0], v[0][0] * v[1][0] + v[0][1] * v[1][1])))
            if turn > 45.5:
                fail(f"{n} turns {turn:.0f} deg at {pcbnew.ToMM(q[0]):.2f}, {pcbnew.ToMM(q[1]):.2f}")
    if worst > 0.5:
        fail(f"{n} has a segment {worst:.1f} deg off the 45 degree grid")
    length[n] = sum(pcbnew.ToMM(t.GetLength()) for t in segs)
    print(f"{n:13s} {length[n]:8.3f} mm  {len(segs):3d} segments")

deg = lambda mm_: mm_ / LAMBDA_G * 360
dl = length["/RF/UHF_A"] - length["/RF/UHF_B"]
print(f"delay line: UHF_A - UHF_B = {dl:.3f} mm = {deg(dl):.2f} deg at {F_MHZ:.0f} MHz (e_eff {E_EFF})")
if abs(deg(dl) - 90) > 2:
    fail("delay line is not 90 +/- 2 deg")
feeds = {n: length[n] for n in NETS[3:]}
spread = max(feeds.values()) - min(feeds.values())
print(f"element feed spread {spread:.3f} mm")
if spread > 0.05:
    fail("element feeds are not length-matched")

# phase lag (deg) each element sees, walking the schematic from the MMCX through the hybrids
net_of = {(x.get("ref"), x.get("pin")): n.get("name") for n in root.iter("net") for x in n.iter("node")}
lag = {"/UHF": 0.0}
todo = ["/UHF"]
while todo:
    n = todo.pop()
    for ref, pin in want[n]:
        if ref in HYBRIDS and pin in PORTS and (ref, "in") not in lag:
            lag[(ref, "in")] = pin
            iso, direct, coupled = PORTS[pin]
            if not any(r.startswith("R") for r, _ in want[net_of[(ref, iso)]]):
                fail(f"{ref} isolated port (pin {iso}) has no load")
            for out, extra in ((direct, 90.0), (coupled, 0.0)):
                m = net_of[(ref, out)]
                lag[m] = lag[n] + deg(length[n]) + extra
                todo.append(m)
el = {}
for n in NETS[3:]:
    ref = next(r for r, _ in want[n] if r.startswith("AE"))
    el[ref] = (lag[n] + deg(length[n])) % 360
steps = [(el[b_] - el[a_]) % 360 for a_, b_ in (("AE1", "AE2"), ("AE2", "AE3"), ("AE3", "AE4"), ("AE4", "AE1"))]
print("element phase lag (deg):", {k: round(v, 1) for k, v in sorted(el.items())}, "steps", [round(s, 1) for s in steps])
if any(abs(s - 90) > 2 for s in steps):
    fail("elements do not step 90 deg in the order AE1, AE2, AE3, AE4")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
