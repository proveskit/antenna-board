#!/usr/bin/env python3
"""Generate charger_swd.kicad_sch (V2d USB charger + SWD pass-through sheet).

Rerun to regenerate the sheet; UUIDs are derived from names so output is stable.
Usage: gen_charger_sheet.py <kicad stock symbols dir> <out .kicad_sch> <root uuid> <sheet uuid> <project>
"""
import math
import re
import sys
import uuid

LIBDIR, OUT, ROOT_UUID, SHEET_UUID, PROJECT = sys.argv[1:6]
NS = uuid.UUID(SHEET_UUID)


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def find_block(text, start):
    depth = 0
    i = start
    while True:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1


_libcache = {}


def lib_symbol(lib_id):
    lib, name = lib_id.split(":")
    if lib_id in _libcache:
        return _libcache[lib_id]
    text = open(f"{LIBDIR}/{lib}.kicad_sym").read()
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(name), text)
    block = find_block(text, m.start() + 2)
    assert "(extends" not in block, lib_id
    block = block.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    pins = {}
    for pm in re.finditer(r'\(pin (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*\(length ([-\d.]+)\)(.*?)\(number "([^"]*)"', block, re.S):
        pins.setdefault(pm.group(8), (float(pm.group(3)), float(pm.group(4))))
    _libcache[lib_id] = (block, pins)
    return _libcache[lib_id]


def g(v):
    return round(round(v / 1.27) * 1.27, 4)


items = []
used_libs = []


def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def prop(name, value, x, y, hide=False, size=1.27, justify=None, angle=0):
    j = f"\n\t\t\t\t(justify {justify})" if justify else ""
    h = "\n\t\t\t(hide yes)" if hide else ""
    return (f'\t\t(property "{name}" "{value}"\n\t\t\t(at {fmt(x)} {fmt(y)} {angle}){h}\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
            f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size {size} {size})\n\t\t\t\t){j}\n\t\t\t)\n\t\t)\n')


class Sym:
    def __init__(self, lib_id, ref, value, x, y, rot=0, mirror=False, fp="", lcsc="", mpn="", desc="", ds="",
                 in_bom=True, ref_at=None, val_at=None, hide_value=False, power=False):
        self.lib_id, self.ref, self.x, self.y, self.rot, self.mirror = lib_id, ref, x, y, rot, mirror
        block, self.libpins = lib_symbol(lib_id)
        if lib_id not in used_libs:
            used_libs.append(lib_id)
        u = uid("sym", ref, x, y)
        mir = "\n\t\t(mirror y)" if mirror else ""
        s = (f'\t(symbol\n\t\t(lib_id "{lib_id}")\n\t\t(at {fmt(x)} {fmt(y)} {rot}){mir}\n\t\t(unit 1)\n\t\t(body_style 1)\n'
             f'\t\t(exclude_from_sim no)\n\t\t(in_bom {"yes" if in_bom else "no"})\n\t\t(on_board {"no" if power else "yes"})\n'
             f'\t\t(in_pos_files {"no" if power else "yes"})\n\t\t(dnp no)\n\t\t(uuid "{u}")\n')
        rx, ry = ref_at or (x + 2.54, y - 1.27)
        vx, vy = val_at or (x + 2.54, y + 1.27)
        ang = 90 if rot in (90, 270) else 0
        s += prop("Reference", ref, rx, ry, hide=power, justify=None if power else "left", angle=ang)
        s += prop("Value", value, vx, vy, hide=hide_value, justify=None if power else "left", angle=ang)
        s += prop("Footprint", fp, x, y, hide=True)
        s += prop("Datasheet", ds, x, y, hide=True)
        s += prop("Description", desc, x, y, hide=True)
        if lcsc:
            s += prop("LCSC", lcsc, x, y, hide=True)
        if mpn:
            s += prop("MPN", mpn, x, y, hide=True)
        for num in self.libpins:
            s += f'\t\t(pin "{num}"\n\t\t\t(uuid "{uid("pin", ref, num)}")\n\t\t)\n'
        s += (f'\t\t(instances\n\t\t\t(project "{PROJECT}"\n\t\t\t\t(path "/{ROOT_UUID}/{SHEET_UUID}"\n'
              f'\t\t\t\t\t(reference "{ref}")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
        items.append(s)

    def p(self, num):
        px, py = self.libpins[str(num)]
        if self.mirror:
            px = -px
        a = math.radians(self.rot)
        X = px * math.cos(a) - py * math.sin(a)
        Y = px * math.sin(a) + py * math.cos(a)
        return (round(self.x + X, 4), round(self.y - Y, 4))


_pwr = [0]


def gnd(pt, hide=False):
    _pwr[0] += 1
    Sym("power:GND", f"#PWR0{200 + _pwr[0]}", "GND", pt[0], pt[1], power=True, hide_value=hide,
        val_at=(pt[0], pt[1] + 3.81))


def flag(ref, pt):
    Sym("power:PWR_FLAG", ref, "PWR_FLAG", pt[0], pt[1], power=True, hide_value=True)


def noconnect(pt):
    items.append(f'\t(no_connect\n\t\t(at {fmt(pt[0])} {fmt(pt[1])})\n\t\t(uuid "{uid("nc", pt)}")\n\t)\n')


def wire(*pts):
    for a, b in zip(pts, pts[1:]):
        items.append(f'\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(a[0])} {fmt(a[1])}) (xy {fmt(b[0])} {fmt(b[1])})\n\t\t)\n'
                     f'\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "{uid("w", a, b)}")\n\t)\n')


def junction(pt):
    items.append(f'\t(junction\n\t\t(at {fmt(pt[0])} {fmt(pt[1])})\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "{uid("j", pt)}")\n\t)\n')


def label(name, pt, rot=0):
    just = "right bottom" if rot == 180 else "left bottom"
    items.append(f'\t(label "{name}"\n\t\t(at {fmt(pt[0])} {fmt(pt[1])} {rot})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
                 f'\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{uid("l", name, pt)}")\n\t)\n')


def hlabel(name, pt, shape, rot=180):
    just = "right" if rot == 180 else "left"
    items.append(f'\t(hierarchical_label "{name}"\n\t\t(shape {shape})\n\t\t(at {fmt(pt[0])} {fmt(pt[1])} {rot})\n'
                 f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{uid("h", name)}")\n\t)\n')


def text(s, x, y, size=1.27, bold=False):
    s = s.replace('"', '\\"').replace("\n", "\\n")
    b = "\n\t\t\t\t(bold yes)" if bold else ""
    items.append(f'\t(text "{s}"\n\t\t(exclude_from_sim no)\n\t\t(at {fmt(x)} {fmt(y)} 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size}){b}\n\t\t\t)\n'
                 f'\t\t\t(justify left top)\n\t\t)\n\t\t(uuid "{uid("t", s[:40], x, y)}")\n\t)\n')


R0603 = "Resistor_SMD:R_0603_1608Metric"
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
TI_DS = "https://www.ti.com/lit/ds/symlink/bq25886.pdf"


def res(ref, val, x, ytop, lcsc, desc, fp=R0603):
    """Vertical resistor whose top pin ends at (x, ytop). Returns (top, bottom)."""
    r = Sym("Device:R", ref, val, x, ytop + 3.81, fp=fp, lcsc=lcsc, desc=desc,
            ref_at=(x + 2.54, ytop + 2.54), val_at=(x + 2.54, ytop + 5.08))
    return r.p(1), r.p(2)


def cap(ref, val, x, ytop, lcsc, desc, fp=C0805, to_gnd=True):
    c = Sym("Device:C", ref, val, x, ytop + 3.81, fp=fp, lcsc=lcsc, desc=desc,
            ref_at=(x + 2.54, ytop + 2.54), val_at=(x + 2.54, ytop + 5.08))
    if to_gnd:
        gnd(c.p(2))
    return c.p(1), c.p(2)


# ---------------------------------------------------------------- U201 core
U = Sym("Battery_Management:BQ25886RGE", "U201", "BQ25886RGER", 101.6, 88.9,
        fp="Package_DFN_QFN:Texas_RGE0024H_VQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm", lcsc="C2765094",
        desc="Standalone 2S boost charger, 5 V USB input", ds=TI_DS, ref_at=(96.52, 64.77), val_at=(96.52, 67.31))
P = {n: U.p(n) for n in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "15", "17", "21", "23", "24"]}

# VBUS input from the sheet pin, with C201 at the pin.
# J204: charge-only USB-C. 5.1k Rd on each CC makes it a sink, so a PD source stays at 5 V.
JC = Sym("Connector:USB_C_Receptacle_USB2.0_16P", "J204", "CHARGE", 30.48, 60.96,
         fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948", mpn="TYPE-C-31-M-12",
         desc="Charge-only USB-C on the outer face; data pins not connected", ref_at=(22.86, 35.56), val_at=(22.86, 33.02))
gnd(JC.p("A1"))
gnd(JC.p("SH"))
vin = (60.96, P["23"][1])
wire(JC.p("A4"), (60.96, JC.p("A4")[1]), vin)
label("VBUS_CHG", vin)
for pin, x, ref in (("A5", 55.88, "R208"), ("B5", 50.8, "R209")):
    wire(JC.p(pin), (x, JC.p(pin)[1]))
    t, b = res(ref, "5.1k", x, JC.p(pin)[1], "C23186", "CC pull-down Rd: USB-C sink, 5 V only")
    gnd(b)
for pin in ("A6", "B6", "A7", "B7", "A8", "B8"):
    noconnect(JC.p(pin))
cx = 76.2
wire(vin, (cx, vin[1]))
wire((cx, vin[1]), P["23"])
junction((cx, vin[1]))
cap("C201", "1uF", cx, vin[1], "C15849", "VBUS bypass, 50 V", fp=C0603)
flag("#FLG0201", (68.58, vin[1]))
junction((68.58, vin[1]))

# D+ tied to D- locally: BC1.2 sees a DCP, ILIM then sets the input limit.
xd = 86.36
wire(P["24"], (xd, P["24"][1]), (xd, P["1"][1]), P["1"])

# OTG and CE tied low: OTG high would boost the battery back out of VBUS.
xo = 86.36
wire(P["5"], (xo, P["5"][1]))
wire(P["3"], (xo, P["3"][1]))
wire((xo, P["5"][1]), (xo, P["3"][1]))
junction((xo, P["3"][1]))
gnd((xo, P["3"][1]), hide=True)

# ICHGSET / VSET / ILIM fan out to resistors to GND.
ytop = 114.3
for pin, x, ref, val, lcsc, desc in [
    ("10", 66.04, "R201", "3.9k", "C51721", "ICHGSET: ICHG = 3.9k / 3810 = 1.02 A"),
    ("6", 76.2, "R203", "0", "C17168", "VSET to GND: 8.2 V float (DNP for 8.4 V)"),
    ("8", 86.36, "R202", "820", "C25135", "ILIM: IINDPM = 1110 / 820 = 1.35 A"),
]:
    wire(P[pin], (x, P[pin][1]), (x, ytop))
    t, b = res(ref, val, x, ytop, lcsc, desc, fp=R0402)
    gnd(b)

gnd(P["4"])

# Right side pins get short stubs to named nets.
noconnect(P["9"])
for pin, name in [("2", "CHG_STAT"), ("21", "PMID"), ("17", "SW"), ("12", "BTST"),
                  ("15", "SYS"), ("13", "CHG_BAT"), ("11", "REGN"), ("7", "TS")]:
    end = (P[pin][0] + 7.62, P[pin][1])
    wire(P[pin], end)
    label(name, end)

# ---------------------------------------------------------------- power stage
# PMID bus: C202/C203, then L201 to SW.
yb = 50.8
label("PMID", (134.62, yb))
wire((134.62, yb), (139.7, yb), (160.02, yb))
junction((139.7, yb))
cap("C202", "22uF", 139.7, yb, "C45783", "PMID input cap, 25 V X5R (VBUS + PMID >= 10 uF after derating)")
L = Sym("Device:L", "L201", "1uH", 163.83, yb, rot=90, fp="Inductor_SMD:L_Changjiang_FNR4030S", lcsc="C167865",
        mpn="FNR4030S1R0MT", desc="1 uH, Isat 5.7 A, 18 mOhm", ref_at=(161.29, yb - 3.81), val_at=(161.29, yb - 6.35))
ll, lr = sorted([L.p(1), L.p(2)])
wire((160.02, yb), ll)
wire(lr, (175.26, yb))
label("SW", (175.26, yb))
junction((170.18, yb))
flag("#FLG0202", (170.18, yb))

# Bootstrap cap BTST to SW.
yt = 63.5
label("BTST", (172.72, yt))
Cb = Sym("Device:C", "C208", "47nF", 182.88, yt, rot=90, fp=C0603, lcsc="C1622", desc="Bootstrap cap",
         ref_at=(181.61, yt - 5.08), val_at=(181.61, yt - 2.54))
a, b = sorted([Cb.p(1), Cb.p(2)])
wire((172.72, yt), a)
wire(b, (193.04, yt))
label("SW", (193.04, yt))

# SYS (boost output): 3 x 22uF.
ys = 76.2
label("SYS", (134.62, ys))
wire((134.62, ys), (139.7, ys), (149.86, ys), (160.02, ys))
for i, x in enumerate([139.7, 149.86, 160.02]):
    if x != 160.02:
        junction((x, ys))
    cap(f"C20{4 + i}", "22uF", x, ys, "C12891", "SYS output cap, 25 V X5R 1206: about 14 uF each at 8.2 V, 3 x 14 = 42 uF vs 44 uF", fp=C1206)

# BAT: C207, F201, CHG LINK J203 to the battery tap.
ybat = 101.6
label("CHG_BAT", (134.62, ybat))
wire((134.62, ybat), (139.7, ybat), (144.78, ybat))
junction((139.7, ybat))
cap("C207", "22uF", 139.7, ybat, "C12891", "BAT cap, 25 V X5R 1206: about 14 uF at 8.2 V (>= 10 uF)", fp=C1206)
F = Sym("Device:Fuse", "F201", "1.5A", 148.59, ybat, rot=90, fp="Fuse:Fuse_1206_3216Metric", lcsc="C187598",
        mpn="046601.5NRHF", desc="1.5 A fast fuse (1.02 A charge = 68 % of rating), 63 V, 50 A interrupt", ref_at=(146.05, ybat - 3.81), val_at=(146.05, ybat - 6.35))
fa, fb = sorted([F.p(1), F.p(2)])
wire((144.78, ybat), fa)
wire(fb, (154.94, ybat))
label("CHG_FUSED", (154.94, ybat))
J3 = Sym("Connector_Generic:Conn_01x02", "J203", "CHG LINK", 172.72, ybat,
         fp="Connector_PinHeader_2.00mm:PinHeader_1x02_P2.00mm_Vertical", desc="Charger to battery link, 2.0 mm pitch so its shunt cannot fit J2; remove for flight",
         ref_at=(172.72, ybat - 2.54), val_at=(172.72, ybat + 5.08))
wire((154.94, ybat), J3.p(1))
p2 = J3.p(2)
wire(p2, (p2[0] - 2.54, p2[1]), (p2[0] - 2.54, p2[1] + 5.08), (177.8, p2[1] + 5.08))
hlabel("Dir_Chrg_In", (177.8, p2[1] + 5.08), "passive", rot=0)

# REGN: C209, TS divider, status LEDs.
yr = 121.92
label("REGN", (134.62, yr))
wire((134.62, yr), (139.7, yr), (149.86, yr), (180.34, yr))
junction((139.7, yr))
cap("C209", "4.7uF", 139.7, yr, "C19666", "REGN bypass", fp=C0603)
junction((149.86, yr))
t, b = res("R204", "10k", 149.86, yr, "C25744", "TS top (REGN to TS)", fp=R0402)
r5t, r5b = res("R205", "12k", 149.86, b[1], "C25752", "TS bottom: TS = 12/22 = 54.5 % of REGN", fp=R0402)
gnd(r5b)
junction(b)
wire(b, (157.48, b[1]))
label("TS", (157.48, b[1]))
label("VBUS_CHG", (167.64, yr - 7.62))
for x, ytop, rref, dref, col, net, dlcsc, dfp, rdesc in [
    (167.64, yr - 7.62, "R206", "D201", "Green", None, "C2297", "LED_SMD:LED_0805_2012Metric", "USB 5 V present: (5 - 2.8) / 4.7k = 0.5 mA; 85 mW at a 20 V fault"),
    (180.34, yr, "R207", "D202", "Red", "CHG_STAT", "C2286", "LED_SMD:LED_0603_1608Metric", "STAT LED: (REGN - 2) / 2.2k = 1.4 mA"),
]:
    rval, rlcsc = ("4.7k", "C23162") if rref == "R206" else ("2.2k", "C4190")
    t, b = res(rref, rval, x, ytop, rlcsc, rdesc)
    D = Sym("Device:LED", dref, col, x, b[1] + 3.81, rot=90, fp=dfp, lcsc=dlcsc, desc=f"{col} status LED",
            ref_at=(x + 5.08, b[1] + 2.54), val_at=(x + 5.08, b[1] + 5.08))
    k, a = D.p(1), D.p(2)
    top, bot = (a, k) if a[1] < k[1] else (k, a)
    wire(b, top)
    if net:
        wire(bot, (x, bot[1] + 2.54))
        label(net, (x, bot[1] + 2.54))
    else:
        gnd(bot)

# ---------------------------------------------------------------- SWD pass-through
ysw = 160.02
J1 = Sym("Connector_Generic:Conn_01x03", "J201", "SWD from FC", 50.8, ysw, mirror=True,
         fp="Connector_JST:JST_SH_BM03B-SRSS-TB_1x03-1MP_P1.00mm_Vertical", lcsc="C160389", mpn="BM03B-SRSS-TB(LF)(SN)",
         desc="Inner side; 1:1 JST-SH cable to FC J22", ref_at=(45.72, ysw - 6.35), val_at=(45.72, ysw - 8.89))
J2 = Sym("Connector_Generic:Conn_01x03", "J202", "SWD", 96.52, ysw,
         fp="Connector_JST:JST_SH_BM03B-SRSS-TB_1x03-1MP_P1.00mm_Vertical", lcsc="C160389", mpn="BM03B-SRSS-TB(LF)(SN)",
         desc="Outer side; Raspberry Pi Debug Probe pinout", ref_at=(93.98, ysw - 6.35), val_at=(93.98, ysw - 8.89))
for pin, net in [("1", "SWCLK"), ("3", "SWDIO")]:
    wire(J1.p(pin), J2.p(pin))
    label(net, (J1.p(pin)[0] + 10.16, J1.p(pin)[1]))
wire(J1.p("2"), J2.p("2"))
junction((73.66, J1.p("2")[1]))
wire((73.66, J1.p("2")[1]), (73.66, J1.p("2")[1] + 5.08))
gnd((73.66, J1.p("2")[1] + 5.08))

# ---------------------------------------------------------------- notes
text("V2d USB charger (BQ25886, standalone 2S boost)", 25.4, 22.86, size=2.0, bold=True)
text("Input = J204 CHARGE USB-C, 5 V only. CC1/CC2 have 5.1k Rd (R208/R209), so a USB-PD source never offers more than 5 V.\n"
     "VBUS operating 4.3 to 6.2 V, OVP 6.2 V, abs max 20 V. VINDPM 4.3 V backs the charger off on a weak port.\n"
     "IINDPM = KILIM / RILIM = 1110 / 820 = 1.35 A (Type-C 1.5 A level). ICHG = 3.9k / 3810 = 1.02 A max; at 1.35 A in, about 0.75 A reaches the pack.\n"
     "VBUS = (4.3, 5.0, 6.2) V @ (0, 1.2, 1.35) A. CHG_BAT = (6.0, 7.4, 8.2) V @ (0, 0.7, 1.02) A.\n"
     "ICHG stays at or under 1.02 A: Dir_Chrg_In reaches the FC on one 24 AWG harness conductor (J1 pin 6).", 25.4, 27.94)
text("D+ tied to D-: BC1.2 detects a DCP (3 A), so ILIM governs.\n"
     "J204 data pins are not connected (charge only).", 25.4, 90.17)
text("OTG and ~{CE} hard tied to GND.\n"
     "OTG high would boost the battery back\n"
     "out of VBUS: never leave it floating.", 25.4, 99.06)
text("VSET: 0 Ohm = 8.2 V (4.1 V/cell, chosen for\n"
     "margin with no cell balancing).\n"
     "DNP R203 (> 150k) = 8.4 V. Never fit 75k or 39k\n"
     "(8.7 V / 8.8 V would overcharge Molicel cells).", 25.4, 127.0)
text("TS: fixed 10k/12k divider = 54.5 % of REGN, inside the\n"
     "45 C (44.75 %) to 10 C (68.25 %) normal window.\n"
     "No cell thermistor reaches this board. IC thermal\n"
     "shutdown and the 12 h safety timer still apply.", 198.12, 128.27)
text("Battery tap safety", 198.12, 86.36, size=1.524, bold=True)
text("Dir_Chrg_In is the raw pack + (upstream of every\n"
     "positive inhibit). Charge current returns through\n"
     "FC GND and the ground-side inhibit, as with J2.\n"
     "F201 opens on a charger or cap short.\n"
     "J203 CHG LINK: fit for bench charging; REMOVE FOR\n"
     "FLIGHT so no charger part hangs on the pack.\n"
     "Battery-only drain with link fitted: 12 uA typ, 20 uA max.\n"
     "ATP: link out, Dir_Chrg_In to GND leakage < 1 uA.\n"
     "ATP: 5 V in, 7.4 V load: green on, red on,\n"
     "charge 0.7 to 1.0 A (input-limited at 1.35 A in).\n"
     "J2 and J203 use different pitches (2.54 / 2.0 mm):\n"
     "a shunt on J2 would short the pack.", 198.12, 90.17)
text("Status LEDs (outer side): green = USB 5 V present;\n"
     "red on = charging, off = done, 1 Hz blink = fault.", 198.12, 148.59)
text("SWD pass-through", 25.4, 144.78, size=2.0, bold=True)
text("FC J22 is unreachable on an assembled cube. A 1:1 JST-SH 3-pin cable (pin 1 to pin 1)\n"
     "runs from FC J22 to J201 on the inner side; J202 on the outer side takes the Raspberry Pi\n"
     "Debug Probe cable. Pinout matches FC J22: 1 SWCLK, 2 GND, 3 SWDIO. No parts in series.", 25.4, 172.72)

# ---------------------------------------------------------------- assemble
libs = "".join("\t\t" + lib_symbol(l)[0].replace("\n\t", "\n\t\t") + "\n" for l in used_libs)
out = (f'(kicad_sch\n\t(version 20260306)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n\t(uuid "{SHEET_UUID}")\n'
       f'\t(paper "A4")\n\t(title_block\n\t\t(title "Antenna Board V2d: USB charger and SWD pass-through")\n\t\t(date "2026-11-09")\n'
       f'\t\t(rev "V2d")\n\t\t(company "PROVES Kit / Open Source Space Foundation")\n\t)\n'
       f'\t(lib_symbols\n{libs}\t)\n' + "".join(items) + '\t(embedded_fonts no)\n)\n')
open(OUT, "w").write(out)
print("wrote", OUT, len(items), "items")
