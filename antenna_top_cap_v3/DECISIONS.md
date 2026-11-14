# Antenna Board V3: decision log

V3 is the V2d top cap with the dipole replaced by the circularly polarized canted turnstile from `proves_canted_turnstile` (branch `Turnstile-Test-Board`, commit 3ed57c5, OreSat0 heritage). Every harness connector, jumper, mounting hole, sensor and the charger and SWD features carry over from V2d, so V3 uses the same structure, harness and flight software. Michael asked on 2026-11-14 for a board that carries only the circular antenna.

Calls marked **at risk** have not been ruled on by the hardware lead.

## Reproduce

All copper edits are scripted. Run these from `antenna_top_cap_v3/` with KiCad 10:

```sh
python3 tools/edit_root_v3.py antenna_top_cap_v3.kicad_sch <rf sheet uuid>       # once, on the V2d copy
python3 tools/gen_rf_sheet.py <kicad symbols dir> rf_turnstile.kicad_sch <root uuid> <rf sheet uuid> antenna_top_cap_v3
tools/build_board.sh                                                                # V2d board + turnstile board -> V3 board
$KPY tools/check_rf.py antenna_top_cap_v3.kicad_pcb <turnstile board>               # RF copper identical to the turnstile
$KPY tools/check_interface.py antenna_top_cap_v3.kicad_pcb ../antenna_top_cap_v2d/antenna_top_cap_v2d.kicad_pcb
```

`$KPY` is KiCad's bundled Python. `build_board.sh` reads the turnstile board straight from git (`git show 3ed57c5:...`).

## Decisions

| # | Decision | Why | Evidence |
|---|---|---|---|
| 1 | The base is the V2d board from PR #14. The outline and 21 interface parts (J1 DEBUG, J2/J3/J4/J10 jumpers, J8/J9/J12 USB, J11/J13 RBF, J201/J202 SWD, J204 charge USB-C, TP1/TP4/TP5/TP6 holes, U3/U4/U6 sensors, Q2 RBF switch) keep V2d's exact position, rotation and side. | Same structure cutouts, harness, shunts and I2C map as V2d. | `check_interface.py`: PASS, 0.000 mm drift on every locked part |
| 2 | The turnstile RF block is copied from the turnstile board at its own coordinates: three QBA-07+ hybrids, four tape pads with slots, the 94.6 mm quarter-wave delay line, length-matched element feeds and the GND stitching. | It is already tuned, and the copy keeps it as tuned. | `check_rf.py`: every RF net's length is within 0.000 mm of the turnstile. Delay line 94.59 mm = 90.4 deg at 437 MHz (e_eff 3.32). Element feeds within 0.007 mm |
| 3 | The turnstile's RF switch path is dropped: PE4259 U4, Si7454DP Q1, the SatNOGS MMCX J2 and the RF_PORT_CTRL header. There is one MMCX, RF1, feeding U301. | Q1 cannot drive the switch above 1.3 V (VIH 2.31 V), the control line floats, and the harness has no control signal (RF review 2026-11-14). | `/UHF` = RF1.5 to U301.1 |
| 4 | **At risk.** RF1 moves 28.4 mm to (24.15, 28.35) from centre, rotated 45 deg, beside U301 where the turnstile's switch sat. A 6.6 mm feed connects it to U301. | V2d's MMCX spot is now under the delay line. Check the FC-to-cap coax length. | |
| 5 | The hybrid loads R301 to R303 are 49.9 Ohm in 1206 (was 0603), rated 0.5 W or more. Each TERM pad stays where the 0603 TERM pad was. **LCSC part not chosen yet.** | With the tapes stowed and 1 W TX, about 0.33 W reaches each isolated port. That is three times an 0603's rating. | RF review finding 3 |
| 6 | The charger block (U201 and its 20 passives, LEDs and R210) moves rigidly by (-11, -2) mm with its own copper. The VBUS trunk from J204 now runs on B.Cu at y = -35.2 mm. The "REMOVE FOR FLIGHT" label moves with R210. | The north element (AE2) and its slot sat on the charger. The old trunk at y = -32.7 mm crossed the slot. | A placement search over the board (0.5 mm grid, F and B copper) found this as the nearest free spot |
| 7 | **At risk.** The J7 burn wire moves 8.5 mm south, and the BURN copper is bridged to it. The burn resistor body now spans the west end of the delay line. | Its pin-2 pads sat on the delay line. How four tapes stow and tie down to one FireLine loop is not settled. | Michael to confirm stow geometry |
| 8 | SCL1/SDA1 to the VEML6031 drop to B.Cu at the pull-ups. | On F.Cu they crossed the west element feed (AE3). | |
| 9 | 44 GND stitching vias are dropped where they landed on other copper, holes, slots or keepouts. The dipole-window keepouts, the balun ground island and the floating J7/B1 GND ties are removed. In1 is solid GND under the RF block. | | DRC: 0 new copper errors |
| 10 | RF netclass: 0.3424 mm track, 0.4 mm gap for `/RF/UHF_*`. `/UHF` stays Default, as on the turnstile. The stackup stays V2d's JLC04161H-7628. | Keeps the 50 Ohm CPWG the turnstile was drawn for. The turnstile's declared 0.1 mm prepreg gave 35 Ohm. | RF review finding 5 |
| 11 | Firmware: no change. BURN is on J1 pin 4, and the TMP112 (0x48) and VEML6031 (0x29) are on FC mux channel 7, as on V2d. | | |

## Before ordering

- Read the QBA-07+ port-10 (90 deg) phase sign from the Mini-Circuits .s3p, or VNA one part. AE1 and AE3 must end up 180 deg apart. The topology is the same as OreSat0's.
- Choose R301 to R303: 49.9 Ohm 1206, 0.5 W or more (anti-surge thick film), on LCSC.
- QBA-07+ is not stocked at LCSC. Consign the parts or hand-place them.
- Confirm the stowed-tape and FireLine geometry (J7 position) and the coax length to the new RF1 spot.
- Set an operational rule: no 1 W TX until deployment is confirmed. This protects the loads and the PA.

## Gates (2026-11-14)

- ERC: 3 errors, the same 3 as V2d (U3 INT pin, two power flags). No new types. 58 items in total vs 66 on V2d.
- DRC with schematic parity: 0 unconnected. The errors are V2d's 2 J12 VBUS pad pairs plus 199 solder-mask bridges. The bridges come from the turnstile's mask-free RF traces (heritage). Parity: 18 warnings, all the V2c-heritage "exclude from BOM" flags.
- `check_rf.py` PASS, `check_interface.py` PASS.
