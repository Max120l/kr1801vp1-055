# What the КР1801ВП1-055 actually does

Traced from the die-level schematic published by the
[1801BM1/k1801](https://github.com/1801BM1/k1801) project (`055/sch/055.pdf`),
using that project's own gate-array cell library (`lib/rtl/lib_1801.v`) for the
cell semantics. Everything below is derived from those two files and is
checkable against them.

## The pins

| pin | name | direction | |
|---|---|---|---|
| 1–8 | V0–V7 | bidirectional | low byte, **three** gate delays |
| 9–16 | W0–W7 | bidirectional | high byte, **one** gate delay |
| 17–19 | A0–A2 | output | repeats C0–C2 |
| 20 | nA/VW | input | direction |
| 21 | GND | | |
| 22–37 | nA0–nA15 | bidirectional | the other side of V and W |
| 38–40 | C0–C2 | input | |
| 41 | nOE | input | high disables nA, V, W |
| 42 | VCC | | +5 V |

## The cells it is built from

Five cell types appear, and the library defines all of them:

| cell | function | delay |
|---|---|---|
| `t370` | `y = ~x` | 3.75 ns |
| `t371` | dual inverter, one section per direction | 3.75 ns |
| `t373` | `y = ~(x1 \| x3)` — 2-input NOR | 4.50 ns |
| `t428` | `y = x` — non-inverting buffer | 3.00 ns |
| `t429` | `y = ~x` | 4.00 ns |
| `tINPUT` | pad: `y1 = x`, `y2 = ~x` | 5.25 / 4.25 ns |
| `tOUTPUT_OE` | pad: `y = oe ? Z : x`, **enable active low** | 16.50 ns |

**Every one is combinational.** There is no flip-flop, no latch, no clock input
and no feedback path anywhere in the drawing. That answers the question that was
gating this project: the control logic has no state, so a substitute needs no
programmable part — ordinary catalogue transceivers reproduce it exactly.

## It is NON-INVERTING

This is the single most important fact in this file, it is easy to get wrong,
and getting it wrong produces a board that inverts the machine's entire address
and data bus.

The pin naming invites the opposite conclusion: one side is written `nA0–nA15`
with a bar and the other `V`/`W` without. That bar records the MPI bus's
active-low convention, **not** an inversion across this part.

Count the inversions in the actual path. Each bidirectional pin's input pad is
used through its **`y2`** output — the complement — with `y1` left as an
unconnected stub in the drawing. So:

```
V group   pad(y2) + t371 + t371 + t371   = 4 inversions   -> non-inverting
W group   pad(y2) + t371                 = 2 inversions   -> non-inverting
```

Both counts are even, in both directions, in both groups. The odd stage counts
(three and one) are chosen so that the two halves keep the *same* polarity while
having *different* delays — with two and one they would disagree, and half the
bus would come out inverted.

The three-bit buffer is different in construction and reaches the same place: it
takes the pad's **`y1`** (true) output with no inverter after it, so zero
inversions. Non-inverting as well.

> **This corrects an earlier note** in the sibling `onerom-1801re2` repository,
> which described the part as inverting and recommended the 74x640. That came
> from reasoning about the bus rather than from the die, and it was wrong. The
> correct substitute is the **74x245**. `make mutants` builds the '640 version
> deliberately and shows the equivalence test rejecting it.

## The control block

```
        A21 = t370:  dir_n   = ~DIR
        J21 = t373:  j       = ~(nOE | DIR)
        B21 = t373:  b       = ~(nOE | dir_n)
        K21 = t429:  en_nA_n = ~j =  (nOE | DIR)      -> 4 × t428 fanout
        E17 = t429:  en_V_n  = ~b =  (nOE | ~DIR)     -> 4 × t428 fanout
```

`tOUTPUT_OE` disables on a high, so a driver is on when its term is 0:

| nOE | nA/VW | drivers on | direction |
|---|---|---|---|
| 1 | × | none | both sides high-Z |
| 0 | 0 | nA0–nA15 | V,W → nA |
| 0 | 1 | V0–V7, W0–W7 | nA → V,W |

which is exactly the datasheet text, and exactly a 74x245's `DIR` + `/OE`.

The four `t428` buffers per chain are fanout only — sixteen bit slices are too
much load for one cell — and are logically identical.

## Delays, and the deliberate asymmetry

| path | cells | total |
|---|---|---|
| V group, either direction | pad 4.25 + 3 × 3.75 + pad 16.50 | **32.0 ns** |
| W group, either direction | pad 4.25 + 1 × 3.75 + pad 16.50 | **24.5 ns** |
| nOE/DIR → nA drivers enabled | 4.50 + 4.00 + 3.00 | **11.5 ns** |
| nOE/DIR → V,W drivers enabled | 3.75 + 4.50 + 4.00 + 3.00 | **15.25 ns** |
| C → A | pad 5.25 + pad 16.50 | **21.75 ns** |

Two staggers, both deliberate. The data halves differ by 7.5 ns, and the two
enable chains differ by 3.75 ns because the DIR-high side carries the extra
`t370` inverter. The k1801 notes give the reason for the first: splitting the
moment the output buffers switch, to reduce the current spike on the supply when
sixteen drivers turn on at once.

**A substitute built from two identical '245s does not reproduce this.** Both
bytes then switch together. That is a power-integrity difference, not a logic
one, and the answer is decoupling rather than an artificial delay — see
[DESIGN.md](DESIGN.md).

## Sources

- [1801BM1/k1801](https://github.com/1801BM1/k1801), CC-BY 3.0 — the die
  schematic (`055/sch/055.pdf`), the pin description (`055/readme.md`) and the
  cell library (`lib/rtl/lib_1801.v`), which is vendored here as
  `rtl/lib_1801.v` unmodified. See [THIRD-PARTY.md](../THIRD-PARTY.md).
- The only known machine using this part is the Elektronika MS 0511 (UKNC),
  where it is D22.
