# Antenna Board V2d: decision log

V2d is V2c plus two features: USB charging of the 2S pack from the J12 "FC USB" port, and an SWD pass-through so the FC's SWD port is reachable on an assembled cube. Everything else is V2c unchanged (netlist diff below).

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
| 2 | **At risk.** Charge input is J12 "FC USB" VBUS (unused through V2c), not a new third USB-C port. | No structure drawing was available to place another edge connector. One cable now gives FC data and charging. | V2c netlist: J12 VBUS unconnected |
| 3 | **At risk.** Float voltage 8.2 V (R203 = 0 Ohm on VSET). DNP R203 for 8.4 V. | 4.1 V/cell leaves margin because no cell balancing was found in the pack path. Never fit 39k or 75k (8.8 V / 8.7 V). The debug board's 150k sat on the 8.4/8.7 V decode boundary. | DS pin table, VSET |
| 4 | ICHG = 3.9k / 3810 = 1.02 A; IINDPM = 1110 / 820 = 1.35 A. | 1.35 A stays inside a Type-C 1.5 A source with the ILIM tolerance. With 1.35 A at 5 V the boost delivers about 0.75 A at 7.4 V, so the input limit sets the real charge rate. Debug board had ILIM 383k (about 3 mA, below the 500 mA minimum). | DS §7.5 KILIM, KICHGSET |
| 5 | D+ tied to D- at the charger only. | BC1.2 then sees a DCP and ILIM sets the limit. The FC's USB data lines on J12 never reach the charger, so RP2350 enumeration is unaffected. | DS Table 3 |
| 6 | OTG and /CE hard tied to GND. | OTG high boosts the battery back out of VBUS. The debug board left OTG floating. | DS pin table |
| 7 | **At risk.** TS is a fixed 10k/12k divider (54.5 % of REGN, inside the 10 to 45 C window). | No cell thermistor reaches the antenna board. IC thermal shutdown and the 12 h safety timer still apply. Same exposure as today's bench-supply method. | DS JEITA thresholds |
| 8 | **At risk.** F201 2 A fast fuse (0466002.NRHF, 63 V, 50 A interrupt) and J203 "CHG LINK" 2-pin header between the charger and Dir_Chrg_In. | Dir_Chrg_In is the raw pack + upstream of every positive inhibit. The fuse clears a shorted charger or cap. With J203 removed no charger part hangs on the pack in flight (14 uA drain otherwise). | FC V5e netlist: J14, R109, J7/J10 |
| 9 | Green LED = USB 5 V present (VBUS through 2.2k). Red LED = STAT (REGN pull-up). PG pin left open. | Moving the green LED off PG freed a routing lane next to the QFN. Both LEDs on the outer face. | |
| 10 | SWD: J201 (inner face) wired 1:1 to J202 (outer face), JST-SH BM03B-SRSS-TB, pinout 1 SWCLK, 2 GND, 3 SWDIO, same as FC J22 and the Raspberry Pi Debug Probe. Needs a 1:1 (pin 1 to pin 1) 3-pin JST-SH jumper from FC J22 to J201. | J1 DEBUG has no spare pins (all 12 used). | FC V5e J22 netlist |
| 11 | **At risk (house rule).** Two 0.3 mm GND vias inside the U201 thermal pad. | TI requires thermal vias under the pad. House default is no via in pad. Without them the EP reaches GND only through pin stubs. | DS §11.1 item 6; proves-pcb-design "Via-in-pad: none" |
| 12 | Charger sits on the inner face at x 151 to 168, y 79 to 93, clear of the B.Cu USB pair and the outer-face art. A few REGN hops use short In2.Cu (+3V3 plane) tracks. | Vias are kept off the mask openings of the "Pleiades Five" box art. | |
| 13 | R201 to R205 are 0402 (two extended parts: C51721 3.9k, C25135 820). | 0603 does not fit the 0.5 mm-pitch QFN fan-out. | |
| 14 | Only one PMID cap (C202, 22 uF). | VBUS + PMID minimum is 10 uF after derating; 22 uF X5R at 5 V gives about 13 uF. TI's "optimal" 44 uF did not fit. | DS pin table, PMID |
| 15 | The bee_movie_script.txt silk moved up 0.3 mm. | Clears J203. Not removed. | |

## Gates (2026-11-09)

- ERC: 23 violations, same as V2c (0 new). 3 errors, all V2c heritage.
- DRC with schematic parity: 4 errors, all V2c heritage (In1 zone overlap, three U4 pad clearances). V2c had 8; the 4 that went away were J12 VBUS pads now on a real net. 0 unconnected. Parity: 19 warnings, all the V2c "exclude from BOM" mismatches.
- `sch_lint.py --strict` on charger_swd.kicad_sch: 0 errors, 0 warnings.
- Netlist diff V2c to V2d: 23 parts added, 18 nets added, 0 removed; only Dir_Chrg_In (+J203.2) and GND (+20 pins) changed.

## Before you order

- Check U201 (QFN, +270 assumed) and J201/J202 (+180, from FC J22) in the JLC placement preview. Also check the bottom-side LEDs' polarity marks.
- Confirm the inner-face height above J201 for a JST-SH plug plus cable bend, and that J202 (4.25 mm tall) on the outer face is inside the +Z envelope.
- Buy or make a 1:1 3-pin JST-SH cable (FC J22 to J201).
- J203 is hand-fitted (excluded from BOM/CPL like J2/J3/J4/J10). Add a 2.54 mm shunt to the kit.

## ATP lines

- J203 out: Dir_Chrg_In to GND leakage with USB unplugged < 1 uA.
- J203 in, USB 5 V in, 7.4 V electronic load on Dir_Chrg_In: green on, red on, charge current 0.9 to 1.05 A or the input-limited value, input current <= 1.45 A.
- Float: with the load removed, Dir_Chrg_In settles to 8.16 to 8.24 V (R203 fitted).
- OTG check: battery on Dir_Chrg_In, USB unplugged: J12 VBUS < 0.1 V.
- SWD: Pi Debug Probe on J202 reaches the FC through J201 (`openocd ... -c "init; targets"`).
