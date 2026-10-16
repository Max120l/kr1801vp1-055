# Testing

In the order it was done, and what each step actually proved. Section 1 is the
check that could have invalidated the design before anything was ordered;
section 4 is what happened when one was built.

## 1. The polarity check

Everything rests on the part being **non-inverting**, read off a die schematic
rather than measured. If it were wrong, every '245 in the BOM should be a '640
and no layout would save the board.

**This is now answered**, and not by this procedure: a '245-based board runs in
the machine, which a non-inverting substitute for an inverting part could not
do. The bench method is kept because it is how you would check a different
specimen, and the carrier is kept because it is useful hardware in its own
right.

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

The open ring pads on the top side are the bench test points. In the machine,
the carrier proves the socket and the pin height on a chip known to run cold,
and afterwards the two swap in seconds for an A/B on the same socket.

### On the bench

With the original on the carrier, +5 V on pin 42 and ground on pin 21:

| step | | |
|---|---|---|
| 1 | pin 41 (nOE) → GND | outputs enabled |
| 2 | pin 20 (nA/VW) → GND | direction: V,W → nA |
| 3 | drive pin 1 (V0) high | |
| 4 | read pin 22 (nA0) | **high** ⇒ non-inverting ✓ · **low** ⇒ inverting ✗ |
| 5 | drive pin 1 low, read pin 22 again | should follow |
| 6 | pin 20 → +5 V, drive pin 22, read pin 1 | the other direction |
| 7 | pin 41 → +5 V | both pins should go high-Z |

Also worth doing on the same setup: **pin 38 → pin 17** with pin 41 both low and
high — the three-bit buffer should follow C regardless of nOE, and if it does
not then the die reading is wrong about the grounded enable and U3 needs gating.
And a scope on pins 1/22 against 9/30 should show roughly 32 ns and 24.5 ns,
confirming the delay figures in [DESIGN.md](DESIGN.md).

### In circuit, without removing anything

The same question can be answered on a running machine with two scope channels,
because **polarity is direction-independent**: an enabled transceiver holds both
sides at the same level whichever way it drives, an inverting one holds them
complementary, so pin 20 never enters the reading. Knowing the part is enabled
comes free from the propagation delay — while it is driving, one side is a copy
of the other lagging by 32.0 ns (pin 1 → 22, low byte) or 24.5 ns (pin 9 → 30,
high byte), and the uncorrelated stretches are the nOE-high windows.

Probe both byte groups: a wrong stage count in either inverts that half of the
bus alone. Use 10× probes. What this cannot do is force nOE, so step 7 above has
no in-circuit equivalent.

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

1. **Before fitting**, reproduce the fault: from cold the machine runs about ten
   minutes, then fails; cooling D22 brings it back within seconds. That
   signature is what the substitute has to remove. With the site socketed, this
   is the original on its carrier. ✔ done
2. **Fit the substitute** and run the register test (`make_regtest.py` from
   [onerom-1801re2](https://github.com/Max120l/onerom-1801re2)) — it touches no
   memory, so it isolates the bus path this chip is on. *not reported*
3. **Run the soak** (`make_ramtest.py`) for longer than the machine used to
   survive. *not reported*
4. **Run the machine's own ТЕСТИРОВАНИЕ** for several passes with ОШИБОК 0.
   That is the test that originally convicted D22, in both directions. ✔ done
5. **Heat it deliberately.** The original failed thermally, so a substitute that
   only works cold has not fixed anything. ✔ done

Step 1 is the one people skip and the one that makes the rest mean something: if
the machine is not currently failing, a working machine afterwards proves
nothing at all.

## 4. The result

A substitute on adapter revision C runs as D22. The machine passes its own
ТЕСТИРОВАНИЕ fourteen consecutive times with ОШИБОК 0, and
[`bustest`](../bustest/README.md) — a purpose-built bus soak running on the
machine — came through cold and hot without a single bad word:

| | cold | hot | total |
|---|---|---|---|
| passes | 1629 | 90 | 1719 (~100 min) |
| words compared | 26 689 536 | 1 474 560 | 28 164 096 |
| data through D22 | 101.8 MiB | 5.6 MiB | 107.4 MiB |
| worst-case transitions | 13 344 768 | 737 280 | 14 082 048 |
| **errors** | **0** | **0** | **0** |

"Worst-case transitions" are words of alternating `0000`/`FFFF`, where all
sixteen lines reverse at the same instant. That is precisely the event the
original's 7.5 ns byte stagger existed to spread, and the one thing two
identical '245s cannot reproduce — so it is the pattern this design most needed
to be tested against, and the one it was.

The hot figures were taken with the board deliberately heated until it was far
too hot to touch, against an original that failed after about ten minutes from
cold and recovered within seconds of being cooled.

### What it settles

A running machine is a strong result here, because the three mistakes the
simulation guards against are fatal rather than subtle — each would have stopped
the machine dead:

| | would have caused | status |
|---|---|---|
| `MUTANT_INVERTING` — '640 for '245 | the whole address and data bus inverted | excluded |
| `MUTANT_DIR` — DIR backwards | every transfer driving the wrong way | excluded |
| `MUTANT_C_GATED` — U3 enable on pin 41 | A0–A2 dropping out whenever nOE rose | excluded |

The first is the one that mattered: the polarity reading came off a die
schematic, and section 1 exists because getting it wrong would have invalidated
the entire BOM.

**The lost stagger is settled too.** It had only ever had an argument behind it
— modern decoupling beats 1980s practice, so the spike should be survivable.
Fourteen million worst-case transitions without a bad bit is not an argument.

Rev C also fits, which rev A did not, so the pin field and the four-row stagger
in [DESIGN.md](DESIGN.md#form-factor) are confirmed by a board that plugs in.

The failure mode was reproduced in the original, localised two independent ways,
removed by the substitute, and the substitute then taken past the temperature
that killed the original while carrying the most hostile data the bus can take.

### As built

| ref | fitted | |
|---|---|---|
| U1, U2 | 74AHCT245PWR | TSSOP-20; AHCT as the part-choice argument requires |
| U3 | 74AHCT125PWR | TSSOP-14, three of four sections used |
| C1–C3 | 100 nF X7R (LCSC C16082) | one per chip |
| C4 | 10 µF 16 V X5R (Samsung CL21A106K0FNNNE) | bulk |
| board | adapter rev C | [adapter/](../adapter/README.md) |

Two notes on the substitutions, neither a problem in the running unit:

- **C4 is X5R where the table says ceramic.** X5R is rated to +85 °C against
  X7R's +125 °C, worth remembering in a machine whose defining fault was
  thermal. The 16 V rating is the more important number and it is generous.
- **The '125's fourth section is spare.** An unused CMOS input must be tied, not
  left floating, or it self-biases near threshold and draws supply current.
  Worth confirming against the rev C netlist.

### Why the hot run stopped at 90 passes

Five minutes at temperature, not an hour, and that was a decision rather than an
omission. Heating a forty-year-old machine to re-test a part that is
demonstrably fine puts the risk on everything *except* the thing being measured:
the electrolytics, the remaining period ICs, and the adapter's own X7R/X5R
capacitors.

It is enough because the question was never whether modern logic survives heat
but whether *the machine* still fails when hot — it does not, and more passes
answer the same question again. A 74AHCT245 is specified across a range that
comfortably contains "too hot to touch", so running clean there is a part
behaving inside its ratings rather than a margin that happened to hold; the
original was a degraded gate array outside any specification at all. And the
failure being repaired was propagation delay stretching with temperature, where
the substitute starts two to four times faster and is new rather than degraded.

Note also that five minutes *at* temperature is not the weaker version of ten
minutes *reaching* it. The original's ten minutes was the time it took to heat
itself to failure from cold; the substitute was already well past that
temperature for all 90 passes.

### Still worth running

- **Rungs 2 and 3** — the `make_regtest.py` and `make_ramtest.py` instruments
  from onerom-1801re2. The register test isolates this bus path specifically,
  which no amount of whole-machine testing does.
- **Power cycles.** Twenty cold starts. Enable-envelope margin shows up as an
  intermittent failure to boot rather than as a wrong bit, so no soak finds it.
- **The scope check below**, the last claim here resting on reasoning rather
  than measurement.

## 5. The release edge

[DESIGN.md](DESIGN.md#timing) says the substitute lets go of the bus a few
nanoseconds sooner than the part the circuit was built around, calls that the
main un-analysed risk, and asks for a scope. Everything since is
circumstantial — the machine runs, cold and hot, under the worst data the bus
can carry. Good evidence, not a measurement.

It is easy now: the substitute is fitted and the adapter brings every signal up
to a 2.5 mm pad field instead of a 0.65 mm TSSOP lead.

### Where to probe

The pin field's top-side ring pads, board oriented as the silk reads with pin 1
at top-left:

| | pin | pad | where it is |
|---|---|---|---|
| **ch1** | 41 | nOE | inner row, second pad from the top of the **right** side |
| **ch2** | 22 | nA0 | the corner pad, bottom of the right side, outer row |
| ch3 | 20 | DIR | outer row, near the bottom of the **left** side |
| gnd | 21 | GND | inner row, bottom-left corner |

ch1 and ch2 are both on the right-hand edge, 24 mm apart, so two probes sit
without crossing. Pin 41's nearest neighbour is pin 42 (VCC) 2.8 mm away
diagonally — enough room, but it is +5 V and this is a working machine.

Ground is the awkward part: pin 21 is the only ground pin, 31 mm from pin 41,
with no GND via closer. A short lead to motherboard ground near the site beats a
long clip back to pin 21 — at these edge rates 20–30 mm is acceptable, a 150 mm
clip lead will manufacture ringing that looks like a finding. **10× probes**: a
1× probe's 50–100 pF on a bus line changes what is being measured.

### The measurement

Trigger **rising edge on ch1 (nOE)** at about 1.5 V — the disable edge, the one
in question. Start at 200 ns/div to see where the release sits in the cycle,
then zoom to 10 ns/div.

Measure **t_dis**: from nOE crossing 1.5 V to nA0 *departing* its driven level.
Departure, not arrival — a driver going high-Z does not snap the line, it drifts
toward the termination on an RC curve. Take the point where it leaves the valid
level by ~0.3 V. Expect roughly 5–14 ns for a 74AHCT245 against the original's
16.5 ns output pads.

**Probe a line driven LOW at the moment of release.** The MPI bus is active low
and terminated high, so a line released from low visibly ramps while one
released from high barely moves.

### What would count as a problem

Not the absolute number — the margin. On the wide view, find how long the data
had already been stable before nOE rose. On an asynchronous handshake bus the
data is taken and *then* the cycle ends, so that gap should be tens to hundreds
of nanoseconds, which swamps the few nanoseconds under discussion and closes the
risk quantitatively.

It is a finding only if the release crowds the end of the data window. The fix
then is on the enable, not the data: an RC on nOE delaying only the disable
edge, as [DESIGN.md](DESIGN.md#timing) says.

The complete answer would be an A/B against the original on its carrier, which
needs no knowledge of the handshake timing at all — but it costs pulling a
working repair to fit a chip known to be failing. Do the single-ended version
first; the A/B only earns its risk if the margin comes back uncomfortably small.
