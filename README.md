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
- BQ25886 2S boost charger on the J12 "FC USB" port, 5 V only (no PD negotiation), about 1 A into the pack, 8.2 V float.
- 2 A fuse plus a removable "CHG LINK" jumper (J203) between the charger and the battery. Remove J203 for flight.
- Green LED: USB 5 V present. Red LED: charging (blinks on a fault).
- J201 (inner face) to J202 (outer face) JST-SH SWD pass-through, same pinout as the FC's J22.
