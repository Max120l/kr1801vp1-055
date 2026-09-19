# A replacement for the КР1801ВП1-055

The 055 is a Soviet gate-array bus transceiver: sixteen bidirectional lines plus
three unidirectional buffers, in a 42-pin planar package. It cannot be bought,
and the only machine known to use it is the **Elektronika MS 0511 (UKNC)**,
where it is **D22** — sitting between the peripheral processor and the MPI bus,
so when it fails the machine fails in ways that look like everything except a
transceiver.

This repository works out what the chip does, proves a substitute built from
catalogue parts behaves identically, and lists what to buy.

**Status: logic settled and proven in simulation; the fault this repository
exists for is now confirmed on the machine (September 2026).** Two independent
methods agree: cooling D22 alone keeps the failing MS 0511 running, and a
CPU-side RAM canary (in onerom-1801re2, `diag/canary`) shows every plane on
the CPU's side of the bus staying clean for hundreds of passes while the
peripheral processor — the side behind D22 — dies hot: black screen, no
console bell, keyboard and hardware reset both ineffective until the machine
cools. The 055 is the part to replace. Nothing built yet; the polarity finding
below should still be confirmed on the real chip (cold) before ordering —
[TESTING.md](docs/TESTING.md#1-confirm-the-polarity-on-the-bench) is a ten-minute
bench check.

## The two findings

**It has no state.** Every cell in the die schematic is a gate, a buffer or an
inverter — no flip-flop, no latch, no clock, no feedback path. That was the
question gating this project, because a stateful control block would have forced
a programmable part. It does not: three ordinary chips reproduce it exactly.

**It does not invert.** Each path carries an even number of inversions — four in
the low byte, two in the high byte, zero in the three-bit buffer. The `nA0–nA15`
pin naming records the bus's active-low convention, not an inversion across this
part. So the substitute is the **74x245**, not the '640.

That second one is a correction. Earlier notes in the sibling
[onerom-1801re2](https://github.com/Max120l/onerom-1801re2) repository called
the part inverting and recommended the '640, reasoning from the bus rather than
from the die. Building that would have inverted the machine's entire address and
data bus. `make mutants` builds it deliberately and shows the test rejecting it.

## The substitute

| ref | part | |
|---|---|---|
| U1, U2 | 74AHCT245 | the sixteen bidirectional lines, one per byte |
| U3 | 74AHCT125 | C0–C2 → A0–A2, permanently enabled |
| C1–C4 | 100 nF × 3, 10 µF | decoupling |

`nA` to the '245 A side, `V`/`W` to the B side, pin 20 straight to `DIR`, pin 41
straight to `/OE`. No glue logic at all. Full pin mapping, part-choice reasoning
and the timing comparison are in [DESIGN.md](docs/DESIGN.md).

## Proving it

```console
$ make check                 # substitute vs the original's own gate-array cells
60 checks, 0 mismatches
EQUIVALENT

$ make mutants               # and the test can actually fail
  caught      MUTANT_INVERTING
  caught      MUTANT_DIR
  caught      MUTANT_C_GATED
all mutants caught
```

The reference model is structural: it instantiates the k1801 project's own cell
library, wired the way the die schematic wires it, rather than describing what
the chip is believed to do. Needs Icarus Verilog.

## Files

| | |
|---|---|
| [docs/LOGIC.md](docs/LOGIC.md) | what the chip does, traced cell by cell, with the delays |
| [docs/DESIGN.md](docs/DESIGN.md) | the substitute: parts, pin mapping, timing, what is lost |
| [docs/TESTING.md](docs/TESTING.md) | bench check, the proof, and bringing it up in the machine |
| `rtl/vp1_055_orig.v` | the original, from its own cells |
| `rtl/vp1_055_repl.v` | the substitute, from gate primitives |
| `rtl/lib_1801.v` | the k1801 cell library, vendored unmodified |
| `sim/tb_equiv.v` | the equivalence testbench |

## What is not done

- **No PCB.** The 42-pin planar footprint is the hard part and is untouched.
  [DESIGN.md](docs/DESIGN.md#form-factor) lists the options; flying leads to a
  small board are enough to prove the design before anyone draws a layout.
- **No hardware test.** Everything here is a reading of a schematic and a
  simulation of that reading.
- **The delay stagger is not reproduced.** The original deliberately makes its
  two bytes 7.5 ns apart to spread the supply current when sixteen drivers
  switch. Two identical '245s switch together; the answer is decoupling, and it
  is discussed rather than solved.

## Credits

The die schematic, the pin description and the cell library are the work of the
[1801BM1/k1801](https://github.com/1801BM1/k1801) project, which reverse
engineered this and a dozen sibling chips from die photographs. None of this
would be possible without it. See [THIRD-PARTY.md](THIRD-PARTY.md).
