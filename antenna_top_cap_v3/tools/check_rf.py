#!/usr/bin/env python3
"""Check the V3 turnstile feed on the board itself (run with KiCad's Python).

usage: check_rf.py <v3 board> <netlist.xml>
Reads only the board and the schematic netlist, not tools/rf_plan.py, so a wrong plan cannot pass itself. Fails if:
- an RF net is not one unbranched F.Cu path of 0.3424 mm track between exactly the pads the schematic gives it,
- any RF corner is not 45 degrees, or any RF segment is off the 0/45/90 degree grid,
- UHF_A is not a quarter guided wave (90 +/- 2 deg at 437 MHz) longer than UHF_B,
- the four element feeds differ by more than 0.05 mm,
- the feed phase does not lag 90 deg per element clockwise as seen from F.Cu (north, east, south, west by pad
  position), which is right-hand circular out of B.Cu, the outer face with the USB ports,
- a hybrid is flipped or its lands are not numbered 1 to 4 clockwise from the top left (datasheet figure 2, top view),
- an isolated port's load is not 49.9 Ohm in 2512 to GND,
- In1 ground is missing under any RF line or hybrid (the cleared boxes under the tape pads and the MMCX pin's antipad excepted),
- GND stitching thins out: fewer than 60 vias within 1.6 mm of RF copper, or a point on an RF line more than
  4 mm from any GND via.
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
centre = b.GetBoardEdgesBoundingBox().GetCenter()
fps = {f.GetReference(): f for f in b.Footprints()}
el = []
for n in NETS[3:]:
    ref = next(r for r, _ in want[n] if r.startswith("AE"))
    q = next(iter(fps[ref].Pads())).GetPosition() - centre
    # screen angle, clockwise from north: KiCad draws F.Cu as seen from the F side, y down
    el.append(((math.degrees(math.atan2(q.x, -q.y)) + 45) % 360 - 45, ref, (lag[n] + deg(length[n])) % 360))
el.sort()
if any(abs(a - want_a) > 3 for (a, _, _), want_a in zip(el, (0, 90, 180, 270))):
    fail(f"tape pads are not north, east, south, west of centre: {[(r, round(a)) for a, r, _ in el]}")
steps = [(el[(i + 1) % 4][2] - el[i][2]) % 360 for i in range(4)]
print("phase lag clockwise from north, seen from F.Cu:", [(r, round((ph - el[0][2]) % 360, 1)) for _, r, ph in el], "steps", [round(x, 1) for x in steps])
if any(abs(x - 90) > 2 for x in steps):
    fail("feed phase does not lag 90 deg per element clockwise from F.Cu: not right-hand circular out of the outer face")

for ref in HYBRIDS:
    f = fps[ref]
    a = math.radians(f.GetOrientationDegrees())
    quad = {}
    for p in f.Pads():
        if p.GetNumber() in PORTS:
            d = p.GetPosition() - f.GetPosition()
            lx, ly = d.x * math.cos(a) - d.y * math.sin(a), d.x * math.sin(a) + d.y * math.cos(a)
            quad[p.GetNumber()] = (lx > 0, ly > 0)
    if f.IsFlipped() or quad != {"1": (False, False), "2": (True, False), "3": (True, True), "4": (False, True)}:
        fail(f"{ref} is flipped or its lands are not in the datasheet's top-view order: {quad}")

comp = {c.get("ref"): c for c in root.iter("comp")}
for ref in sorted(r for r in comp if r.startswith("R30")):
    c = comp[ref]
    if c.findtext("value") != "49.9" or "2512" not in c.findtext("footprint") or net_of.get((ref, "2")) != "GND":
        fail(f"{ref} is not a 49.9 Ohm 2512 load to GND")
    if {p.GetNumber(): p.GetNetname() for p in fps[ref].Pads()}.get("2") != "GND":
        fail(f"{ref} pad 2 is not on GND on the board")

in1 = [z for z in b.Zones() if z.GetNetname() == "GND" and z.IsOnLayer(pcbnew.In1_Cu) and not z.GetIsRuleArea()]
fill = in1[0].GetFilledPolysList(pcbnew.In1_Cu) if in1 else None
boxes = []
for _, ref, _ in el:
    bx = next(iter(fps[ref].Pads())).GetBoundingBox()
    bx.Inflate(pcbnew.FromMM(1.0))
    boxes.append(bx)
gnd_vias = [t.GetPosition() for t in b.Tracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
gnd_vias += [p.GetPosition() for ref in HYBRIDS for p in fps[ref].Pads() if p.GetNetname() == "GND" and p.HasHole()]
rf_holes = [p.GetPosition() for n in NETS for _, _, p in pads.get(n, []) if p.HasHole()]
bare, far, near, where = 0, 0.0, set(), []
for t in b.Tracks():
    if t.GetNetname() not in NETS or t.GetClass() != "PCB_TRACK":
        continue
    k = max(1, int(pcbnew.ToMM(t.GetLength()) / 0.25))
    for i in range(k + 1):
        q = pcbnew.VECTOR2I(int(t.GetStart().x + (t.GetEnd().x - t.GetStart().x) * i / k), int(t.GetStart().y + (t.GetEnd().y - t.GetStart().y) * i / k))
        ds = [math.hypot(g.x - q.x, g.y - q.y) for g in gnd_vias]
        near.update(j for j, d_ in enumerate(ds) if d_ < pcbnew.FromMM(1.6))
        if any(bx.Contains(q) for bx in boxes) or any(math.hypot(h.x - q.x, h.y - q.y) < pcbnew.FromMM(2.0) for h in rf_holes):
            continue  # the cleared tape-pad boxes and the MMCX pins' antipads and thermals
        if fill is None or not fill.Contains(q):
            bare += 1
            where.append((round(pcbnew.ToMM(q.x - centre.x), 2), round(pcbnew.ToMM(q.y - centre.y), 2)))
        far = max(far, pcbnew.ToMM(min(ds)))
for ref in HYBRIDS:
    bare += fill is None or not fill.Contains(fps[ref].GetPosition())
print(f"In1 ground: {bare} bare sample points under RF copper; GND vias within 1.6 mm of RF copper: {len(near)}; farthest RF point from a GND via: {far:.2f} mm")
if bare:
    fail(f"In1 ground is missing under RF copper, first at {where[:3]}")
if len(near) < 60 or far > 4.0:
    fail("GND stitching along the RF lines is too thin")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
