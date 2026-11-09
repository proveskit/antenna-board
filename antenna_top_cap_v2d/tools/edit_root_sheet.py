#!/usr/bin/env python3
"""Apply the V2d root-sheet edits to antenna_top_cap_v2d.kicad_sch (run once on the V2c copy).

- J12 VBUS: drop the no-connect flag, wire it to local label FC_USB_VBUS.
- Add the "Charger & SWD" hierarchical sheet with pins FC_USB_VBUS and Dir_Chrg_In.
- Fill the title block.
"""
import re
import sys
import uuid

SCH, SHEET_UUID = sys.argv[1:3]
NS = uuid.UUID(SHEET_UUID)
uid = lambda *p: str(uuid.uuid5(NS, "root/" + "/".join(map(str, p))))
t = open(SCH).read()
assert "charger_swd.kicad_sch" not in t, "already applied"

nc = re.search(r'\t\(no_connect\n\t\t\(at 49\.53 73\.66\)\n\t\t\(uuid "[^"]+"\)\n\t\)\n', t)
assert nc, "J12 VBUS no_connect not found"
t = t[:nc.start()] + t[nc.end():]

root_uuid = re.search(r'\(generator_version "10.0"\)\n\t\(uuid "([^"]+)"\)', t).group(1)


def wire(a, b):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n'
            f'\t\t)\n\t\t(uuid "{uid("w", a, b)}")\n\t)\n')


def label(name, at, rot, just):
    return (f'\t(label "{name}"\n\t\t(at {at[0]} {at[1]} {rot})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{uid("l", name, at)}")\n\t)\n')


def glabel(name, at, shape):
    return (f'\t(global_label "{name}"\n\t\t(shape {shape})\n\t\t(at {at[0]} {at[1]} 0)\n\t\t(fields_autoplaced yes)\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left)\n\t\t)\n\t\t(uuid "{uid("g", name, at)}")\n'
            f'\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"\n\t\t\t(at {at[0]} {at[1]} 0)\n\t\t\t(hide yes)\n'
            f'\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n\t)\n')


def text(s, x, y):
    s = s.replace("\n", "\\n")
    return (f'\t(text "{s}"\n\t\t(exclude_from_sim no)\n\t\t(at {x} {y} 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t)\n\t\t\t(justify left top)\n\t\t)\n\t\t(uuid "{uid("t", x, y)}")\n\t)\n')


add = ""
# J12 VBUS pin end (49.53, 73.66): wire up clear of R26's value text, then the label.
add += wire((49.53, 73.66), (49.53, 63.5))
add += label("FC_USB_VBUS", (49.53, 63.5), 0, "left bottom")
add += text("V2d: VBUS now feeds the USB charger\n(Charger & SWD sheet). 5 V only.", 52.07, 64.77)

# Sheet symbol in the empty lower-middle area.
sx, sy, sw, sh = 85.09, 160.02, 33.02, 12.7
py = 165.1
add += (f'\t(sheet\n\t\t(at {sx} {sy})\n\t\t(size {sw} {sh})\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n'
        f'\t\t(fields_autoplaced yes)\n\t\t(stroke\n\t\t\t(width 0.1524)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill\n\t\t\t(color 0 0 0 0)\n\t\t)\n'
        f'\t\t(uuid "{SHEET_UUID}")\n'
        f'\t\t(property "Sheetname" "Charger & SWD"\n\t\t\t(at {sx} {round(sy - 0.7116, 4)} 0)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
        f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left bottom)\n\t\t\t)\n\t\t)\n'
        f'\t\t(property "Sheetfile" "charger_swd.kicad_sch"\n\t\t\t(at {sx} {round(sy + sh + 0.5846, 4)} 0)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
        f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left top)\n\t\t\t)\n\t\t)\n'
        f'\t\t(pin "FC_USB_VBUS" input\n\t\t\t(at {sx} {py} 180)\n\t\t\t(uuid "{uid("pin", "vbus")}")\n'
        f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n'
        f'\t\t(pin "Dir_Chrg_In" passive\n\t\t\t(at {round(sx + sw, 4)} {py} 0)\n\t\t\t(uuid "{uid("pin", "bat")}")\n'
        f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify right)\n\t\t\t)\n\t\t)\n'
        f'\t\t(instances\n\t\t\t(project "antenna_top_cap_v2d"\n\t\t\t\t(path "/{root_uuid}"\n\t\t\t\t\t(page "2")\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
add += wire((sx, py), (round(sx - 7.62, 4), py))
add += label("FC_USB_VBUS", (round(sx - 7.62, 4), py), 0, "left bottom")
ex = round(sx + sw + 5.08, 4)
add += wire((round(sx + sw, 4), py), (ex, py))
add += glabel("Dir_Chrg_In", (ex, py), "bidirectional")

anchor = "\t(sheet_instances"
assert anchor in t
t = t.replace(anchor, add + anchor, 1)

tb = ('\t(title_block\n\t\t(title "PROVES Antenna Board V2d")\n\t\t(date "2026-11-09")\n\t\t(rev "V2d")\n'
      '\t\t(company "PROVES Kit / Open Source Space Foundation")\n\t\t(comment 1 "Harness: J1 DEBUG to FC V5e J16; SWD J201 to FC J22")\n\t)\n')
assert "(title_block" not in t
t = t.replace('\t(paper "A4")\n', '\t(paper "A4")\n' + tb, 1)
open(SCH, "w").write(t)
print("root edited, root uuid", root_uuid)
