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

A built substitute has since run in the machine without trouble, which is
evidence that the margin is there but is not the measurement — nobody has put a
scope on the release edge yet. The check is easier now than when this was
written, because it can be done on the working board instead of the original.

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

If it ever proves to matter, the cheap experiment is a series resistor pack —
22–33 Ω — on one byte, but measure before adding parts. So far it has not
proved to matter: a built unit runs without it. That is not a worst-case
result, though, because nothing has yet driven all sixteen lines through
`0000`/`FFFF` transitions on purpose — see
[TESTING.md](TESTING.md#still-worth-running).

### Why not a delay line

The obvious way to put the 7.5 ns back is a delay line, and it does not work
here: **delay lines are unidirectional and these sixteen paths are not.** A
lumped-LC module or a buffer-chain delay has an input and an output, so
restoring the stagger would mean splitting every bit into two steered
unidirectional paths — thirty-two delay elements plus direction logic, which is
no longer a '245 and is more complicated than the chip it replaces.

It would also be aimed at the wrong signal. Data arriving *earlier* is safe on
an asynchronous handshake bus, because the end of the valid window is set by the
source holding data until the handshake completes, not by this part's delay: a
faster transceiver moves the window's start earlier and leaves its end where it
was, so the window widens rather than shifts. The one edge that genuinely moves
is the release, and that lives on the nOE path, not the data path — which is why
the fix suggested above is an RC on the enable rather than a slower data path.
It is also the smallest of the three differences: 11.5/15.25 ns against ~9 ns
typical, a few nanoseconds, not the twenty-odd on the data paths.

Series resistors survive the objection that kills delay lines, because a
resistor is bidirectional. That is what makes the 22–33 Ω pack above the right
shape of fix: it damps the edge and cuts the peak current in both directions,
with no steering logic and no change to the logic model that `make check`
proves.

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
