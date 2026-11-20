#!/usr/bin/env python3
"""Generate rf_turnstile.kicad_sch (V3 circularly polarized turnstile feed).

Rerun to regenerate the sheet; UUIDs are derived from names so output is stable.
Usage: gen_rf_sheet.py <kicad stock symbols dir> <out .kicad_sch> <root uuid> <sheet uuid> <project>
Project symbols (lib "turnstile_rf") are read from ./symbols.
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
    path = "symbols/turnstile_rf.kicad_sym" if lib == "turnstile_rf" else f"{LIBDIR}/{lib}.kicad_sym"
    text = open(path).read()
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
                 in_bom=True, ref_at=None, val_at=None, hide_value=False, power=False, fjust="left"):
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
        s += prop("Reference", ref, rx, ry, hide=power, justify=None if power else fjust, angle=ang)
        s += prop("Value", value, vx, vy, hide=hide_value, justify=None if power else fjust, angle=ang)
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
    Sym("power:GND", f"#PWR0{300 + _pwr[0]}", "GND", pt[0], pt[1], power=True, hide_value=hide,
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


R_FP = "Resistor_SMD:R_2512_6332Metric"
HYB_FP = "Antenna_board:MHC0410L03"
TAPE_FP = "Antenna_board:Turnstile_Tape_Element"
HYB_DS = "https://datasheet.lcsc.com/datasheet/pdf/46836830f8b0c6affe7c26a253a585e6.pdf"


def hybrid(ref, x, y, nets):
    """nets: pin number -> net. Any port can be the input; the port beside it on the same long side is isolated,
    the port straight across is coupled (0 deg) and the diagonal port is direct (-90 deg)."""
    u = Sym("turnstile_rf:MHC0410L03", ref, "MHC0410L03", x, y, fp=HYB_FP, mpn="MHC0410L03", lcsc="C52139893", ds=HYB_DS,
            desc="MEGSINE 3 dB 90 degree hybrid, 400-1000 MHz, 14.22 x 8.89 mm", ref_at=(x - 10.16, y - 8.89))
    for num, name in nets.items():
        left = num in ("1", "2")
        if name == "UHF":
            hlabel("UHF", u.p(num), "input", rot=180)
        else:
            label(name, u.p(num), 180 if left else 0)
    gnd(u.p("5"), hide=True)
    return u


def load(ref, x, y, term):
    r = Sym("Device:R", ref, "49.9", x, y, fp=R_FP, lcsc="C723714", mpn="RC2512FK-7W49R9L",
            desc="Hybrid isolated-port load, 49.9 Ohm 1 %, 2512, 2 W (stowed 1 W TX puts about 0.5 W in R302 and R303)",
            ref_at=(x + 2.54, y - 1.27), val_at=(x + 2.54, y + 1.27))
    label(term, r.p("1"), 90)
    gnd(r.p("2"))


def element(ref, x, y, netname, phase):
    a = Sym("Device:Antenna", ref, f"Tape {phase}", x, y, fp=TAPE_FP,
            desc=f"Spring-steel tape element, {phase} feed phase", ref_at=(x + 2.54, y - 6.35), val_at=(x + 2.54, y - 3.81))
    label(netname, a.p("1"))


hybrid("U301", 76.2, 101.6, {"2": "UHF", "1": "TERM1", "3": "UHF_B", "4": "UHF_A"})
load("R301", 76.2, 132.08, "TERM1")
hybrid("U302", 147.32, 63.5, {"2": "UHF_A", "1": "TERM2", "3": "UHF_0", "4": "UHF_90"})
load("R302", 147.32, 93.98, "TERM2")
hybrid("U303", 147.32, 139.7, {"2": "UHF_B", "1": "TERM3", "3": "UHF_180", "4": "UHF_270"})
load("R303", 147.32, 170.18, "TERM3")
element("AE2", 220.98, 50.8, "UHF_0", "north, 0 deg")
element("AE1", 220.98, 76.2, "UHF_90", "east, 90 deg")
element("AE4", 220.98, 127.0, "UHF_180", "south, 180 deg")
element("AE3", 220.98, 152.4, "UHF_270", "west, 270 deg")

text("Circularly polarized turnstile feed", 25.4, 25.4, size=2.0, bold=True)
text("Right-hand circular out of the outer face (B.Cu, the side with the USB ports).\n"
     "Three MEGSINE MHC0410L03 hybrids (JLC C52139893). The port straight across from the input is coupled (0 deg),\n"
     "the diagonal port is direct (-90 deg), the port beside the input is isolated and takes the 49.9 Ohm load.\n"
     "- All three are fed on pin 2: pin 3 is the 0 deg output and pin 4 the -90 deg output.\n"
     "- UHF_A is lambda_g/4 longer than UHF_B (94.1 mm at 437 MHz, e_eff 3.32): UHF_A arrives 180 deg behind UHF_B.\n"
     "- The feed phase lags north (AE2), east (AE1), south (AE4), west (AE3) in 90 deg steps. That is clockwise\n"
     "  seen from the inner face and counter-clockwise seen from the outer face.\n"
     "- UHF_0/90/180/270 are length-matched. RF netclass: 0.3424 mm CPWG, 0.4 mm gap to the GND pour.\n"
     "- All RF corners are 45 deg. tools/check_rf.py checks the lengths, the pins, the corners and the sense.", 25.4, 30.48)
# ---------------------------------------------------------------- assemble
libs = "".join("\t\t" + lib_symbol(l)[0].replace("\n\t", "\n\t\t") + "\n" for l in used_libs)
out = (f'(kicad_sch\n\t(version 20260306)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n\t(uuid "{SHEET_UUID}")\n'
       f'\t(paper "A4")\n\t(title_block\n\t\t(title "Antenna Board V3: turnstile CP feed")\n\t\t(date "2026-11-19")\n'
       f'\t\t(rev "V3")\n\t\t(company "PROVES Kit / Open Source Space Foundation")\n\t)\n'
       f'\t(lib_symbols\n{libs}\t)\n' + "".join(items) + '\t(embedded_fonts no)\n)\n')
open(OUT, "w").write(out)
print("wrote", OUT, len(items), "items")
