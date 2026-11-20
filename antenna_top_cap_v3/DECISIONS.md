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
| 2a | Port use follows datasheet table 2: the port straight across from the input is coupled (0 deg), the diagonal port is direct (-90 deg), and the port beside the input is isolated. All three hybrids are fed on pin 2, so pin 3 is the 0 deg output, pin 4 the -90 deg output and pin 1 takes the load. | With pin 2 as the input the phase lags clockwise seen from the inner face (decision 2f), every output leaves from the outside corner nearest its element, and the inter-hybrid lines reach the inside corners without running along a hybrid. | `check_rf.py` walks the netlist with this table |
| 2b | UHF_A (U301 to U302) carries the quarter-wave delay as a 7-run serpentine east of centre, 2.0 mm between runs with GND pour and vias between them. It leaves the serpentine at its west end and runs north to U302. UHF_A is 94.126 mm longer than UHF_B. | UHF_A leaves U301 at -90 deg and the delay adds 90 deg, so U302 is fed 180 deg behind U303. The east side is the only free area that large. | `check_rf.py`: 90.00 deg at 437 MHz (e_eff 3.32), element steps 90.0, 90.0, 90.0, 90.0 |
| 2c | The four element feeds are 16.428 mm each, from the hybrid land to the tape pad centre. The hybrid centres are offset by up to 0.29 mm from the diagonals to make them equal, because AE2's pad centre is 0.455 mm off the others. | Equal feeds keep the hybrid's phase and amplitude balance at the elements. | `check_rf.py`: spread 0.001 mm |
| 2d | Every RF corner is 45 degrees. No arcs. | House routing style (Michael). | `check_rf.py` fails on any corner over 45 degrees or any segment off the 45 degree grid |
| 2e | The hybrid footprint is generated from the datasheet outline drawing (rev 2): four L-shaped corner lands, one solid-connected ground land with twelve 0.3 mm ground holes in it, paste in four windows. | The datasheet gives a board layout picture but no land table. Ground holes under the part follow that picture. | `tools/gen_mhc.py`. **Check the first board's solder joints**; the holes are not plugged |
| 2f | Sense of rotation: **right-hand circular out of the outer face** (B.Cu, the side with the USB ports). The feed phase lags north (AE2), east (AE1), south (AE4), west (AE3). That is clockwise seen from the inner face (F.Cu) and counter-clockwise seen from the outer face. Nets are named by that lag: UHF_0 north, UHF_90 east, UHF_180 south, UHF_270 west. | Michael, 2026-11-19: right-hand circular, and the outer face is the one with the USB ports. A wave leaving a face is right-hand when its field turns counter-clockwise as seen looking back at that face. | `check_rf.py` takes north, east, south, west from the pad positions and fails unless each lags the one before by 90 deg |
| 3 | The turnstile's RF switch path is dropped: PE4259 U4, Si7454DP Q1, the SatNOGS MMCX J2 and the RF_PORT_CTRL header. There is one MMCX, RF1, feeding U301 pin 2. | Q1 cannot drive the switch above 1.3 V (VIH 2.31 V), the control line floats, and the harness has no control signal (RF review 2026-11-14). | `/UHF` = RF1.5 to U301.2 |
| 4 | **At risk.** RF1 moves to (21.77, 28.99) from centre, rotated 45 deg, on the diagonal out of U301 pin 2. That is 27 mm from its V2d spot. A 4.4 mm feed connects it. | V2d's MMCX spot is now between the hybrids. Check the FC-to-cap coax length. | |
| 5 | The hybrid loads R301 to R303 are 49.9 Ohm 2512, 2 W: YAGEO RC2512FK-7W49R9L (JLC C723714, 4,948 in stock on 2026-11-19). Each sits on a 2.0 mm stub from its isolated port, with its ground pad tied solid to the pour and three GND vias 1.3 mm past it. | With all four tapes stowed and 1 W TX, each outer hybrid gets about 0.5 W back and puts it in its load (R302, R303). A standard 1206 is 0.25 W, and parts run hotter in vacuum. | RF reviews 2026-11-19 |
| 6 | The charger block (U201 and its 20 passives, LEDs and R210) moves rigidly by (-11, -2) mm with its own copper. The VBUS trunk from J204 now runs on B.Cu at y = -35.2 mm. The "REMOVE FOR FLIGHT" label moves with R210. | The north element (AE2) and its slot sat on the charger. The old trunk at y = -32.7 mm crossed the slot. | A placement search over the board (0.5 mm grid, F and B copper) found this as the nearest free spot |
| 7 | The J7 burn wire stays exactly where V2d has it. | The new feed leaves that area free. UHF_B passes 0.85 mm south of J7's ground pads. | J7 at (-7.76, -6.91), as V2d |
| 7a | **At risk.** Two FireLine lines, each all the way around (Michael 2026-11-14), are assumed to both loop over the one J7 burn resistor. Same BURN line and current. A second resistor in parallel would double the burn current. | | Michael to confirm |
| 8 | SCL1/SDA1 to the VEML6031 drop to B.Cu at the pull-ups. | On F.Cu they crossed the west element feed (AE3). | |
| 8a | SWD from J202 to J201 is re-routed: on F.Cu down the west side of the TP6 keepout, on B.Cu under the strip between AE2's pad and its slot (0.4 mm clear of the cleared box), then on F.Cu around the outside of U302 and into J201 from the south. | V2d's route ran through what is now the charger, U302, UHF_A and the AE1 feed. The north tape lies on that strip of F.Cu on its way to the slot, so nothing else runs there. | DRC: no new errors |
| 8b | Under each tape pad, In1, In2 and B.Cu are cleared 0.3 mm past the pad edge, the same for all four. On F.Cu the pour and stitching vias are kept off the pad, the slot and the strip between them, where the tape lies. The payload USB pair on B.Cu, which ran under AE2's pad, now turns south 5.3 mm east of the pad; its 2.96 mm skew is V2d's own. | Over In1 at 0.21 mm each 4.0 x 11.3 mm pad was about 8.6 pF across its feed, about -j42 Ohm at 437 MHz, and the tape over the F.Cu pour added more. There are still no matching parts on the feeds. | RF reviews 2026-11-19. `check_rf.py` fails if any of this copper comes back. VNA each element on the first board |
| 9 | GND stitching: vias every 2.5 mm, 1.05 mm either side of every RF line, dropped where they would land on other copper, holes, slots or keepouts. The dipole-window keepouts, the balun ground island and the floating B1 GND ties are removed. In1 is solid GND under the RF lines and hybrids. | | `check_rf.py`: 110 GND vias within 1.6 mm of RF copper, no RF point more than 3.44 mm from one, no bare In1 under RF copper |
| 10 | RF netclass: 0.3424 mm track, 0.4 mm gap, for `/RF/*` (the lines and the load stubs) and `/UHF`. A custom rule in `antenna_top_cap_v3.kicad_dru` lets `/UHF` pass 0.23 mm from the MMCX's own ground pins. The stackup stays V2d's JLC04161H-7628. | 50 Ohm CPWG on this stackup. | RF review 2026-11-14, finding 5 |
| 11 | Inner-face mask art over the RF block is removed: two shield logos, "NOT TODAY PROTON" and "In another life". The inner-face PDF logo moves to the free south-west corner. "This is where the magic happens" moves 3.6 mm north, off U301. | That art opened the mask over the RF parts and lines. The inner face is not visible on an assembled cube. | |
| 12 | The outer-face "Pleiades Five" art is trimmed where the moved charger sits under it: polygons, lettering and frame lines are cut back 0.3 mm around every B.Cu land and via there and 0.2 mm around every B.Cu track, and "THE PLEIADES FIVE" slides 8.5 mm along its band to the part the charger does not reach. Elsewhere 15 GND stitching vias and U302's ground holes show inside art openings; that is cosmetic. | The openings bridged BTST, REGN, CHG_BAT, Dir_Chrg_In and GND copper. | DRC: the 17 art mask bridges are gone |
| 13 | Firmware: no change. BURN is on J1 pin 4, and the TMP112 (0x48) and VEML6031 (0x29) are on FC mux channel 7, as on V2d. | | |

## Before ordering

- VNA one MHC0410L03 on the first board: phase and amplitude balance at 437 MHz, and confirm that fed on pin 2, pin 3 leads pin 4 by 90 deg. The datasheet limits are band-wide, 400 to 1000 MHz.
- Measure UHF_A against UHF_B on the first board. By length the delay is 90.00 deg; the reviewer's e_eff range (3.15 to 3.45) puts it between 88 and 92 deg.
- VNA each element with its tape on. The pads now have no plane under them and no matching parts.
- Rule on the FireLine routing (decision 7a) and confirm the coax length to the new RF1 spot.
- Check the hybrid solder joints on the first article (unplugged ground holes in the land, decision 2e).
- Set an operational rule: no 1 W TX until deployment is confirmed. This protects the loads and the PA.

## Gates (2026-11-19)

- ERC: 3 errors, the same 3 as V2d (U3 INT pin, two power flags).
- DRC with schematic parity: 0 unconnected. 7 errors, all V2d's own: 2 J12 VBUS pad pairs counted as shorts and as mask bridges, and 3 U4 pad gaps. Parity: 18 warnings, all the V2c-heritage "exclude from BOM" flags.
- `check_rf.py` PASS: every RF net is one unbranched F.Cu path between the pads the schematic gives it, all corners 45 degrees, delay 90.00 deg, feed spread 0.001 mm, right-hand sense out of the outer face, hybrids unflipped, loads 49.9 Ohm 2512 to GND, In1 solid within 0.9 mm of RF copper and under the hybrid bodies, tape pads and strips cleared, no other net within 1.0 mm (closest 2.13 mm), stitching present.
- `check_interface.py` PASS: 21 locked parts match in position, rotation, side and every pad's net and position, and the Edge.Cuts outline is identical.
- Independent RF review 2026-11-19 on the first MEGSINE layout (9cd1d37): pass for review, five items to fix before ordering. All five are fixed in 615f8b7.
- Second independent RF review 2026-11-19 on 615f8b7: pass, right-hand sense out of B.Cu confirmed, six more items. All six are addressed in this revision (the USB skew is V2d's and is left alone).
