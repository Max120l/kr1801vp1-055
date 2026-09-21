# Testing

Three levels, cheapest first. The first one costs five minutes and can
invalidate the whole design, so do it before ordering anything.

## 1. Confirm the polarity on the bench

Everything here rests on the part being **non-inverting**, which was read off a
die schematic rather than measured. It is worth ten minutes to check against the
real chip, because if it is wrong then every '245 in the BOM should be a '640
and no amount of careful layout will save the board.

### The carrier

The package fits no breadboard and, with its 0.5 mm square pins, no machined
receptacle either — the original will not plug into the socket that replaces
it. A bare adapter PCB solves both problems at once: it is a breakout for the
chip *and* a plug for the socket, and once built it stays useful as the A/B
reference against the substitute.

1. Fit the header pins to a bare adapter first (the same round-pin strip as
   the substitute build), **plastic on the underside**, mating end up through
   the board. The tail is only ~3 mm and the board takes 1.6 of it, so with
   the plastic on top there is nothing left to reach the receptacles; on the
   bottom the plastic is just a 2.5 mm standoff. Trim the stubs above the
   board to ~1.5 mm.
2. Set the chip on the top side, **pin 1 at the square pad**, shifted about
   half a millimetre along the row so that each square pin lies against its
   stub on the same 1.7 mm pad. Solder each pair with a small blob. The
   stagger keeps the nearest neighbour 2.8 mm away, so bridges are unlikely.
   Check pin 1 before the first joint — it is the one thing 42 joints later
   cannot fix.
3. The whole stack (receptacle, standoff, board, chip) stands about 10 mm
   above the motherboard, twice the original. Look at what sits above D22 with
   the case closed before committing.

The open ring pads on the top side are the bench test points: clip onto them
for the polarity check below. In the machine, the carrier proves the socket
and the pin height on a chip that is known to run cold, so the first power-up
of the substitute only tests the substitute — and afterwards the two swap in
seconds for a hot A/B on the same socket.

### The polarity check

With the original 055 on the carrier, +5 V on pin 42 and ground on pin 21:

| step | | |
|---|---|---|
| 1 | pin 41 (nOE) → GND | outputs enabled |
| 2 | pin 20 (nA/VW) → GND | direction: V,W → nA |
| 3 | drive pin 1 (V0) high | |
| 4 | read pin 22 (nA0) | **high** ⇒ non-inverting ✓ · **low** ⇒ inverting ✗ |
| 5 | drive pin 1 low, read pin 22 again | should follow |
| 6 | pin 20 → +5 V, drive pin 22, read pin 1 | the other direction |
| 7 | pin 41 → +5 V | both pins should go high-Z |

Also worth doing while it is on the bench, since it is the same setup:

- **pin 38 → pin 17**, with pin 41 both low and high. The three-bit buffer
  should follow C regardless of nOE. If it does not, the die reading is wrong
  about the grounded enable and U3 needs gating after all.
- **The delay stagger.** A scope on pin 1 and pin 22 against pin 9 and pin 30
  should show roughly 32 ns and 24.5 ns. If those are wildly off, the cell
  library's typical delays do not describe this die revision and the timing
  section of [DESIGN.md](DESIGN.md) is guesswork.

Record what you measure. A negative result here is worth more than the rest of
this repository.

## 2. The equivalence proof

```console
$ make check
KR1801VP1-055: original (die cells) vs substitute (74x245)

dir=1  nA -> V/W
dir=0  V/W -> nA
oe_n=1  both sides high-Z
C0-C2 -> A0-A2, independent of /OE

60 checks, 0 mismatches
EQUIVALENT
```

This compares a structural model of the original — built from the gate array's
own cells, wired as its schematic wires them — against a model of the substitute
built from gate primitives, wired as the board wires it. Walking ones catch a
swapped bit or the two bytes on the wrong transceivers; the /OE cases catch a
substitute that stays enabled when it should let go.

A test that cannot fail proves nothing, so:

```console
$ make mutants
  caught      MUTANT_INVERTING
  caught      MUTANT_DIR
  caught      MUTANT_C_GATED
all mutants caught
```

Each mutant is one wire or one part number away from the real design: a '640
instead of a '245, DIR backwards, and U3's enable tied to pin 41 instead of
ground. All three would look reasonable on a schematic.

**What this does not prove.** It is a logic equivalence only. It says nothing
about propagation delay against the machine's real timing, nothing about drive
strength or bus loading, and nothing about the supply transient discussed in
[DESIGN.md](DESIGN.md). It rules out the mistakes that are cheap to make and
expensive to find, and that is all.

## 3. In the machine

The UKNC this project came from has a documented fault that D22 causes, which
makes it an unusually good test fixture: there is a known-bad behaviour to fix,
not just an absence of smoke.

The diagnostic instruments in the sibling
[onerom-1801re2](https://github.com/Max120l/onerom-1801re2) repository already
run through the ROM socket and need no working machine. In rough order:

1. **Before fitting**, reproduce the fault: from cold the machine runs about ten
   minutes, then fails; cooling D22 brings it back within seconds. That
   signature is what the substitute has to remove. With the site already
   socketed, this is the original on its carrier (section 1) — which also
   proves the socket and pin height before the substitute ever goes in.
2. **Fit the substitute** and run the register test (`make_regtest.py`) — it
   touches no memory, so it isolates the bus path this chip is on, and a pass
   takes milliseconds rather than seconds.
3. **Run the soak** (`make_ramtest.py`) for longer than the machine used to
   survive. Ten minutes is the bar to clear; an hour is a result.
4. **Run the machine's own ТЕСТИРОВАНИЕ** for several passes with ОШИБОК 0.
   That is the test that originally convicted D22, in both directions.
5. **Heat it deliberately.** The original failed thermally, so a substitute that
   only works cold has not fixed anything. A hot-air gun at low temperature, or
   just a long run in a warm room.

Step 1 is the one people skip and the one that makes the rest mean something: if
the machine is not currently failing, a working machine afterwards proves
nothing at all.
