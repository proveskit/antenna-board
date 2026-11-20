# antenna-board

This repo contains the KiCAD files for the PROVES Kit Antenna Board. This board currently goes on the +Z endcap of the satellite and hosts the antennas, interfacing ports, and some other support circuitry!

## antenna_top_cap_board_v1a
This antenna board is a reformat of the V1 Antenna Board that consolidates a bunch of the 2pos Picolock and STEMMA connectors into a single connector that runs back to the V3b EPS Board. We are probably going to leapfrog this version to land on V2 which fundementally changes things about the antenna feed path. 

## antenna_top_cap_v2
This version of the antenna top cap featuers major changes to the antenna feed path and debug passthroughs. Notable features are as follows: 
- Updated Balun Part Number (no longer sucks! still sucks to solder though)
- Addition of 12-pos and 5-pos Battery Board and Flight Controller Board debug connectors.


## antenna_top_cap_v2d
V2c plus USB charging and an SWD pass-through. See `antenna_top_cap_v2d/DECISIONS.md` for the design calls and ATP lines.
- BQ25886 2S boost charger on a new charge-only USB-C (J204), 5 V only (no PD negotiation), up to 1 A into the pack, 8.2 V float. J12 "FC USB" stays data-only.
- 1.5 A fuse plus a 0 Ohm "CHG LINK" (R210, outer face) between the charger and the battery. Hot-air R210 off before flight.
- Green LED: USB 5 V present. Red LED: charging (blinks on a fault).
- J201 (inner face) to J202 (outer face) JST-SH SWD pass-through, same pinout as the FC's J22.

## antenna_top_cap_v3
V2d with the dipole replaced by the circularly polarized canted turnstile (OreSat0 heritage, from `proves_canted_turnstile` on `Turnstile-Test-Board`). Harness, jumpers, holes, sensors, charger and SWD are V2d's, so it drops into the same structure with the same firmware. See `antenna_top_cap_v3/DECISIONS.md`.
- Four tape elements fed 0/90/180/270 deg by three Mini-Circuits QBA-07+ hybrids and a quarter-wave delay line.
- One MMCX (RF1), moved next to the feed network.
- `tools/check_rf.py` proves the RF copper matches the turnstile; `tools/check_interface.py` proves the interface parts match V2d.
