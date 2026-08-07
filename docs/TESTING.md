# Testing

Three levels, cheapest first. The first one costs five minutes and can
invalidate the whole design, so do it before ordering anything.

## 1. Confirm the polarity

Everything here rests on the part being **non-inverting**, which was read off a
die schematic rather than measured. It is worth ten minutes to check against the
real chip, because if it is wrong then every '245 in the BOM should be a '640
and no amount of careful layout will save the board.

There are two ways to do it. Prefer the in-circuit one while the machine still
runs: it needs no desoldering, and on a 42-pin planar package soldered into a
machine whose fault is thermal and intermittent, not risking the chip matters
more than the tidiness of the setup.

### In the machine, with a scope

The measurement works in place because **polarity is direction-independent**. A
non-inverting transceiver holds both sides at the same level whenever it is
enabled, whichever way it happens to be driving; an inverting one holds them
complementary. So pin 20 can be left to do whatever the machine is doing with
it — the direction never enters the reading, and two channels are enough.

What does matter is knowing the part is enabled, because with nOE high both
sides are high-Z and the two nets are unrelated. The propagation delay supplies
that for free: while the 055 is driving, one side is a copy of the other lagging
by the figure below, and which one lags says what the direction was. The
uncorrelated stretches are the disabled windows; ignore them. No external
trigger is needed — trigger on ch1 and look for the windows where ch2 tracks it.
With four channels, put nOE (pin 41) and nA/VW (pin 20) on ch3 and ch4 and the
windows can be gated directly instead of inferred.

Probe **both byte groups**. They are independent claims, not one claim measured
twice: the V chain carries three `t371` stages and the W chain one, and if the
die reading has either count wrong then that group inverts and the other does
not. That is exactly the half-the-bus failure [LOGIC.md](LOGIC.md) warns about,
and measuring V0 alone leaves it open.

| ch1 | ch2 | expected lag | |
|---|---|---|---|
| pin 1 (V0) | pin 22 (nA0) | 32.0 ns | low byte, three stages |
| pin 9 (W0) | pin 30 (nA8) | 24.5 ns | high byte, one stage |
| pin 38 (C0) | pin 17 (A0) | 21.75 ns | the three-bit buffer |

| what you see | |
|---|---|
| ch2 follows ch1, same sense | **non-inverting** ✓ — the '245 stands |
| ch2 follows ch1, inverted | **inverting** ✗ — every '245 becomes a '640 |

Start with C0 → A0. Its output driver's enable is tied to ground on the die, so
it is permanently on and tracks continuously with no windows to hunt for — the
one measurement here that needs no interpretation. It settles a *different*
question from the byte paths, being the zero-inversion path through the pad's
`y1` output, so it does not prove the '245 choice on its own. What it does prove
is whether pin 41 reaches those buffers at all, which is the `MUTANT_C_GATED`
question and decides whether U3 needs gating.

Bandwidth is not a constraint. The original's output pads are 16.5 ns, so the
edges are slow and polarity is very nearly a DC relationship: 100 MHz is
luxurious, and 20 MHz would still answer the go/no-go even if it blurred the
delays.

Cautions, roughly in the order they will bite:

- **Measure cold**, in the first minutes, while the machine still behaves. If
  the bit you land on looks mushy, move to another bit in the same group rather
  than trying to read through it. Marginality does not threaten this particular
  reading — a dying driver shows up as weak drive, slow edges or a stuck level,
  whereas inversion is a property of the topology and cannot drift.
- **10× probes, never 1×.** A 1× probe's 50–100 pF hung on an already marginal
  output is a good way to finish it off.
- **The real hazard is mechanical.** 42-pin planar, fine pitch, and a slipped
  tip shorts two bus lines on a running machine. Where the net is reachable
  somewhere else — a via, a series resistor pad, the connector, the same net on
  a neighbouring chip — probe there rather than at the package leg. Short ground
  spring, not the clip lead.

This also produces the delay-stagger measurement in passing: the two lags should
land near 32 and 24.5 ns. If they are wildly off, the cell library's typical
delays do not describe this die revision and the timing section of
[DESIGN.md](DESIGN.md) is guesswork.

**What it cannot settle.** nOE cannot be forced from outside, so the high-Z
release check is not reproduced: in place there is no way to distinguish
"released" from "driving the level the bus already carries". Stretches where the
two sides are plainly uncorrelated are evidence the part let go — weaker than
the bench check below, but not nothing.

### On the bench, with the chip out

Worth doing when the chip is out anyway, which — given the above — means when it
is being replaced. Socket it at that point.

With the original 055 out of the machine, on a breadboard, +5 V on pin 42 and
ground on pin 21:

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
   signature is what the substitute has to remove.
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
