# Antenna Board V2d: decision log

V2d is V2c plus two features: USB charging of the 2S pack from a new charge-only USB-C port (J204), and an SWD pass-through so the FC's SWD port is reachable on an assembled cube. Everything else is V2c unchanged (netlist diff below). J12 "FC USB" stays data-only, as in V2c.

The layout was done overnight on 2026-11-09 without the hardware lead available. Every call below that he has not ruled on is marked **at risk**.

## Reproduce

All edits are scripted. From `antenna_top_cap_v2d/`:

```sh
python3 tools/edit_root_sheet.py antenna_top_cap_v2d.kicad_sch 7b1e2f0a-5c3d-4e6f-9a8b-2d0c1e3f4a5b   # once, on the V2c copy
python3 tools/gen_charger_sheet.py <kicad symbols dir> charger_swd.kicad_sch e63e39d7-6ac0-4ffd-8aa3-1841a4541b55 7b1e2f0a-5c3d-4e6f-9a8b-2d0c1e3f4a5b antenna_top_cap_v2d
tools/build_board.sh              # V2c board -> place_charger.py -> route_charger.py
tools/jlc_production.py ...       # BOM + CPL, see jlcpcb/production_files
```

## Decisions

| # | Decision | Why | Source |
|---|---|---|---|
| 1 | **At risk.** Charger is the BQ25886 from `debug_board_v1`, used as a 5 V-only USB-C sink (5.1k Rd on CC, no PD controller). | A sink that never negotiates PD only ever gets 5 V, so nothing on the board sees more than 6.2 V in normal use. BQ25886 VBUS is rated 20 V abs max with 6.2 V OVP, so a non-compliant high-voltage source stops the charger instead of damaging it. A PD design (9 V plus a buck charger) charges faster but adds a PD controller and a 9 to 20 V input stage. | BQ25886 DS SLUSD88A §7.1, §7.5 |
| 2 | Charge input is a new charge-only USB-C, J204, on the outer face's top edge (data pins not connected). J12 stays data-only. | Michael 2026-11-09: a third port needs no structure cutout. Sharing J12 would pull up to 1.35 A from a laptop port during FC debug and can trip port current limiters, dropping the FC's USB link. | Michael in thread |
| 3 | **At risk.** Float voltage 8.2 V (R203 = 0 Ohm on VSET). DNP R203 for 8.4 V. | 4.1 V/cell leaves margin because no cell balancing was found in the pack path. Never fit 39k or 75k (8.8 V / 8.7 V). The debug board's 150k sat on the 8.4/8.7 V decode boundary. | DS pin table, VSET |
| 4 | ICHG = 3.9k / 3810 = 1.02 A; IINDPM = 1110 / 820 = 1.35 A. | Dir_Chrg_In reaches the FC on one 24 AWG harness conductor (J1 pin 6), so charge current stays at or under about 1 A (Michael's limit). 1.35 A stays inside a Type-C 1.5 A source with the ILIM tolerance. At 1.35 A in, about 0.75 A reaches the pack, so the input limit sets the real rate. Debug board had ILIM 383k (about 3 mA, below the 500 mA minimum). | DS §7.5 KILIM, KICHGSET |
| 5 | D+ tied to D- at the charger only. | BC1.2 then sees a DCP and ILIM sets the limit. J204's data pins are not connected. | DS Table 3 |
| 6 | OTG and /CE hard tied to GND. | OTG high boosts the battery back out of VBUS. The debug board left OTG floating. | DS pin table |
| 7 | **At risk.** TS is a fixed 10k/12k divider (54.5 % of REGN, inside the 10 to 45 C window). | No cell thermistor reaches the antenna board. IC thermal shutdown and the 12 h safety timer still apply. Same exposure as today's bench-supply method. | DS JEITA thresholds |
| 8 | F201 1.5 A fast fuse (046601.5NRHF, C187598, 63 V, 50 A interrupt) and J203 "CHG LINK" between the charger and Dir_Chrg_In. J203 is a **2.0 mm** pitch header so its shunt cannot be pushed onto J2 (2.54 mm, pack + to GND), which would dead-short the pack. | Dir_Chrg_In is the raw pack + upstream of every positive inhibit. 1.02 A charge is 68 % of the 1.5 A rating (Littelfuse derates to 75 %), and 1.5 A protects one 24 AWG conductor. Estimated fault loop (pack, 150 mm 22 AWG battery harness, DF11 contacts, 150 mm 24 AWG Dir_Chrg_In + 2 GND, ground inhibit, board copper, fuse): about 150 to 250 mOhm, so 34 to 56 A prospective at 8.4 V, at or under the 50 A interrupt rating. Measure on the first assembled cube. | Michael 2026-11-11; proves-wiring-harness FC_Antenna.yml |
| 9 | Green LED = USB 5 V present (VBUS through 4.7k, 85 mW at a 20 V fault). Red LED = STAT (REGN pull-up). PG pin left open. | Moving the green LED off PG freed a routing lane next to the QFN. Both LEDs on the outer face. | review F6 |
| 10 | SWD: J201 (inner face) wired 1:1 to J202 (outer face), JST-SH BM03B-SRSS-TB, pinout 1 SWCLK, 2 GND, 3 SWDIO, same as FC J22 and the Raspberry Pi Debug Probe. Needs a 1:1 (pin 1 to pin 1) 3-pin JST-SH jumper from FC J22 to J201. | J1 DEBUG has no spare pins (all 12 used). | FC V5e J22 netlist |
| 11 | Four 0.3 mm GND vias inside the U201 thermal pad, untented, not plugged. | TI requires thermal vias under the pad. Michael 2026-11-11: vias in a large exposed pad are fine, as on past boards; the no-via-in-pad rule is for small signal pads. | DS §11.1 item 6; Michael in thread |
| 12 | Charger sits on the inner face at x 151 to 168, y 79 to 93, clear of the B.Cu USB pair and the outer-face art. A few REGN hops use short In2.Cu (+3V3 plane) tracks. | Vias are kept off the mask openings of the "Pleiades Five" box art. | |
| 13 | R201 to R205 are 0402 (two extended parts: C51721 3.9k, C25135 820). | 0603 does not fit the 0.5 mm-pitch QFN fan-out. | |
| 14 | Only one PMID cap (C202, 22 uF 0805). | VBUS + PMID minimum is 10 uF after derating; 22 uF X5R at 5 V gives about 13 uF. TI's "optimal" 44 uF did not fit. | DS pin table, PMID |
| 16 | SYS caps C204 to C206 and BAT cap C207 are 22 uF 25 V X5R **1206** (C12891, Basic). C207 sits on the outer face under the BAT via. | 0805 parts derate to about 7 to 8 uF at 8.2 V. 1206 gives about 14 uF each, 42 uF on SYS against TI's 2 x 22 uF after derating, and about 14 uF on BAT. | review F1 |
| 17 | SYS cap GND pads tie together with 0.6 mm copper, each has its own via to In1, and they and the EP use solid (not thermal-spoke) zone connections. | Shortens the boost hot loop. | review F2 |
| 18 | C208 (bootstrap) moved to the outer face directly under the SW and BTST pins: one via each, about 4 mm of loop. | It sat about 10 mm away next to the inductor. | review F3 |
| 19 | No VBUS TVS. | A 5 V TVS would conduct hard on a non-compliant 9 to 20 V source. BQ25886 VBUS is rated to 20 V and its OVP is 6.2 V. | review F6 |
| 15 | The bee_movie_script.txt silk moved up 0.3 mm. | Clears J203. Not removed. | |

## Gates (2026-11-09)

- ERC: 23 violations, same as V2c (0 new). 3 errors, all V2c heritage.
- DRC with schematic parity: 8 errors, exactly the V2c set (In1 zone overlap, three U4 pad clearances, J12 VBUS pad pairs). 0 new violations of any severity from V2d copper or parts. 0 unconnected. Parity: 19 warnings, all the V2c "exclude from BOM" mismatches.
- `sch_lint.py --strict` on charger_swd.kicad_sch: 0 errors, 0 warnings.
- Netlist diff V2c to V2d: 26 parts added, 0 removed; nets only added, except Dir_Chrg_In (+J203.2) and GND (+charger pins). J12 is unchanged.
- Independent review (2026-11-09): 4 major, 2 minor findings fixed (F1 to F4, F6 VBUS LED resistor, F7 more EP vias, F8 VBUS now 1 mm on B.Cu). F5 closed 2026-11-11 by the loop estimate and the 1.5 A fuse.

## Fit check (Onshape Alcyone_Assem, 2026-11-11)

Bounding boxes from the assembly API (Z up; the model carries antenna V2 and FC V5d, same outlines):

| Item | Z range (mm) | Result |
|---|---|---|
| Antenna PCB | -32.0 to -30.5 | inner face = bottom (-32.0) |
| Structure rails (Half U) top | -25.6 | rails stand 4.9 mm above the outer face; J202 (4.25 mm) and J204 (3.3 mm) sit below the rail tops |
| FC V5d PCB | -60.6 to -59.0 | 27 mm free between the antenna inner face and the FC top: room for a JST-SH plug on J201 plus the cable bend |
| Side brackets at TP4/TP5 | -56.1 to -32.0 | J201 courtyard ends 4.9 mm short of the TP4 bracket footprint; route the J201 cable away from it |

## JLC dry run (2026-11-11, not ordered)

- Gerber: 4 layers, 100 x 100 mm. ENIG, 0.2 mm min via, Standard PCBA both sides, 5 boards: **$263.23** before shipping (PCB $88.46, PCBA $174.77).
- BOM is grouped by LCSC number: separate lines that share an LCSC part get unticked by JLC's matcher (J8/J12/J204 and J201/J202 did on the first pass).
- Placement preview checked: J201/J202 +180 correct (pins on pads), J204 matches J8/J12, D201/D202 cathodes correct, L201 and the 1206 caps fine. U201 needed **0**, not +270: +270 put the model's pin-1 dot top-right. Fixed in tools/jlc_corrections.csv and the CPL.
- Shortfalls are V2c parts, not V2d: J9/J11 DF11-4DP (10 short) and U4 TMP112 (5 short). J13 is DNP.

## Before you order

- Rotations verified in the JLC preview (above). Re-check after any CPL regeneration.
- Clearances checked against the Onshape assembly (above).
- Buy or make a 1:1 3-pin JST-SH cable (FC J22 to J201).
- J203 is hand-fitted (excluded from BOM/CPL like J2/J3/J4/J10). Add a **2.0 mm** shunt to the kit.

## ATP lines

- J203 out: Dir_Chrg_In to GND leakage with USB unplugged < 1 uA.
- J203 in, 5 V into J204, 7.4 V electronic load on Dir_Chrg_In: green on, red on, charge current 0.7 to 1.05 A, input current <= 1.45 A.
- Charge only between 10 and 45 C: the fixed TS divider does not stop a cold-cell charge. The FC's LT3652 can charge the same pack at the same time.
- Float: with the load removed, Dir_Chrg_In settles to 8.16 to 8.24 V (R203 fitted).
- OTG check: battery on Dir_Chrg_In, USB unplugged: J204 VBUS < 0.1 V.
- SWD: Pi Debug Probe on J202 reaches the FC through J201 (`openocd ... -c "init; targets"`).
