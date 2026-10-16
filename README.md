# A replacement for the КР1801ВП1-055

The 055 is a Soviet gate-array bus transceiver: sixteen bidirectional lines plus
three unidirectional buffers, in a 42-pin through-hole package with the pins
in four staggered rows. It cannot be bought,
and the only machine known to use it is the **Elektronika MS 0511 (UKNC)**,
where it is **D22** — sitting between the peripheral processor and the MPI bus,
so when it fails the machine fails in ways that look like everything except a
transceiver.

This repository works out what the chip does, proves a substitute built from
catalogue parts behaves identically, and lists what to buy.

**Status: built, fitted, and proven — cold and hot.** The fault this repository
exists for was confirmed on the machine in September 2026 by two independent
methods: cooling D22 alone keeps the failing MS 0511 running, and a CPU-side RAM
canary (in onerom-1801re2, `diag/canary`) shows every plane on the CPU's side of
the bus staying clean for hundreds of passes while the peripheral processor —
the side behind D22 — dies hot: black screen, no console bell, keyboard and
hardware reset both ineffective until the machine cools. The 055 was the part to
replace.

A substitute on **adapter revision C** now runs in that site. The machine passes
its own ТЕСТИРОВАНИЕ **fourteen consecutive times with ОШИБОК 0**, and a
purpose-built bus soak has moved **101.8 MiB through the chip in 1629 passes
with zero errors** — including thirteen million transitions in which all sixteen
lines reverse at once, which is the one case the substitute cannot reproduce the
original's design for. Both against a part that failed after about ten minutes
from cold. That also settles the polarity finding below, more cheaply than the
bench check written for it — [TESTING.md](docs/TESTING.md#4-the-result).

And then hot: the machine was deliberately heated, with the soak running, until
the board was too hot to touch, for a further **90 passes with the error count
still at zero**. The original failed after ten minutes from cold and recovered
within seconds of being cooled, so that is the fault's own axis — **the repair
holds where the part it replaces actually broke.** Five minutes at temperature
is a short window and the hot figure deserves a longer run; see
[TESTING.md](docs/TESTING.md#hot).

## The two findings

**It has no state.** Every cell in the die schematic is a gate, a buffer or an
inverter — no flip-flop, no latch, no clock, no feedback path. That was the
question gating this project, because a stateful control block would have forced
a programmable part. It does not: three ordinary chips reproduce it exactly.

**It does not invert.** Each path carries an even number of inversions — four in
the low byte, two in the high byte, zero in the three-bit buffer. The `nA0–nA15`
pin naming records the bus's active-low convention, not an inversion across this
part. So the substitute is the **74x245**, not the '640.

That second one is a correction, and it is now settled on hardware rather than
only on the die. Earlier notes in the sibling
[onerom-1801re2](https://github.com/Max120l/onerom-1801re2) repository called
the part inverting and recommended the '640, reasoning from the bus rather than
from the die. Building that would have inverted the machine's entire address and
data bus. `make mutants` builds it deliberately and shows the test rejecting it —
and a '245-based board now runs in the machine, which a non-inverting substitute
for an inverting part could not do.

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

The machine then agreed with the simulation: a board built to this design runs
as D22, and all three mutants above describe mistakes that would have stopped it
running at all — see [TESTING.md](docs/TESTING.md#4-the-result).

## Files

| | |
|---|---|
| [docs/LOGIC.md](docs/LOGIC.md) | what the chip does, traced cell by cell, with the delays |
| [docs/DESIGN.md](docs/DESIGN.md) | the substitute: parts, pin mapping, timing, what is lost |
| [docs/TESTING.md](docs/TESTING.md) | bench check, the proof, and bringing it up in the machine |
| [adapter/](adapter/README.md) | the 42-pin adapter board: generator, routing, gerbers |
| [bustest/](bustest/README.md) | a FODOS volume of adversarial bus patterns, for the worst case ТЕСТИРОВАНИЕ never produces |
| `rtl/vp1_055_orig.v` | the original, from its own cells |
| `rtl/vp1_055_repl.v` | the substitute, from gate primitives |
| `rtl/lib_1801.v` | the k1801 cell library, vendored unmodified |
| `sim/tb_equiv.v` | the equivalence testbench |

## What is not done

- **The PCB is at revision C** — [adapter/](adapter/README.md): a 31 × 32 mm
  two-layer board with the three chips on top and a 42-pin field in the
  measured four-row site geometry underneath, generated and routed by script,
  gerbers included. Revision A was fabricated and did not fit: it mirrored the
  two sides, and the real package's sides are translated copies (rows
  10 · 11 · 10 · 11 with pin 1 top-left, pin 1 in the inner row). Rev C
  corrects the field, and is the revision now fabricated and running in the
  machine.
- **No scope has ever been on the nOE release edge**, of either part. It is the
  one claim in [DESIGN.md](docs/DESIGN.md#timing) still resting on reasoning
  rather than measurement — though a repair that survives a hot worst-case soak
  is strong circumstantial evidence the margin is there. See
  [TESTING.md](docs/TESTING.md#1-confirm-the-polarity-on-the-bench).
- **The delay stagger is still not reproduced**, and now demonstrably does not
  need to be — at least not cold. The original spread its two bytes 7.5 ns apart
  to limit the supply transient when sixteen drivers switch; two identical '245s
  switch together, and the answer here is decoupling. Thirteen million
  deliberate worst-case transitions have now gone through without a bad bit, so
  this is a solved problem rather than an out-voted one. Hot is still untested.

## Credits

The die schematic, the pin description and the cell library are the work of the
[1801BM1/k1801](https://github.com/1801BM1/k1801) project, which reverse
engineered this and a dozen sibling chips from die photographs. None of this
would be possible without it. See [THIRD-PARTY.md](THIRD-PARTY.md).
