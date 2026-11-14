#!/usr/bin/env python3
"""Build antenna_top_cap_v3.kicad_pcb: V2d interface + turnstile CP RF block (run with KiCad's Python).

usage: build_v3.py <v2d board> <turnstile board> <netlist.xml> <kicad footprints dir> <out board> [stage]
Starts from the V2d board every run, so reruns are idempotent.
  1. Drop the dipole: B1, J6, their nets, and the dipole-window keepouts / balun ground island.
  2. Transplant the turnstile RF block (U1-U3, R1-R3, AE1-AE4, RF tracks, GND stitching) at its own
     coordinates. Lengths of the 90-degree delay line and element feeds are kept exactly.
  3. Move the charger block (rigid) off the +Y-up (north) element, and re-run its two outside links.
  4. Move J7 (burn wire) and RF1 (MMCX) out of the delay line, route BURN and the UHF feed.
  5. Drop GND stitching vias that now land on other copper, holes, slots or keepouts.
  6. Bind the RF footprints to the V3 schematic (library IDs, values, fields, symbol paths); the hybrid
     isolated-port loads become 1206 parts with the TERM pad where the 0603 TERM pad was.
"""
import math
import sys
import xml.etree.ElementTree as ET

import pcbnew

V2D, TURN, NETLIST, FPDIR, OUT = sys.argv[1:6]
STAGE = int(sys.argv[6]) if len(sys.argv) > 6 else 9
mm = pcbnew.FromMM

RF_REFS = ["U1", "U2", "U3", "R1", "R2", "R3", "AE1", "AE2", "AE3", "AE4"]
REF_V3 = {"U1": "U301", "U2": "U302", "U3": "U303", "R1": "R301", "R2": "R302", "R3": "R303"}  # V2d already uses R1, U3
# turnstile net -> V3 schematic net
NETMAP = {
    "/UHF": "/UHF",
    "/UHF-SHORT": "/RF/UHF_A",
    "/UHF-SHORT+1{slash}4WAVE": "/RF/UHF_B",
    "/UHF_0": "/RF/UHF_0",
    "/UHF_90": "/RF/UHF_90",
    "/UHF_180": "/RF/UHF_180",
    "/UHF_270": "/RF/UHF_270",
    "Net-(U1-TERM)": "/RF/TERM1",
    "Net-(U2-TERM)": "/RF/TERM2",
    "Net-(U3-TERM)": "/RF/TERM3",
}
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


# ---- 2. transplant (adds first: removing items before iterating others upsets the SWIG wrappers)
rf_src = [tr for tr in T_TRACKS if tr.GetNetname() in NETMAP and tr.GetNetname() != "/UHF"]


def near_rf(pos, r=4.0e6):
    for tr in rf_src:
        if tr.GetClass() == "PCB_VIA":
            continue
        a, b = tr.GetStart(), tr.GetEnd()
        dx, dy = b.x - a.x, b.y - a.y
        L2 = dx * dx + dy * dy or 1
        u = max(0, min(1, ((pos.x - a.x) * dx + (pos.y - a.y) * dy) / L2))
        if math.hypot(a.x + u * dx - pos.x, a.y + u * dy - pos.y) < r:
            return True
    return False


NEW_VIAS = []
for f in T_FPS:
    if f.GetReference() not in RF_REFS:
        continue
    nf = pcbnew.FOOTPRINT(f)
    nf.SetReference(REF_V3.get(f.GetReference(), f.GetReference()))
    for p in nf.Pads():
        if p.GetNetname():
            p.SetNet(net(NETMAP.get(p.GetNetname(), p.GetNetname())))
    v.Add(nf)
    nf.Move(delta)
for tr in T_TRACKS:
    n = tr.GetNetname()
    keep = (n in NETMAP and n != "/UHF") or (tr.GetClass() == "PCB_VIA" and n == "GND" and near_rf(tr.GetPosition()))
    if not keep:
        continue
    nt = tr.Duplicate().Cast()
    nt.SetNet(net(NETMAP.get(n, n)))
    v.Add(nt)
    if nt.GetClass() == "PCB_VIA":
        NEW_VIAS.append(nt.GetPosition())
    nt.Move(delta)

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
    DEAD.append(seg(VB, (7.4, -32.72), (-9.15, -32.72)))
    DEAD.append(seg(VB, (7.4, -39.92), (7.4, -32.72)))
    chg_nets = {p.GetNetname() for r in CHG_REFS for p in FP[r].Pads()} - {VB}
    move_block(CHG_REFS, *CHG_OFF, only_nets=chg_nets)
    for tr in V_TRACKS:  # charger-internal VBUS copper moves with the block
        if tr.GetNetname() == VB and tr not in DEAD:
            q = tr.GetStart()
            if pcbnew.ToMM(q.y) - CY > -35.0 and pcbnew.ToMM(q.x) - CX < 0:
                tr.Move(pcbnew.VECTOR2I(mm(CHG_OFF[0]), mm(CHG_OFF[1])))
    vd = (-9.15 + CHG_OFF[0], -32.72 + CHG_OFF[1])
    track(VB, pcbnew.B_Cu, 1.0, (7.4, -39.92), (7.4, -35.2), (vd[0] + 0.52, -35.2), vd)
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

# ---- 4. burn wire and MMCX out of the delay line
def gnd_in(x0, y0, x1, y1):
    """V2d GND tracks with both ends inside a board-centred box."""
    A, B = P(x0, y0), P(x1, y1)
    ins = lambda q: A.x <= q.x <= B.x and A.y <= q.y <= B.y
    return [tr for tr in V_TRACKS if tr.GetNetname() == "GND" and tr.GetClass() != "PCB_VIA" and ins(tr.GetStart()) and ins(tr.GetEnd())]


# GND ties left floating once J7 moves and B1 goes; a floating track takes the net of whatever it touches on fill.
DEAD.extend(gnd_in(-12.0, 9.8, -5.0, 14.0))  # J7 pin-2 ties
DEAD.extend(gnd_in(-1.6, 13.5, 0.3, 19.0))  # B1 ground
if STAGE >= 4:
    move_block(["J7"], 0, 8.5, only_nets={"BURN"}, bridge=True)
    rf1 = FP["RF1"]
    rf1.SetPosition(P(24.15, 28.35))
    rf1.SetOrientationDegrees(45)
    for p in rf1.Pads():
        if p.GetNumber() == "5":
            p.SetNet(net("/UHF"))
    track("/UHF", pcbnew.F_Cu, 0.3424, P(24.15, 28.35), pad("U301", "1").GetPosition())

# ---- 5. GND stitching vias that now sit on other copper, holes, slots or keepouts
def seg_dist(q, a, b):
    dx, dy = b.x - a.x, b.y - a.y
    L2 = dx * dx + dy * dy or 1
    u = max(0, min(1, ((q.x - a.x) * dx + (q.y - a.y) * dy) / L2))
    return math.hypot(a.x + u * dx - q.x, a.y + u * dy - q.y)


if STAGE >= 5:
    CLR = mm(0.25)
    items = [x for x in v.Tracks()]
    pads = [p for f in [x for x in v.Footprints()] for p in f.Pads()]
    edges = [d for d in v.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    edges += [g for f in [x for x in v.Footprints()] for g in f.GraphicalItems() if g.GetLayer() == pcbnew.Edge_Cuts]
    keepouts = [z for z in v.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias() and z not in dead_zones_pre]
    dead_ids = {id(x) for x in DEAD}
    culled = 0
    for vi in items:
        if vi.GetClass() != "PCB_VIA" or vi.GetNetname() != "GND":
            continue
        q, r = vi.GetPosition(), vi.GetWidth() / 2
        mine = any(abs(q.x - w.x - delta.x) < 10 and abs(q.y - w.y - delta.y) < 10 for w in NEW_VIAS)
        bad = False
        for tr in items:
            if tr is vi:
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
                bad = seg_dist(q, tr.GetStart(), tr.GetEnd()) < r + tr.GetWidth() / 2 + CLR
            if bad:
                break
        if not bad and mine:
            for p in pads:
                if p.GetNetname() != "GND" and p.GetEffectiveShape(p.GetLayerSet().Seq()[0]).Collide(q, int(r + CLR)):
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
    print("GND vias culled", culled)

# ---- 6. bind RF footprints to the schematic
if STAGE >= 6:
    root = ET.parse(NETLIST).getroot()
    comps = {c.get("ref"): c for c in root.iter("comp")}
    pinnet = {(n2.get("ref"), n2.get("pin")): n.get("name") for n in root.iter("net") for n2 in n.iter("node")}
    IO = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

    def bind(fp, ref):
        c = comps[ref]
        lib, name = c.findtext("footprint").split(":")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetValue(c.findtext("value"))
        fp.SetPath(pcbnew.KIID_PATH(c.find("sheetpath").get("tstamps") + c.findtext("tstamps")))
        fields = {f.get("name"): f.text or "" for f in c.iter("field")}
        for fname in ("MPN", "Description", "Datasheet"):
            if fields.get(fname):
                fld = fp.GetField(fname) if fp.HasField(fname) else None
                if fld is None:
                    fld = pcbnew.PCB_FIELD(fp, 0, fname)
                    fp.Add(fld)
                fld.SetText(fields[fname])
                fld.SetVisible(False)

    for ref in ["U301", "U302", "U303", "AE1", "AE2", "AE3", "AE4", "RF1"]:
        bind(FP[ref], ref)
    for ref in ["AE1", "AE2", "AE3", "AE4"]:
        FP[ref].SetAttributes(pcbnew.FP_SMD)
    for ref in ["U301", "U302", "U303"]:
        FP[ref].Reference().SetVisible(False)  # V2d shows only connector refs on silk
    for ref in ["R301", "R302", "R303"]:
        old = FP[ref]
        pads = {p.GetNumber(): p.GetPosition() for p in old.Pads()}
        term, gndp = pads["2"], pads["1"]  # turnstile R1-R3: pad 2 on TERM, pad 1 on GND
        new = IO.FootprintLoad(f"{FPDIR}/Resistor_SMD.pretty", "R_1206_3216Metric")
        new.SetReference(ref)
        v.Add(new)
        ux, uy = gndp.x - term.x, gndp.y - term.y
        for deg in range(0, 360, 45):
            new.SetOrientationDegrees(deg)
            new.SetPosition(pcbnew.VECTOR2I(0, 0))
            q = {p.GetNumber(): p.GetPosition() for p in new.Pads()}
            dx, dy = q["2"].x - q["1"].x, q["2"].y - q["1"].y
            if dx * ux + dy * uy > 0.99 * math.hypot(dx, dy) * math.hypot(ux, uy):
                break
        new.SetPosition(pcbnew.VECTOR2I(term.x - q["1"].x, term.y - q["1"].y))
        for p in new.Pads():
            p.SetNet(net(pinnet[(ref, p.GetNumber())]))
        bind(new, ref)
        new.Reference().SetVisible(False)
        DEAD.append(old)

# ---- 7. silk and art
if STAGE >= 7:
    def near(item, x, y, tol=1.0):
        q = item.GetPosition()
        return abs(pcbnew.ToMM(q.x) - CX - x) < tol and abs(pcbnew.ToMM(q.y) - CY - y) < tol

    texts = [d for d in v.GetDrawings() if d.GetClass() == "PCB_TEXT"]
    for d in texts:
        if d.GetText() == "REMOVE FOR FLIGHT":  # R210 label sat just outside the charger box
            d.Move(pcbnew.VECTOR2I(mm(CHG_OFF[0]), mm(CHG_OFF[1])))
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
