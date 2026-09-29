# The adapter board

A 31 × 32 mm two-layer board that plugs into the socketed D22 site and carries
the substitute: two 74AHCT245 for the sixteen bidirectional lines, one
74AHCT125 for C0–C2 → A0–A2, decoupling, and underneath a field of 42 pins in
the original package's pattern. No glue logic — pin 20 goes straight to the
'245s' DIR (its sense already matches: high = nA drives V/W) and pin 41 to
their /OE. The logic is the one proven equivalent in `sim/`.

![top](img/top.png) ![bottom](img/bottom.png)

`vp1-055-adapter-gerbers.zip` is the fab package (two layers, 0.2 mm tracks,
0.15 mm clearance, 0.7/0.3 mm vias, GND pours — any prototype fab).
`adapter_routed.kicad_pcb` is the routed board: 330 segments, 18 vias, every
connection routed, DRC clean.

## Routing practice

Checked against the usual two-layer rules (JLCPCB's routing best-practice
list, September 2026):

| rule | this board |
|---|---|
| signal width 8–10 mil | 0.2 mm (8 mil) everywhere |
| power wider | VCC/GND at 0.3 mm wherever the neighbours allow (about half their length); the rest 0.2 mm. Three AHCT chips draw a few tens of mA, so 8 mil is electrically fine either way |
| clearance ≥ 4 mil | 0.15 mm (6 mil) minimum, measured |
| 45° bends, no acute angles | 274 bends at 45°, 6 right angles, no acute ones |
| via ring ≥ 0.18–0.25 mm | 0.7 mm pad on a 0.3 mm drill: 0.2 mm ring |
| hole-to-hole ≥ 0.2 mm | 0.53 mm minimum |
| copper-to-edge ≥ 0.2 mm | pours stop 0.5 mm inside the edge, everything else more |
| reference plane / return path | solid GND pour on the bottom (≈600 mm², 60 % of the board) under the top-layer signal runs, a smaller one on top, stitched by the GND pins and vias |
| decoupling next to the VCC pin | each 100 nF within 3.6 mm of its chip's VCC pin; 10 µF bulk at the '125 |
| 3W spacing | not met in the bus bundles (0.35 mm centre-to-centre). Irrelevant at these edge rates and lengths; noted for honesty |
| silk ≥ 1 mm text, clear of pads | 1 mm text, pads knocked out of the silk in the export |
| DRC zero errors | yes, with the design's own rules loaded (see `polish_adapter.py` for why that matters) |

## The site, as measured

The КР1801ВП1 package is through-hole, 42 pins in **four staggered rows**:

| | |
|---|---|
| pitch within a row | 2.5 mm |
| consecutive pin numbers along a side | 1.25 mm (they alternate rows) |
| inner row to outer row, same side | 2.5 mm |
| outer row to outer row | 25.0 mm |
| pins | 0.5 mm square; standard machined receptacles fit |
| numbering | pin 1 at the dimple corner, **inner** row; down the left side, up the right (DIP order) |
| rows | with pin 1 top-left, **10 · 11 · 10 · 11** from left to right. The two sides are *translated* copies, not mirror images: the 11-pin row (the one that reaches the end positions) is the **inner** row on the pin-1 side and the **outer** row on the pin-22 side. Pins 1 and 21 are inboard, pins 22 and 42 outboard. |

**Revision C** is the current board (`REV C` on both silks). Revision A was
fabricated with the two sides mirrored (11 · 10 · 10 · 11): its right side
fits the site, its left side has the two rows swapped. Revision B guessed the
parity the other way round (11 · 10 · 11 · 10) and was never fabricated. Rev A
boards remain usable as the bench carrier in
[TESTING.md](../docs/TESTING.md) if the left-side pins are wired instead of
plugged.

Measured on the MS 0511 board in September 2026. If a different board or
package revision disagrees, the numbers live in one dictionary at the top of
`build_adapter.py`.

## Parts

Also as [`BOM.csv`](BOM.csv), with quantities, DigiKey and Mouser numbers
and the 42 socket receptacles for the machine side.

| ref | part | package |
|---|---|---|
| U1, U2 | 74AHCT245 (SN74AHCT245PWR) | TSSOP-20 |
| U3 | 74AHCT125 (SN74AHCT125PWR) | TSSOP-14 |
| C1–C3 | 100 nF | 0603 |
| C4 | 10 µF | 0805 |
| J1 | 42 PCB pins, Ø0.51 mm with a 1.17 mm flange (Mill-Max 3128-1-00-21-00-00-08-0) | single pins, soldered from the top |
| socket | 42 receptacles for Ø0.46–0.51 mm pins in a 1.0–1.1 mm hole (Harwin H3153-01) | one per hole on the MS 0511 |

The pin and the receptacle are a matched pair: the H3153-01 is specified for
0.46–0.51 mm pins and the 3128 pin is 0.51 mm. Ordinary machined-pin header
strips are *not* a safe substitute unless measured — Mill-Max's 2.54 mm
headers have 0.61 mm tails and their 1.27 mm headers 0.43 mm, both outside
the receptacle's range. The receptacle needs a 1.0–1.1 mm hole on the
machine; check the site with a 1.0 mm drill shank before ordering.

TSSOP because that is what fits inside the site outline; SOIC would need the
board to overhang the chip ends by ~10 mm, and the D22 neighbourhood is
crowded. 0.65 mm pitch hand-solders fine with flux and a drag.

Use **AHCT**, not HC/HCT or AC: TTL-level inputs (the bus and the ВМ2 are
TTL-compatible), and the speed is in the same band as the original — see
`docs/DESIGN.md` for the timing comparison.

## Building the files

```
./run.sh          # KiCad 7 python, kicad-cli, Java, freerouting.jar, xvfb-run
```

`build_adapter.py` writes the board from the geometry and the netlist;
Freerouting routes it (`search.sh` tries a few placement nudges until every
connection completes); `finish_adapter.py` imports the routes (parsing the
session file itself — pcbnew's importer only works inside the GUI), runs DRC
and saves; `polish_adapter.py` widens the power traces where clearance
allows, adds the GND pours and runs DRC again; `kicad-cli` exports gerbers
and drill. The zip is what goes to the fab; the routed `.kicad_pcb` is there
for anyone who wants to look or move things.

One trap: netclass rules live in the project file, which this pipeline does
not have, so a freshly loaded board falls back to KiCad's 0.25/0.2 mm
defaults and DRC then flags every track. The scripts restore the design's
rules before checking; do the same if you open the board elsewhere.

## Assembly

1. Fit the socket on the machine first: one machined receptacle per hole, 42
   of them (singles, not strips — strips are 2.54 mm and drift off the 2.5 mm
   holes within a row).
2. Solder the SMD parts on the top of the adapter.
3. Push the 42 pins through the adapter from the top, **long (6.35 mm) end
   down**: the flange stops on the top pad and is soldered there, the short
   2.5 mm stub stays above the board. Use the socketed site as the jig (pins
   plugged into the receptacles first, adapter lowered onto them, then
   soldered) so they stay straight; then trim the pins to ~3.5 mm below the
   board, which is what the receptacle takes.
4. Plug in with the pin-1 corner (square pad, marked on the silk) at the
   dimple corner of the site.

## Acceptance test

Boot FODOS and run the canary (`diag/canary` in onerom-1801re2) on a warm
machine for twenty minutes: the bell keeps ticking and the log is clean. That
is the exact failure the original chip had, so it is the exact test.
