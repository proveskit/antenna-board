#!/usr/bin/env python3
"""Turn the V2d root sheet into V3 (run once on the V2d copy).

- Remove the dipole: B1 (balun) and J6 (tape pads) and the wires that only served them.
- Label the MMCX centre pin UHF and add the "RF" hierarchical sheet (rf_turnstile.kicad_sch) on it.
- Retitle the sheet.
"""
import re
import sys
import uuid

SCH, SHEET_UUID = sys.argv[1:3]
NS = uuid.UUID(SHEET_UUID)
uid = lambda *p: str(uuid.uuid5(NS, "root/" + "/".join(map(str, p))))
t = open(SCH).read()
assert "rf_turnstile.kicad_sch" not in t, "already applied"
root_uuid = re.search(r'\(generator_version "10.0"\)\n\t\(uuid "([^"]+)"\)', t).group(1)


def find_block(text, start):
    depth, i = 0, start
    while True:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1


def drop_symbol(ref):
    global t
    for m in re.finditer(r"\n\t\(symbol\n", t):
        blk = find_block(t, m.start() + 2)
        if f'(property "Reference" "{ref}"' in blk:
            t = t.replace("\t" + blk + "\n", "", 1)
            return
    raise KeyError(ref)


def drop_by_uuid(u):
    global t
    i = t.index(f'(uuid "{u}")')
    s = t.rfind("\n\t(", 0, i) + 1
    blk = find_block(t, s + 1)
    t = t.replace("\t" + blk + "\n", "", 1)


for ref in ("B1", "J6"):
    drop_symbol(ref)
DIPOLE_WIRES = [
    "659fec62-722e-4667-bd13-0a98f43c64c7", "bff9890b-46d8-4274-a151-877f0177cd85", "64cc5d14-ad7b-4bbb-84df-96bf2da78ead",
    "4b0f8203-2359-44c1-87f8-8fc547e26ee6", "4dc63f77-ee87-4030-be26-b07e1b70fe42", "4deb0750-ee57-4ac0-bbab-5a4663c083a2",
    "6e9b16fa-66e1-4f00-933c-a8fa7a97c7e4", "82ce81a8-d831-49e8-966f-49dc1ebda54d", "ae8ec62b-9e77-479d-8d82-33d791eef92a",
    "b58d25e6-7b62-411a-af2b-e16aa33c1b40", "caa2aacb-ace5-4183-b8b7-197c47d3996d",
]
for u in DIPOLE_WIRES:
    drop_by_uuid(u)


def wire(a, b):
    return (f'\t(wire\n\t\t(pts\n\t\t\t(xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n'
            f'\t\t)\n\t\t(uuid "{uid("w", a, b)}")\n\t)\n')


def label(name, at, rot, just):
    return (f'\t(label "{name}"\n\t\t(at {at[0]} {at[1]} {rot})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            f'\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{uid("l", name, at)}")\n\t)\n')


add = label("UHF", (184.15, 105.41), 0, "left bottom")
sx, sy, sw, sh = 190.5, 99.06, 30.48, 12.7
py = 105.41
add += (f'\t(sheet\n\t\t(at {sx} {sy})\n\t\t(size {sw} {sh})\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n'
        f'\t\t(fields_autoplaced yes)\n\t\t(stroke\n\t\t\t(width 0.1524)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill\n\t\t\t(color 0 0 0 0)\n\t\t)\n'
        f'\t\t(uuid "{SHEET_UUID}")\n'
        f'\t\t(property "Sheetname" "RF"\n\t\t\t(at {sx} {round(sy - 0.7116, 4)} 0)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
        f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left bottom)\n\t\t\t)\n\t\t)\n'
        f'\t\t(property "Sheetfile" "rf_turnstile.kicad_sch"\n\t\t\t(at {sx} {round(sy + sh + 0.5846, 4)} 0)\n\t\t\t(show_name no)\n\t\t\t(do_not_autoplace no)\n'
        f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left top)\n\t\t\t)\n\t\t)\n'
        f'\t\t(pin "UHF" input\n\t\t\t(at {sx} {py} 180)\n\t\t\t(uuid "{uid("pin", "uhf")}")\n'
        f'\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n'
        f'\t\t(instances\n\t\t\t(project "antenna_top_cap_v3"\n\t\t\t\t(path "/{root_uuid}"\n\t\t\t\t\t(page "3")\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
add += wire((184.15, py), (sx, py))
anchor = "\t(sheet_instances"
t = t.replace(anchor, add + anchor, 1)

t = re.sub(r'\(title "[^"]*"\)', '(title "PROVES Antenna Board V3 (circularly polarized turnstile)")', t, 1)
t = re.sub(r'\(date "[^"]*"\)', '(date "2026-11-14")', t, 1)
t = re.sub(r'\(rev "[^"]*"\)', '(rev "V3")', t, 1)
open(SCH, "w").write(t)
print("root edited, root uuid", root_uuid)
