# Antenna Board V3: decision log

V3 is the V2d top cap with the dipole replaced by a circularly polarized canted turnstile. The four tape pads come from `proves_canted_turnstile` (branch `Turnstile-Test-Board`, commit 3ed57c5, OreSat0 heritage). The feed network was re-laid out on 2026-11-19 around three MEGSINE MHC0410L03 hybrids, because the Mini-Circuits QBA-07+ is not stocked at JLC. Every harness connector, jumper, mounting hole, sensor and the charger and SWD features carry over from V2d, so V3 uses the same structure, harness and flight software. Michael asked on 2026-11-14 for a board that carries only the circular antenna.

Calls marked **at risk** have not been ruled on by the hardware lead.

## Reproduce

All copper edits are scripted. Run these from `antenna_top_cap_v3/` with KiCad 10:

```sh
python3 tools/gen_mhc.py                                                            # MHC0410L03 footprint and symbol
python3 tools/edit_root_v3.py antenna_top_cap_v3.kicad_sch <rf sheet uuid>          # once, on the V2d copy
python3 tools/gen_rf_sheet.py <kicad symbols dir> rf_turnstile.kicad_sch <root uuid> <rf sheet uuid> antenna_top_cap_v3
tools/build_board.sh                                                                # V2d board + tape pads + tools/rf_plan.py -> V3 board
kicad-cli sch export netlist --format kicadxml -o net.xml antenna_top_cap_v3.kicad_sch
$KPY tools/check_rf.py antenna_top_cap_v3.kicad_pcb net.xml                         # lengths, pins, 45 degree corners, element phases
$KPY tools/check_interface.py antenna_top_cap_v3.kicad_pcb ../antenna_top_cap_v2d/antenna_top_cap_v2d.kicad_pcb
```

`$KPY` is KiCad's bundled Python. `build_board.sh` reads the turnstile board straight from git (`git show 3ed57c5:...`). `python3 tools/rf_plan.py` prints the planned lengths without KiCad.

## Decisions

| # | Decision | Why | Evidence |
|---|---|---|---|
| 1 | The base is the V2d board from PR #14 (at d0c2acd, with the right-angle J202 on the top edge). The outline and 21 interface parts (J1 DEBUG, J2/J3/J4/J10 jumpers, J8/J9/J12 USB, J11/J13 RBF, J201/J202 SWD, J204 charge USB-C, TP1/TP4/TP5/TP6 holes, U3/U4/U6 sensors, Q2 RBF switch) keep V2d's exact position, rotation and side. | Same structure cutouts, harness, shunts and I2C map as V2d. | `check_interface.py`: PASS, 0.000 mm drift on every locked part |
| 2 | The hybrids are three MEGSINE MHC0410L03 (JLC C52139893, 14.22 x 8.89 mm). They sit on the board diagonals at 45 degrees with the output side facing out: U301 south-east, U302 north-east, U303 south-west. The four tape pads and slots stay where the turnstile board has them. | QBA-07+ has no JLC stock. The MEGSINE part has lower loss (0.25 dB typical) and is rated +/-7 deg and +/-0.5 dB, which costs under 0.05 dB of polarization loss. A lumped LC hybrid (2x 13 nH C701184, 2x 18 nH C86133, 4x 18 pF C1647 per hybrid) is the fallback if MEGSINE stock runs out. | JLC stock 56 on 2026-11-19. Comparison in the project thread, 2026-11-16 |
| 2a | Port use follows datasheet table 2: the port straight across from the input is coupled (0 deg), the diagonal port is direct (-90 deg), and the port beside the input is isolated. U301 is fed on pin 2, so UHF_A (pin 4) is the -90 deg output. U302 and U303 are fed on pin 1. | With these inputs every output leaves from the outside corner nearest its element, and the two inter-hybrid lines leave from the inside corners. | `check_rf.py` walks the netlist with this table |
| 2b | UHF_A (U301 to U302) carries the quarter-wave delay as a 12-run serpentine east of centre, 2.0 mm between runs with GND pour and vias between them. UHF_A is 94.126 mm longer than UHF_B. | UHF_A leaves U301 at -90 deg and the delay adds 90 deg, so U302 is fed 180 deg behind U303. Each element then lags the one before it by 90 deg in the order AE1, AE2, AE3, AE4. The east side is the only free area that large. | `check_rf.py`: 90.00 deg at 437 MHz (e_eff 3.32), element steps 90.0, 90.0, 90.0, 90.0 |
| 2c | The four element feeds are 16.428 mm each, from the hybrid land to the tape pad centre. The hybrid centres are offset by up to 0.29 mm from the diagonals to make them equal, because AE2's pad centre is 0.455 mm off the others. | Equal feeds keep the hybrid's phase and amplitude balance at the elements. | `check_rf.py`: spread 0.001 mm |
| 2d | Every RF corner is 45 degrees. No arcs. | House routing style (Michael). | `check_rf.py` fails on any corner over 45 degrees or any segment off the 45 degree grid |
| 2e | The hybrid footprint is generated from the datasheet outline drawing (rev 2): four L-shaped corner lands, one solid-connected ground land with twelve 0.3 mm ground holes in it, paste in four windows. | The datasheet gives a board layout picture but no land table. Ground holes under the part follow that picture. | `tools/gen_mhc.py`. **Check the first board's solder joints**; the holes are not plugged |
| 2f | **At risk.** Sense of rotation. Seen from the inner face (F.Cu, the side the tapes solder to), the feed phase lags counter-clockwise: east, north, west, south. That radiates right-hand circular out of the inner face and left-hand circular out of the outer face. | The order of the net names is kept from the turnstile board. The QBA-07+ phase sign on that board was never checked, so its sense was not known either. | Michael to say which sense the ground stations use. Swapping it means mirroring the feed, not a part change |
| 3 | The turnstile's RF switch path is dropped: PE4259 U4, Si7454DP Q1, the SatNOGS MMCX J2 and the RF_PORT_CTRL header. There is one MMCX, RF1, feeding U301 pin 2. | Q1 cannot drive the switch above 1.3 V (VIH 2.31 V), the control line floats, and the harness has no control signal (RF review 2026-11-14). | `/UHF` = RF1.5 to U301.2 |
| 4 | **At risk.** RF1 moves to (21.77, 28.99) from centre, rotated 45 deg, on the diagonal out of U301 pin 2. That is 27 mm from its V2d spot. A 4.4 mm feed connects it. | V2d's MMCX spot is now between the hybrids. Check the FC-to-cap coax length. | |
| 5 | The hybrid loads R301 to R303 are 49.9 Ohm in 1206, rated 0.5 W or more, each 1.7 mm from its isolated port. **LCSC part not chosen yet.** | With the tapes stowed and 1 W TX, about 0.33 W reaches each isolated port. | RF review 2026-11-14, finding 3 |
| 6 | The charger block (U201 and its 20 passives, LEDs and R210) moves rigidly by (-11, -2) mm with its own copper. The VBUS trunk from J204 now runs on B.Cu at y = -35.2 mm. The "REMOVE FOR FLIGHT" label moves with R210. | The north element (AE2) and its slot sat on the charger. The old trunk at y = -32.7 mm crossed the slot. | A placement search over the board (0.5 mm grid, F and B copper) found this as the nearest free spot |
| 7 | The J7 burn wire stays exactly where V2d has it. | The new feed leaves that area free. UHF_B passes 0.85 mm south of J7's ground pads. | J7 at (-7.76, -6.91), as V2d |
| 7a | **At risk.** Two FireLine lines, each all the way around (Michael 2026-11-14), are assumed to both loop over the one J7 burn resistor. Same BURN line and current. A second resistor in parallel would double the burn current. | | Michael to confirm |
| 8 | SCL1/SDA1 to the VEML6031 drop to B.Cu at the pull-ups. | On F.Cu they crossed the west element feed (AE3). | |
| 8a | SWD from J202 to J201 is re-routed on F.Cu: down the west side of the TP6 keepout, east between AE2's pad and its slot (0.75 mm from the pad), around the outside of U302 and up into J201 from the south. | V2d's route ran through what is now the charger, U302, UHF_A and the AE1 feed. The lines are idle in flight. | DRC: no new errors |
| 9 | GND stitching: vias every 2.5 mm, 1.05 mm either side of every RF line, dropped where they would land on other copper, holes, slots or keepouts. The dipole-window keepouts, the balun ground island and the floating B1 GND ties are removed. In1 is solid GND under the RF block. | | 134 GND vias within 1.6 mm of RF copper. DRC: 0 new copper errors |
| 10 | RF netclass: 0.3424 mm track, 0.4 mm gap for `/RF/UHF_*`. `/UHF` and the load stubs use the same width; `/UHF` stays in the Default class because the 0.4 mm gap fails at the MMCX pins. The stackup stays V2d's JLC04161H-7628. | 50 Ohm CPWG on this stackup. | RF review 2026-11-14, finding 5 |
| 11 | Inner-face mask art over the RF block is removed: two shield logos, "NOT TODAY PROTON" and "In another life". The inner-face PDF logo moves to the free south-west corner. "This is where the magic happens" moves 3.6 mm north, off U301. | That art opened the mask over the RF parts and lines. The inner face is not visible on an assembled cube. | |
| 12 | **Open, Michael to choose.** The outer-face "Pleiades Five" panel (the Pegasus logo and the "THE PLEIADES FIVE" band) opens the mask over the moved charger: R210, C207, C208, two REGN vias and a BTST track. That accounts for 17 mask-bridge errors. | A search found no free spot on the board for the panel, and the only clear charger spot is the far south-east, which needs a long VBUS reroute. | Options: trim the art around the charger, or move the charger south-east |
| 13 | Firmware: no change. BURN is on J1 pin 4, and the TMP112 (0x48) and VEML6031 (0x29) are on FC mux channel 7, as on V2d. | | |

## Before ordering

- Rule on the sense of rotation (decision 2f).
- VNA one MHC0410L03 on the first board: phase and amplitude balance at 437 MHz, and confirm pin 4 leads pin 3 by 90 deg when fed on pin 1. The datasheet limits are band-wide, 400 to 1000 MHz.
- Measure UHF_A against UHF_B on the first board. The serpentine's runs couple slightly, so the real delay can differ from the 90.00 deg its length gives.
- Choose R301 to R303: 49.9 Ohm 1206, 0.5 W or more (anti-surge thick film), on LCSC.
- Rule on the outer-face art (decision 12) and the FireLine routing (decision 7a).
- Confirm the coax length to the new RF1 spot.
- Set an operational rule: no 1 W TX until deployment is confirmed. This protects the loads and the PA.

## Gates (2026-11-19)

- ERC: 3 errors, the same 3 as V2d (U3 INT pin, two power flags).
- DRC with schematic parity: 0 unconnected. 24 errors: V2d's own 7 (2 J12 VBUS pad pairs counted as shorts and as mask bridges, 3 U4 pad gaps) plus 17 outer-face art mask bridges (decision 12). Parity: 18 warnings, all the V2c-heritage "exclude from BOM" flags.
- `check_rf.py` PASS: every RF net is one unbranched F.Cu path between the pads the schematic gives it, all corners 45 degrees, delay 90.00 deg, feed spread 0.001 mm, element steps 90 deg.
- `check_interface.py` PASS: 21 locked parts match in position, rotation, side and every pad's net and position, and the Edge.Cuts outline is identical.
