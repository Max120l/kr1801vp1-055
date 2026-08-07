# The substitute

Three chips replace one. The logic is settled — see [LOGIC.md](LOGIC.md) — and
this file is the parts and the wiring that follow from it.

## Parts

| ref | part | function |
|---|---|---|
| U1 | 74AHCT245 | low byte: nA0–nA7 ↔ V0–V7 |
| U2 | 74AHCT245 | high byte: nA8–nA15 ↔ W0–W7 |
| U3 | 74AHCT125 (or 3 sections of a '244/'541) | C0–C2 → A0–A2, always enabled |
| C1–C3 | 100 nF X7R, 0402/0603 | one per chip, right at the pins |
| C4 | 10 µF ceramic | bulk |

**'245, not '640.** The '640 is the inverting variant and this part does not
invert. Same package, same pinout, one digit different in the order code — so
this is worth checking on the reel and not only on the schematic.

**'AHCT, not 'HC.** The UKNC's logic around D22 is a mixture of TTL-compatible
Soviet parts, and AHCT has TTL input thresholds (V_IH 2.0 V) where AHC has CMOS
ones (V_IH 3.85 V at 5 V). A '245 in HC would be marginal against anything
driving a weak TTL high. AHCT is also close to the original's speed; see below.

**U3 must not be inverting and must not be gated.** Its enable is tied to ground
on the die and pin 41 does not reach it. A '240 (inverting) or an enable wired
to /OE both pass a casual inspection and both are wrong — `make mutants`
demonstrates the test catching the second.

## Wiring

The whole point of the mapping below is that it needs no glue: no inverter on
DIR, no gate on /OE, nothing.

| 055 pin | signal | goes to |
|---|---|---|
| 1–8 | V0–V7 | U1 **B1–B8** |
| 9–16 | W0–W7 | U2 **B1–B8** |
| 22–29 | nA0–nA7 | U1 **A1–A8** |
| 30–37 | nA8–nA15 | U2 **A1–A8** |
| 20 | nA/VW | U1 **DIR**, U2 **DIR** — direct |
| 41 | nOE | U1 **/OE**, U2 **/OE** — direct |
| 38–40 | C0–C2 | U3 inputs |
| 17–19 | A0–A2 | U3 outputs |
| 21 | GND | U1/U2/U3 GND, U3 enables |
| 42 | VCC | U1/U2/U3 VCC |

Why the sides fall out this way: a '245 with `DIR` high drives **B** from **A**.
The die enables the V/W drivers when DIR is high. So V/W must be the B side and
nA the A side, and then `DIR` and `/OE` connect straight through with the same
sense the original uses.

## Timing

| path | original | 74AHCT245 typ | 74AHCT245 max |
|---|---|---|---|
| data through, V group | 32.0 ns | ~7 ns | ~11.5 ns |
| data through, W group | 24.5 ns | ~7 ns | ~11.5 ns |
| enable to output | 11.5 / 15.25 ns | ~9 ns | ~14 ns |

The substitute is **two to four times faster than the part it replaces**, in a
circuit designed around the slower one. That direction is the safe one for
propagation delay — data arrives earlier — but it is not automatically safe for
*release*: a buffer that goes high-Z sooner than the original can drop data
before something downstream has latched it.

Worth being honest that this is the main un-analysed risk in the design. Two
reasons it is probably fine, and one thing to check:

- The enable path is the closest of the three to the original (9 ns against
  11.5), so the *change* in release timing is the smallest of the three numbers.
- Whatever drives pin 41 is producing an envelope sized for a chip with 16.5 ns
  output pads, so the envelope has margin built in.
- **Check it anyway** with a scope: nOE against nA during a read, before and
  after. [TESTING.md](TESTING.md) has the procedure.

If a hold problem ever does appear, the fix is an RC on the enable line rather
than a slower logic family — the data paths are fine and slowing them would give
back margin that is currently helping.

## The lost asymmetry

The original staggers its two bytes by 7.5 ns so that sixteen output drivers do
not switch simultaneously. Two identical '245s switch together.

This is a supply-current question, not a logic one, and modern parts make it
both worse and better: AHCT edges are much faster than the gate array's, so the
di/dt per driver is higher, but the package inductance and the available
decoupling are far better than 1980s practice. The answer is C1–C3 as close to
the power pins as the layout allows, and the 10 µF nearby.

If it ever proves to matter, the cheap experiment is a series resistor pack on
one byte — but measure before adding parts.

## Form factor

The original is a 42-pin planar package, which is the hard part of this project
and is deliberately not solved here. Options, roughly in order of effort:

1. **An adapter board** carrying U1–U3 on top, with a pin field matching the
   original's footprint underneath. Needs the exact package drawing.
2. **Flying leads** to a small board mounted elsewhere in the machine — ugly,
   reversible, and entirely adequate for proving the design before committing to
   a layout.
3. Reuse the k1801 project's own `055/sch/055.lay6` footprint work if it turns
   out to contain the package geometry — worth opening in Sprint Layout before
   redrawing it.

**Socket the original when removing it.** Nothing here is proven on hardware
yet, and the ability to put the old chip back is the difference between an
experiment and a one-way trip.
