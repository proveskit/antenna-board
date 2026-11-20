#!/usr/bin/env python3
"""Build antenna_top_cap_v3.kicad_pcb: V2d interface + turnstile CP RF block (run with KiCad's Python).

usage: build_v3.py <v2d board> <turnstile board> <netlist.xml> <kicad footprints dir> <out board> [stage]
Starts from the V2d board every run, so reruns are idempotent.
  1. Drop the dipole: B1, J6, their nets, and the dipole-window keepouts / balun ground island.
  2. Take the four tape element pads (AE1-AE4) from the turnstile board at their own coordinates, then place
     the three MHC0410L03 hybrids and their 1206 loads and route the feed network from tools/rf_plan.py.
  3. Move the charger block (rigid) off the +Y-up (north) element, and re-run its two outside links.
  4. Move RF1 (MMCX) next to U301 and route the UHF feed. J7 (burn wire) stays where V2d has it.
  5. Stitch GND vias along the RF lines and drop any that land on other copper, holes, slots or keepouts.
  6. Bind the RF footprints to the V3 schematic (library IDs, values, fields, symbol paths).
"""
import math
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rf_plan  # noqa: E402

V2D, TURN, NETLIST, FPDIR, OUT = sys.argv[1:6]
STAGE = int(sys.argv[6]) if len(sys.argv) > 6 else 9
mm = pcbnew.FromMM

RF_REFS = ["AE1", "AE2", "AE3", "AE4"]
CHG_REFS = ["U201", "L201", "C201", "C202", "C204", "C205", "C206", "C207", "C208", "C209", "F201",
            "R201", "R202", "R203", "R204", "R205", "R206", "R207", "R210", "D201", "D202"]
CHG_OFF = (-11.0, -2.0)

v = pcbnew.LoadBoard(V2D)
t = pcbnew.LoadBoard(TURN)
T_TRACKS = [x for x in t.Tracks()]
T_FPS = [x for x in t.Footprints()]
V_TRACKS = [x for x in v.Tracks()]
vc = v.GetBoardEdgesBoundingBox().GetCenter()
tc = t.GetBoardEdgesBoundingBox().GetCenter()
CX, CY = pcbnew.ToMM(vc.x), pcbnew.ToMM(vc.y)
delta = pcbnew.VECTOR2I(vc.x - tc.x, vc.y - tc.y)


def P(x, y):
    """Board-centred mm -> absolute VECTOR2I."""
    return pcbnew.VECTOR2I(mm(CX + x), mm(CY + y))


def net(name):
    n = v.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(v, name)
        v.Add(n)
    return n


def pad(ref, num):
    for p in FP[ref].Pads():
        if p.GetNumber() == num:
            return p
    raise KeyError((ref, num))


def track(netname, layer, width, *pts):
    for a, c in zip(pts, pts[1:]):
        tr = pcbnew.PCB_TRACK(v)
        tr.SetStart(a if isinstance(a, pcbnew.VECTOR2I) else P(*a))
        tr.SetEnd(c if isinstance(c, pcbnew.VECTOR2I) else P(*c))
        tr.SetWidth(mm(width))
        tr.SetLayer(layer)
        tr.SetNet(net(netname))
        v.Add(tr)


def via(netname, at, dia=0.6, drill=0.3):
    vi = pcbnew.PCB_VIA(v)
    vi.SetPosition(at if isinstance(at, pcbnew.VECTOR2I) else P(*at))
    vi.SetViaType(pcbnew.VIATYPE_THROUGH)
    vi.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    vi.SetWidth(mm(dia))
    vi.SetDrill(mm(drill))
    vi.SetNet(net(netname))
    v.Add(vi)


# ---- 2. tape element pads from the turnstile (adds first: removing items before iterating others upsets SWIG)
_root = ET.parse(NETLIST).getroot()
COMPS = {c.get("ref"): c for c in _root.iter("comp")}
PINNET = {(n2.get("ref"), n2.get("pin")): n.get("name") for n in _root.iter("net") for n2 in n.iter("node")}
NEW_VIAS = []
for f in T_FPS:
    if f.GetReference() not in RF_REFS:
        continue
    nf = pcbnew.FOOTPRINT(f)
    for p in nf.Pads():
        p.SetNet(net(PINNET[(f.GetReference(), p.GetNumber())]))
    v.Add(nf)
    nf.Move(delta)
IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def place(libdir, name, ref, at, rot):
    f = IO.FootprintLoad(libdir, name)
    f.SetReference(ref)
    v.Add(f)
    f.SetPosition(P(*at))
    f.SetOrientationDegrees(rot)
    for p in f.Pads():
        if p.GetNumber():
            p.SetNet(net(PINNET[(ref, p.GetNumber())]))
    f.Reference().SetVisible(False)  # V2d shows only connector refs on silk
    return f


def no_fill(name, box, layers, no_vias=False):
    z = pcbnew.ZONE(v)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowZoneFills(True)
    for flag in (z.SetDoNotAllowTracks, z.SetDoNotAllowPads, z.SetDoNotAllowFootprints):
        flag(False)
    z.SetDoNotAllowVias(no_vias)
    ls = pcbnew.LSET()
    for layer in layers:
        ls.AddLayer(layer)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((box.GetLeft(), box.GetTop()), (box.GetRight(), box.GetTop()), (box.GetRight(), box.GetBottom()), (box.GetLeft(), box.GetBottom())):
        o.Append(x, y)
    v.Add(z)
    return z


# No plane copper under the tape pads (over In1 at 0.21 mm each pad is about 8.6 pF across its feed), the same on
# B.Cu for all four, and no F.Cu pour or vias on the strip the tape crosses between its pad and its slot.
TAPE_KEEPOUTS = []
for f in [x for x in v.Footprints()]:
    if f.GetReference() in RF_REFS:
        pad_box = next(iter(f.Pads())).GetBoundingBox()
        strip = pcbnew.BOX2I(pad_box.GetOrigin(), pad_box.GetSize())
        for g in f.GraphicalItems():
            if g.GetLayer() == pcbnew.Edge_Cuts:
                strip.Merge(g.GetBoundingBox())
        pad_box.Inflate(mm(0.3))
        strip.Inflate(mm(0.3))
        no_fill(f"{f.GetReference()} pad: no plane copper", pad_box, (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu))
        TAPE_KEEPOUTS.append(no_fill(f"{f.GetReference()} tape strip: no pour, no vias", strip, (pcbnew.F_Cu,), no_vias=True))

RF_PLAN = rf_plan.plan()
for ref, (at, rot) in rf_plan.HYBRIDS.items():
    place(f"{HERE}/footprints.pretty", "MHC0410L03", ref, at, rot)
for ref, (hyb, pin) in rf_plan.LOADS.items():
    pts, d = rf_plan.term(hyb, pin)
    # pad 1 (TERM) faces the hybrid and the stub ends on its centre; pad 2 (GND) gets its own via just past it
    r = place(f"{FPDIR}/Resistor_SMD.pretty", "R_2512_6332Metric", ref, (0, 0), math.degrees(math.atan2(-d[1], d[0])))
    half = math.dist(*[(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)) for p in r.Pads()]) / 2
    r.SetPosition(P(*rf_plan.go(pts[-1], d, half)))
    track(PINNET[(ref, "1")], pcbnew.F_Cu, rf_plan.WIDTH, *pts)
    for p in r.Pads():
        if p.GetNumber() == "2":
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    end = rf_plan.go(pts[-1], d, 2 * half + 1.3)
    for side in (-1.2, 0, 1.2):  # three ground vias just past the ground pad
        via("GND", (end[0] - d[1] * side, end[1] + d[0] * side))
for name, pts in RF_PLAN.items():
    if name != "/UHF":
        track(name, pcbnew.F_Cu, rf_plan.WIDTH, *pts)

FP = {f.GetReference(): f for f in [x for x in v.Footprints()]}

DEAD = []  # removed at the end, after every iteration over board items
dead_zones_pre = []
for z in [x for x in v.Zones()]:
    r = z.GetBoundingBox()
    if abs(pcbnew.ToMM(r.GetX()) - CX + 32.7) < 0.3 and abs(pcbnew.ToMM(r.GetY()) - CY - 14.7) < 0.3:
        dead_zones_pre.append(z)


def move_block(refs, dx, dy, keep_nets=(), only_nets=None, bridge=False):
    """Rigidly move footprints and the copper fully inside their box.

    Copper crossing the box edge is rubber-banded, or with bridge=True left alone and joined by a new segment.
    """
    off = pcbnew.VECTOR2I(mm(dx), mm(dy))
    box = FP[refs[0]].GetBoundingBox(False)
    for ref in refs:
        box.Merge(FP[ref].GetBoundingBox(False))
    box.Inflate(mm(1.0))
    for ref in refs:
        FP[ref].Move(off)
    for tr in V_TRACKS:
        if tr.GetNetname() in keep_nets or (only_nets and tr.GetNetname() not in only_nets):
            continue
        a = box.Contains(tr.GetStart())
        if tr.GetClass() == "PCB_VIA":
            if a:
                tr.Move(off)
            continue
        e = box.Contains(tr.GetEnd())
        if a and e:
            tr.Move(off)
        elif a or e:
            q = tr.GetStart() if a else tr.GetEnd()
            if bridge:
                track(tr.GetNetname(), tr.GetLayer(), pcbnew.ToMM(tr.GetWidth()), q, q + off)
            elif a:
                tr.SetStart(q + off)
            else:
                tr.SetEnd(q + off)
    for d in v.GetDrawings():
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and box.Contains(d.GetPosition()):
            d.Move(off)


# ---- 3. charger block off the north element
def seg(netname, a, b, tol=0.05):
    """The V2d track of netname with these board-centred endpoints (either direction)."""
    A, B = P(*a), P(*b)
    for tr in V_TRACKS:
        if tr.GetNetname() != netname or tr.GetClass() == "PCB_VIA":
            continue
        s0, s1 = tr.GetStart(), tr.GetEnd()
        for u, w in ((s0, s1), (s1, s0)):
            if abs(u.x - A.x) < mm(tol) and abs(u.y - A.y) < mm(tol) and abs(w.x - B.x) < mm(tol) and abs(w.y - B.y) < mm(tol):
                return tr
    raise KeyError((netname, a, b))


VB = "/Charger & SWD/VBUS_CHG"
if STAGE >= 3:
    # The VBUS trunk from J204 used to run along y -32.72, which is now the north element's slot.
    DEAD.append(seg(VB, (6.9, -32.72), (-9.15, -32.72)))
    DEAD.append(seg(VB, (7.4, -33.22), (6.9, -32.72)))
    DEAD.append(seg(VB, (7.4, -39.92), (7.4, -33.22)))
    chg_nets = {p.GetNetname() for r in CHG_REFS for p in FP[r].Pads()} - {VB}
    move_block(CHG_REFS, *CHG_OFF, only_nets=chg_nets)
    for tr in V_TRACKS:  # charger-internal VBUS copper moves with the block
        if tr.GetNetname() == VB and tr not in DEAD:
            q = tr.GetStart()
            if pcbnew.ToMM(q.y) - CY > -35.0 and pcbnew.ToMM(q.x) - CX < 0:
                tr.Move(pcbnew.VECTOR2I(mm(CHG_OFF[0]), mm(CHG_OFF[1])))
    vd = (-9.15 + CHG_OFF[0], -32.72 + CHG_OFF[1])
    track(VB, pcbnew.B_Cu, 1.0, (7.404, -39.917), (7.404, -35.7), (6.904, -35.2), (vd[0] + 0.483, -35.2), vd)
    track(VB, pcbnew.B_Cu, 0.3, (-2.77 + CHG_OFF[0], -32.72 + CHG_OFF[1]), (-2.77 + CHG_OFF[0], -35.2))  # R206 stub onto the trunk centreline

    # SCL1/SDA1 to the VEML6031 crossed the west element feed on F.Cu: drop them to B.Cu at the pull-ups.
    DEAD.append(seg("SCL1", (-13.5, 2.8), (-26.4, 15.7)))
    DEAD.append(seg("SCL1", (-34.5, 15.7), (-26.4, 15.7)))
    DEAD.extend(tr for tr in V_TRACKS if tr.GetClass() == "PCB_VIA" and tr.GetNetname() in ("SCL1", "SDA1")
                and min(math.hypot(pcbnew.ToMM(tr.GetPosition().x) - CX - x, pcbnew.ToMM(tr.GetPosition().y) - CY - y)
                        for x, y in ((-34.5, 15.7), (-33.55, 13.74))) < 0.05)  # B.Cu now runs straight through
    track("SCL1", pcbnew.F_Cu, 0.152, (-13.5, 2.8), (-15.5, 4.8))
    via("SCL1", (-15.5, 4.8))
    track("SCL1", pcbnew.B_Cu, 0.152, (-15.5, 4.8), (-26.4, 15.7), (-34.5, 15.7))
    DEAD.append(seg("SDA1", (-14.1, 2.9), (-24.94, 13.74)))
    DEAD.append(seg("SDA1", (-24.94, 13.74), (-33.55, 13.74)))
    track("SDA1", pcbnew.F_Cu, 0.152, (-14.1, 2.9), (-14.4, 2.6))
    via("SDA1", (-14.4, 2.6))
    track("SDA1", pcbnew.B_Cu, 0.152, (-14.4, 2.6), (-25.54, 13.74), (-33.55, 13.74))

# ---- 3b. SWD from J202 (top edge) to J201: V2d runs it on F.Cu through what is now the charger and the RF block
def offset(pts, d):
    """Parallel polyline d mm to the left of travel (y down, so left of south is east), mitred corners."""
    out = []
    for i, p in enumerate(pts):
        ns = []
        for a, b in zip(pts[max(i - 1, 0):i + 1], pts[max(i, 1):i + 2]):
            L = math.dist(a, b)
            ns.append(((b[1] - a[1]) / L, -(b[0] - a[0]) / L))
        nx, ny = sum(n[0] for n in ns), sum(n[1] for n in ns)
        k = d / (nx * ns[0][0] + ny * ns[0][1])
        out.append((p[0] + nx * k, p[1] + ny * k))
    return out


# West of the TP6 keepout, then under the strip between AE2's pad and its slot on B.Cu (the tape lies on that strip
# on F.Cu), back to F.Cu, around the outside of U302 and into J201 from the south.
SWD_W = [(-10.15, -42.0), (-10.15, -31.65), (-8.65, -30.15), (-8.4, -30.15)]
SWD_E = [(8.4, -30.15), (25.6, -30.15), (29.3, -26.45), (29.3, -14.3), (30.4, -13.2), (38.0, -13.2)]
SWD = {"/Charger & SWD/SWCLK": ([(-1.046, -43.317), (-9.75, -43.317)],
                                [(-9.75, -43.317)] + offset(SWD_W, 0.4)[:-1] + [(-7.3, -30.55)],
                                [(8.9, -30.55)] + offset(SWD_E, 0.4)[1:] + [(38.354, -13.6), (38.954, -14.2), (38.954, -15.292)]),
       "/Charger & SWD/SWDIO": ([(0.954, -42.617), (-10.75, -42.617)],
                                [(-10.75, -42.617), (-10.75, -42.4), (-10.55, -42.2)] + offset(SWD_W, -0.4)[:-1] + [(-8.3, -29.75)],
                                [(7.9, -29.75)] + offset(SWD_E, -0.4)[1:] + [(40.354, -12.8), (40.954, -13.4), (40.954, -15.292)])}
if STAGE >= 3:
    for name, (back, west, east) in SWD.items():
        for tr in V_TRACKS:  # keep only the B.Cu stub at J202
            if tr.GetNetname() == name and (tr.GetClass() == "PCB_VIA" or tr.GetLayer() == pcbnew.F_Cu or tr.GetLength() > mm(5)):
                DEAD.append(tr)
        track(name, pcbnew.B_Cu, 0.2, *back)
        track(name, pcbnew.F_Cu, 0.2, *west)
        track(name, pcbnew.B_Cu, 0.2, west[-1], east[0])
        track(name, pcbnew.F_Cu, 0.2, *east)
        for q in (west[0], west[-1], east[0]):
            via(name, q)

    # The payload USB pair on B.Cu ran under AE2's pad, where In1 and In2 are now cleared: take it round the east end.
    W = 0.267208
    for name, drop, new in (
            ("USB_D+", [((20.706, -29.63), (8.731, -29.63)), ((8.731, -29.63), (3.5, -24.398)), ((3.5, -24.398), (3.5, -12.612))],
             [(20.706, -29.63), (12.4, -29.63), (11.6, -28.83), (11.6, -23.3), (3.5, -15.2), (3.5, -12.612)]),
            ("USB_D-", [((8.4, -30.098), (20.9, -30.098)), ((2.6, -24.298), (8.4, -30.098)), ((2.6, -9.498), (2.6, -24.298))],
             [(20.9, -30.098), (12.069, -30.098), (11.0, -29.029), (11.0, -23.5), (2.6, -15.1), (2.6, -9.498)])):
        for a_, b_ in drop:
            DEAD.append(seg(name, a_, b_))
        track(name, pcbnew.B_Cu, W, *new)

# ---- 4. MMCX next to U301
def gnd_in(x0, y0, x1, y1):
    """V2d GND tracks with both ends inside a board-centred box."""
    A, B = P(x0, y0), P(x1, y1)
    ins = lambda q: A.x <= q.x <= B.x and A.y <= q.y <= B.y
    return [tr for tr in V_TRACKS if tr.GetNetname() == "GND" and tr.GetClass() != "PCB_VIA" and ins(tr.GetStart()) and ins(tr.GetEnd())]


# GND ties left floating once B1 goes; a floating track takes the net of whatever it touches on fill.
DEAD.extend(gnd_in(-1.6, 13.5, 0.3, 19.0))
if STAGE >= 4:
    rf1 = FP["RF1"]
    rf1.SetPosition(P(*RF_PLAN["/UHF"][-1]))
    rf1.SetOrientationDegrees(rf_plan.RF1_ROT)
    for p in rf1.Pads():
        if p.GetNumber() == "5":
            p.SetNet(net("/UHF"))
    track("/UHF", pcbnew.F_Cu, rf_plan.WIDTH, *RF_PLAN["/UHF"])


# ---- 5. GND stitching vias that now sit on other copper, holes, slots or keepouts
def seg_dist(q, a, b):
    dx, dy = b.x - a.x, b.y - a.y
    L2 = dx * dx + dy * dy or 1
    u = max(0, min(1, ((q.x - a.x) * dx + (q.y - a.y) * dy) / L2))
    return math.hypot(a.x + u * dx - q.x, a.y + u * dy - q.y)


def stitch(pts, off=1.05, pitch=2.5):
    """GND vias both sides of a polyline; the cull below drops the ones that do not fit."""
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        n = int(L // pitch)
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for i in range(n + 1):
            t = (L - n * pitch) / 2 + i * pitch
            for sgn in (-1, 1):
                q = P(a[0] + ux * t - uy * off * sgn, a[1] + uy * t + ux * off * sgn)
                via("GND", q)
                NEW_VIAS.append(q - delta)


if STAGE >= 5:
    for pts in RF_PLAN.values():
        stitch(pts)
    CLR = mm(0.25)
    RF_CLR = mm(0.45)  # RF netclass clearance is 0.4 mm
    items = [x for x in v.Tracks()]
    going = {p.GetNetname() for r in ("B1", "J6") for p in FP[r].Pads()} - {"GND", ""}
    staying = [f for f in [x for x in v.Footprints()] if f.GetReference() not in ("B1", "J6")]  # the dipole parts go in step 1
    pads = [p for f in staying for p in f.Pads()]
    edges = [d for d in v.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    edges += [g for f in staying for g in f.GraphicalItems() if g.GetLayer() == pcbnew.Edge_Cuts]
    gone = {(z.GetBoundingBox().GetX(), z.GetBoundingBox().GetY()) for z in dead_zones_pre}  # SWIG wrappers do not compare equal
    keepouts = [z for z in v.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()
                and (z.GetBoundingBox().GetX(), z.GetBoundingBox().GetY()) not in gone]
    dead_ids = {id(x) for x in DEAD}
    culled = 0
    for vi in items:
        if vi.GetClass() != "PCB_VIA" or vi.GetNetname() != "GND":
            continue
        q, r = vi.GetPosition(), vi.GetWidth() / 2
        mine = any(abs(q.x - w.x - delta.x) < 10 and abs(q.y - w.y - delta.y) < 10 for w in NEW_VIAS)
        bad = False
        for tr in items:
            if tr is vi or tr.GetNetname() in going:
                continue
            if tr.GetNetname() == "GND":
                if mine and tr.GetClass() == "PCB_VIA" and not any(tr is d for d in DEAD) and math.hypot(
                        tr.GetPosition().x - q.x, tr.GetPosition().y - q.y) < (vi.GetDrillValue() + tr.GetDrillValue()) / 2 + mm(0.55):
                    bad = True
                    break
                continue
            if not mine and not tr.GetNetname().startswith(("/RF/", "/UHF")):
                continue
            if tr.GetClass() == "PCB_VIA":
                bad = math.hypot(tr.GetPosition().x - q.x, tr.GetPosition().y - q.y) < r + tr.GetWidth() / 2 + CLR
            else:
                rf = tr.GetNetname().startswith(("/RF/", "/UHF"))
                bad = seg_dist(q, tr.GetStart(), tr.GetEnd()) < r + tr.GetWidth() / 2 + (RF_CLR if rf else CLR)
            if bad:
                break
        if not bad and mine:
            for p in pads:
                gap = RF_CLR if p.GetNetname() != "GND" else mm(0.15)  # no stitching via in a GND land either
                if p.GetLayerSet().Seq() and p.GetEffectiveShape(p.GetLayerSet().Seq()[0]).Collide(q, int(r + gap)):
                    bad = True
                    break
                if p.HasHole() and math.hypot(p.GetPosition().x - q.x, p.GetPosition().y - q.y) < vi.GetDrillValue() / 2 + max(p.GetDrillSize().x, p.GetDrillSize().y) / 2 + mm(0.3):
                    bad = True
                    break
        if not bad and mine:
            for e in edges:
                if e.GetShape() == pcbnew.SHAPE_T_SEGMENT and seg_dist(q, e.GetStart(), e.GetEnd()) < r + mm(0.5):
                    bad = True
                    break
                if e.GetShape() != pcbnew.SHAPE_T_SEGMENT and e.GetBoundingBox().Inflate(int(r + mm(0.5))).Contains(q):
                    bad = True
                    break
        if not bad and mine:
            bad = any(z.Outline().Contains(q) for z in keepouts)
        if bad:
            DEAD.append(vi)
            culled += 1
            if not mine and any(tr.GetClass() != "PCB_VIA" and tr.GetNetname() == "GND" and q in (tr.GetStart(), tr.GetEnd()) for tr in items):
                sys.exit(f"V2d GND via with a track on it would be culled at {pcbnew.ToMM(q.x) - CX:.2f}, {pcbnew.ToMM(q.y) - CY:.2f}")
    print("GND vias culled", culled)

# ---- 6. bind RF footprints to the schematic
if STAGE >= 6:
    FP2 = {f.GetReference(): f for f in [x for x in v.Footprints()]}
    comps = COMPS

    def bind(fp, ref):
        c = comps[ref]
        lib, name = c.findtext("footprint").split(":")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetValue(c.findtext("value"))
        fp.SetPath(pcbnew.KIID_PATH(c.find("sheetpath").get("tstamps") + c.findtext("tstamps")))
        fields = {f.get("name"): f.text or "" for f in c.iter("field")}
        for fname in ("MPN", "LCSC", "Description", "Datasheet"):
            if fields.get(fname):
                fld = fp.GetField(fname) if fp.HasField(fname) else None
                if fld is None:
                    fld = pcbnew.PCB_FIELD(fp, 0, fname)
                    fp.Add(fld)
                fld.SetText(fields[fname])
                fld.SetVisible(False)

    for ref in ["U301", "U302", "U303", "R301", "R302", "R303", "AE1", "AE2", "AE3", "AE4", "RF1"]:
        bind(FP2[ref], ref)
    for ref in ["AE1", "AE2", "AE3", "AE4"]:
        FP2[ref].SetAttributes(pcbnew.FP_SMD)

# ---- 7. silk and art
if STAGE >= 7:
    def near(item, x, y, tol=1.0):
        q = item.GetPosition()
        return abs(pcbnew.ToMM(q.x) - CX - x) < tol and abs(pcbnew.ToMM(q.y) - CY - y) < tol

    texts = [d for d in v.GetDrawings() if d.GetClass() == "PCB_TEXT"]
    for d in texts:
        if d.GetText() == "REMOVE FOR FLIGHT":  # R210 label sat just outside the charger box
            d.Move(pcbnew.VECTOR2I(mm(CHG_OFF[0]), mm(CHG_OFF[1])))
        if d.GetText() == "This is where the magic happens":  # sat on U301
            d.Move(pcbnew.VECTOR2I(0, mm(-3.6)))
        if d.GetText().startswith("3PySquared Antenna Board"):
            d.SetText(d.GetText().replace("\nV2d\n", "\nV3 (CP turnstile)\n"))
    # The inner-face PDF logo and its caption now sit on the charger: move them to the free south-west corner.
    logo_off = pcbnew.VECTOR2I(mm(-11.8), mm(54.5))
    for f in [x for x in v.Footprints()]:
        if f.GetReference() == "G***" and f.GetLayer() == pcbnew.F_Cu:
            r = f.GetBoundingBox(False, False)
            if abs(pcbnew.ToMM(r.GetX()) - CX + 24.2) < 0.3 and abs(pcbnew.ToMM(r.GetY()) - CY + 25.5) < 0.3:
                f.Move(logo_off)
    for d in texts:
        if d.GetText() == "bee_movie_script.txt":
            d.Move(logo_off)
    # Inner-face mask art (two shield logos, "NOT TODAY PROTON", "In another life") would open the mask over
    # U302, R302, AE1 and the RF lines. The inner face is not visible on an assembled cube: drop it.
    for f in [x for x in v.Footprints()]:
        if f.GetReference() == "G***" and f.GetLayer() == pcbnew.F_Cu:
            r = f.GetBoundingBox(False, False)
            x, y = pcbnew.ToMM(r.GetX()) - CX, pcbnew.ToMM(r.GetY()) - CY
            if (abs(x - 15.3) < 0.3 and abs(y + 27.4) < 0.3) or (abs(x - 15.3) < 0.3 and abs(y + 1.8) < 0.3):
                DEAD.append(f)
    for d in texts:
        if d.GetLayer() == pcbnew.F_Mask and d.GetText().startswith(("{dblquote}In another life", "NOT TODAY PROTON")):
            DEAD.append(d)
    FP["RF1"].Reference().SetVisible(False)

    # Outer-face art (bare-copper mask openings) now lies over the moved charger: cut it back 0.3 mm around every
    # B.Cu land and via there, so no opening bridges two nets and the charger's joints keep their mask dams.
    ART_BOX = pcbnew.BOX2I(P(-27.0, -37.0), pcbnew.VECTOR2I(mm(22.5), mm(22.5)))  # the charger block after its move
    cut = pcbnew.SHAPE_POLY_SET()
    for f in [x for x in v.Footprints()]:
        if f.GetReference() != "G***":
            for p in f.Pads():
                if p.IsOnLayer(pcbnew.B_Cu) and ART_BOX.Contains(p.GetPosition()):
                    p.TransformShapeToPolygon(cut, pcbnew.B_Cu, mm(0.3), mm(0.005), pcbnew.ERROR_OUTSIDE)
    for tr in [x for x in v.Tracks()]:
        if tr.GetClass() == "PCB_VIA" and ART_BOX.Contains(tr.GetPosition()) and tr not in DEAD:
            q, r = tr.GetPosition(), mm(0.3 + 0.3)
            cut.NewOutline()
            for i in range(24):
                cut.Append(int(q.x + r * math.cos(i * math.pi / 12)), int(q.y + r * math.sin(i * math.pi / 12)))
        elif tr.GetClass() == "PCB_TRACK" and tr.GetLayer() == pcbnew.B_Cu and tr.GetNetname() and tr not in DEAD \
                and (ART_BOX.Contains(tr.GetStart()) or ART_BOX.Contains(tr.GetEnd())):
            tr.TransformShapeToPolygon(cut, pcbnew.B_Cu, mm(0.2), mm(0.005), pcbnew.ERROR_OUTSIDE)
    cut.Simplify()

    def mask_poly(ps):
        ps.BooleanSubtract(cut)
        ps.Fracture()
        return ps

    for f in [x for x in v.Footprints()]:
        if f.GetReference() == "G***" and f.GetBoundingBox(False).Intersects(ART_BOX):
            for g in f.GraphicalItems():
                if g.GetLayer() == pcbnew.B_Mask and g.GetShape() == pcbnew.SHAPE_T_POLY:
                    g.SetPolyShape(mask_poly(g.GetPolyShape()))
    for d in texts:
        if d.GetText() == "THE PLEIADES FIVE":  # along its band to the part the charger does not reach
            d.Move(pcbnew.VECTOR2I(mm(-8.5), 0))
    lines = [d for d in v.GetDrawings() if d.GetClass() == "PCB_SHAPE" and d.GetLayer() == pcbnew.B_Mask
             and d.GetShape() == pcbnew.SHAPE_T_SEGMENT and d.GetBoundingBox().Intersects(ART_BOX)]
    for d in texts + lines:
        if d.GetLayer() == pcbnew.B_Mask and d.GetBoundingBox().Intersects(ART_BOX):
            ps = pcbnew.SHAPE_POLY_SET()
            if d.GetClass() == "PCB_TEXT":
                d.TransformTextToPolySet(ps, 0, mm(0.005), pcbnew.ERROR_INSIDE)
            else:
                d.TransformShapeToPolygon(ps, pcbnew.B_Mask, 0, mm(0.005), pcbnew.ERROR_INSIDE)
            ps = mask_poly(ps)
            for i in range(ps.OutlineCount()):  # one shape per glyph piece
                one = pcbnew.SHAPE_POLY_SET()
                one.AddOutline(ps.Outline(i))
                g = pcbnew.PCB_SHAPE(v, pcbnew.SHAPE_T_POLY)
                g.SetLayer(pcbnew.B_Mask)
                g.SetFilled(True)
                g.SetWidth(0)
                g.SetPolyShape(one)
                v.Add(g)
            DEAD.append(d)
# ---- 1. drop the dipole (removals last)
drop_nets = set()
for ref in ("B1", "J6"):
    f = FP[ref]
    for p in f.Pads():
        if p.GetNetname() not in ("GND", ""):
            drop_nets.add(p.GetNetname())
dead_tracks = [tr for tr in V_TRACKS if tr.GetNetname() in drop_nets]
dead_zones = []
for z in v.Zones():
    r = z.GetBoundingBox()
    x, y = pcbnew.ToMM(r.GetX()) - CX, pcbnew.ToMM(r.GetY()) - CY
    if abs(x + 32.7) < 0.3 and abs(y - 14.7) < 0.3:  # dipole-window rule areas (F/B/In2 and In1)
        dead_zones.append(z)
    elif z.GetNetname() == "GND" and abs(x + 2.1) < 0.3 and abs(y - 14.7) < 0.3:  # balun ground island on In1
        dead_zones.append(z)
    elif z.GetLayerSet().Contains(pcbnew.F_Mask) and abs(x - 0.3) < 0.3 and abs(y - 12.8) < 0.3:
        dead_zones.append(z)
for tr in dead_tracks + DEAD:
    v.Remove(tr)
for z in dead_zones:
    v.Remove(z)
for ref in ("B1", "J6"):
    v.Remove(FP[ref])

v.SynchronizeNetsAndNetClasses(False)  # new nets pick up the RF netclass (0.4 mm CPWG gap) before the fill
pcbnew.ZONE_FILLER(v).Fill(v.Zones())
v.Save(OUT)
print(f"stage {STAGE}: rf placed, dropped nets {sorted(drop_nets)}, zones removed {len(dead_zones)}, tracks removed {len(dead_tracks)}")
