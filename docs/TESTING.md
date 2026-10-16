# Testing

Three levels, cheapest first. The first one costs five minutes and can
invalidate the whole design, so do it before ordering anything. Section 4
records what happened when one was actually built, and what it did and did not
settle.

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

### Without taking the chip out

The same question can be answered with the 055 still in a running machine, two
scope channels and no desoldering. Worth knowing because it needs neither the
carrier nor a working socket, and because it is the only version of this check
that can be repeated later on a machine that has started misbehaving again.

It works because **polarity is direction-independent**: an enabled transceiver
holds both sides at the same level whichever way it is driving, and an inverting
one holds them complementary. So pin 20 need not be known or controlled. What
does matter is knowing the part is enabled, and the propagation delay gives that
for free — while the 055 is driving, one side is a copy of the other lagging by
the figure below, and the uncorrelated stretches are the nOE-high windows.

| ch1 | ch2 | expected lag | |
|---|---|---|---|
| pin 1 (V0) | pin 22 (nA0) | 32.0 ns | low byte, three stages |
| pin 9 (W0) | pin 30 (nA8) | 24.5 ns | high byte, one stage |
| pin 38 (C0) | pin 17 (A0) | 21.75 ns | always enabled, no windows to hunt |

ch2 tracking ch1 in the same sense means non-inverting; tracking it inverted
means the BOM is wrong. Probe both byte groups: the V chain has three `t371`
stages and the W chain one, and a wrong count in either inverts that half of the
bus alone. The two lags also give the delay stagger directly.

Measure cold, in the first minutes, and use 10× probes — a 1× probe's 50–100 pF
on an already marginal output is a good way to finish it off. The package helps
here: four staggered rows at 2.5 mm leave the nearest neighbour 2.8 mm away, so
this is ordinary probing rather than fine-pitch work.

What it cannot do is force nOE, so step 7 above has no in-circuit equivalent.

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

## 4. The result

A substitute on adapter revision C has been built and fitted as D22. The machine
runs: **fourteen consecutive passes of its own ТЕСТИРОВАНИЕ with ОШИБОК 0**, and
over thirty minutes of continuous operation against an original that failed
after about ten from cold.

Rung 4 of the ladder in section 3 is therefore cleared, and rung 5 in its weaker
form — thirty minutes at room temperature, not a deliberate heat soak. Rungs 2
and 3 have not been reported.

### What the working substitute settles

A running machine is not a weak result here, because the three mistakes the
simulation guards against are all fatal rather than subtle. Each would have
stopped the machine dead, so fourteen clean passes exclude all three:

| | would have caused | status |
|---|---|---|
| `MUTANT_INVERTING` — '640 for '245 | the whole address and data bus inverted | excluded |
| `MUTANT_DIR` — DIR backwards | every transfer driving the wrong way | excluded |
| `MUTANT_C_GATED` — U3 enable on pin 41 | A0–A2 dropping out whenever nOE rose | excluded |

The first is the one that mattered. The polarity reading came off a die
schematic, and section 1 exists because getting it wrong would have invalidated
the entire BOM. A non-inverting board cannot run in place of an inverting part,
so the machine running **is** the confirmation — a stronger one than the bench
check would have produced, and it arrived by building the thing rather than by
measuring first.

Rev C also fits, which rev A did not. The pin field and the four-row stagger in
[DESIGN.md](DESIGN.md#form-factor) are confirmed by a board that plugs in.

Two of the three risks [DESIGN.md](DESIGN.md) flags as un-analysed now have
evidence against them:

- **Release timing.** The substitute lets go of the bus a few nanoseconds sooner
  than a part the circuit was designed around. The envelope evidently has the
  margin.
- **The lost stagger.** Sixteen drivers switching together, with decoupling in
  place of the original's 7.5 ns split, does not upset the machine.

Both are *evidence*, not measurement. Neither has been seen on a scope, and the
stagger has not been tested against a worst-case pattern — see below.

### The worst case, measured once

The first run of [bustest](../bustest/README.md) on a fodos30 volume did produce
a result, although not the one it was written to collect.

The procedure stopped at its `DIFFERENCES` step — the comparator dependency the
README had already flagged as unverified on a FODOS clone — but it stopped
*after* the copy, leaving `SCRTCH.DAT` on the disk. Reading that scratch file
off the returned image settles the question the comparator was supposed to
answer: **it is byte-for-byte identical to `WORST.DAT`**, all 25 600 words of it.

So one hundred blocks of alternating `0000`/`FFFF` — the pattern that makes all
sixteen lines reverse on every single word, which is exactly what the original's
7.5 ns stagger existed to spread — crossed the bus twice, read and written, with
no error in any word.

That is a measurement rather than an inference, and it is the first direct
evidence that two identical '245s switching together is not a problem in this
machine. It is one pass at room temperature, not a soak and not hot, so it
bounds the risk rather than closing it.

It also says the copy path itself is sound: `COPY` preserved arbitrary binary
data faithfully, so RT-11's default is image mode and the pattern files survive
a round trip through the PP's bus unchanged.

### As built

| ref | fitted | |
|---|---|---|
| U1, U2 | 74AHCT245PWR | TSSOP-20; AHCT as the part-choice argument requires |
| U3 | 74AHCT125PWR | TSSOP-14, three of four sections used |
| C1–C3 | 100 nF X7R (LCSC C16082) | one per chip |
| C4 | 10 µF 16 V X5R (Samsung CL21A106K0FNNNE) | bulk |
| board | adapter rev C | [adapter/](../adapter/README.md) |

Two notes on the substitutions, neither of them a problem in the running unit:

- **C4 is X5R where the table says ceramic.** X5R is rated to +85 °C against
  X7R's +125 °C, which is worth remembering in a machine whose defining fault
  was thermal. The 16 V rating is the more important number and it is generous:
  a 10 µF ceramic on a 5 V rail keeps most of its capacitance only because it is
  so far from its voltage limit.
- **The '125's fourth section is spare.** An unused CMOS input must be tied, not
  left floating, or it self-biases near threshold and draws supply current —
  precisely the noise this design spends four capacitors avoiding. Worth
  confirming against the rev C netlist.

### The soak, at room temperature

`BUSTST` ran for about ninety-five minutes on the repaired machine:

```
BUSTST - KR1801VP1-055 bus stress. Stop with CTRL-C.
PASS 003135 ERRS 000000
```

Octal 3135 is **1629 passes**, and every one of them compared clean:

| | |
|---|---|
| words compared | 26 689 536 |
| word transfers over the bus | 53 379 072 (each written, then read back) |
| data through D22 | 101.8 MiB |
| disk blocks moved | 208 512 |
| errors | **0** |

Of that, `WORST.DAT` alone accounts for **6 672 384 words of alternating
`0000`/`FFFF`** — over thirteen million transitions in which all sixteen lines
reverse at the same instant. That is precisely the event the original's 7.5 ns
stagger existed to spread, and the one thing two identical '245s cannot
reproduce.

**That closes the stagger question at room temperature.** It had only ever had
an argument behind it — decoupling is better than 1980s practice, so the spike
should be survivable — and then a single measured pass. Thirteen million
worst-case transitions without a bad bit is no longer an argument.

Three caveats, none of them small:

- **Room temperature only.** The original failed thermally. A substitute that
  passes cold has not been tested where the part it replaces actually broke.
- **It is a path test, not a chip test.** Anything this could have caught lies
  somewhere between the disk surface and memory. D22 carries all of it, but so
  do other things.
- **The release timing is still unmeasured.** No scope has been on the nOE
  edge; see [DESIGN.md](DESIGN.md#timing).

### Still worth running

Nothing above specifically stresses the one place this design knowingly departs
from the original, which is the simultaneous switching of all sixteen drivers.
ТЕСТИРОВАНИЕ chooses its own patterns and may never produce the worst case.

- **An adversarial disk verify.** With a floppy emulator available, write a file
  whose words alternate `0000`/`FFFF`, read it back and compare. Every transfer
  then forces all sixteen lines to reverse together, which is what the stagger
  existed to spread. Follow with `5555`/`AAAA` for adjacent-bit coupling and a
  walking one for stuck bits. A self-checking, data-dependent loop is a better
  instrument for a transceiver than any pass/fail selftest, because one bad bit
  surfaces as a mismatch instead of being averaged away. Note the traffic has to
  reach the peripheral processor's side of the bus to touch this chip at all,
  which is why disk I/O is the right vehicle and a CPU-side memory test is not.
- **Sustained I/O.** Long disk-to-disk copies and verifies keep the PP's side of
  the bus busy for hours.
- **Rungs 2 and 3**, the `make_regtest.py` and `make_ramtest.py` instruments
  from onerom-1801re2. The register test isolates this bus path specifically,
  which no amount of whole-machine testing does.
- **Heat, deliberately — now the only test that matters.** Everything above is
  cold. The original ran about ten minutes from cold and then failed, recovering
  within seconds of being cooled, so temperature is the axis the whole fault
  lived on. `BUSTST` reports a bad word the moment it happens, which makes a
  hot run finally worth doing: warm the area with a hair dryer while it runs and
  watch `ERRS`. A substitute that holds at 1629 passes cold and holds again hot
  is the end of this project.
- **Power cycles.** Twenty cold starts. Enable-envelope margin shows up as an
  intermittent failure to boot rather than as a wrong bit, so no soak finds it.
- **A hot A/B on the socket**, which the carrier makes a seconds-long swap: the
  original back in, warmed until it dies, then the substitute in the same site
  under the same heat. That is the comparison the whole project is for.
- **The scope check [DESIGN.md](DESIGN.md) asks for** — nOE against nA during a
  read — now easy and non-destructive on the fitted substitute.
