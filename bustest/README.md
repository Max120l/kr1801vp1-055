# A bus stress test for the D22 site

The machine's own ТЕСТИРОВАНИЕ passes fourteen times over with the substitute
fitted, which says the replacement works. It does not say anything about the one
place this design knowingly differs from the original.

The gate array staggers its two bytes by 7.5 ns so that sixteen output drivers
never switch at the same instant. Two identical '245s switch together. That is a
supply-current difference rather than a logic one, and the answer in
[DESIGN.md](../docs/DESIGN.md#the-lost-asymmetry) is decoupling — but ТЕСТИРОВАНИЕ
chooses its own data and may never once produce the worst case. This volume
produces it deliberately.

## Why it has to go through the disk

D22 sits between the inverted MPI AD bus and the **peripheral** processor's
internal bus, so it carries every word the PP fetches or moves and nothing the
central processor does on its own. FODOS runs on the CP. A CPU-side memory test
therefore never touches this chip — which onerom-1801re2's CPU-side canary
demonstrated the hard way, staying clean for hundreds of passes while the PP
died hot.

Disk I/O is what makes the PP work, so disk I/O is the vehicle.

## The patterns

| file | words | what it is for |
|---|---|---|
| `WORST.DAT` | `0000`/`FFFF` alternating | all sixteen lines reverse on every word — the case the stagger existed to spread |
| `COUPLE.DAT` | `5555`/`AAAA` alternating | adjacent bits in opposition, then swapped: coupling rather than timing |
| `WALK.DAT` | walking one, then walking zero | one line changing at a time — the opposite extreme, and what finds a single stuck or swapped bit |
| `ADDRS.DAT` | each word is its own index | a block that lands in the wrong place reads as such, not merely as a mismatch |

The AD bus is active low, so `0000` in the file is `FFFF` on the bus. That makes
no difference here: either way all sixteen lines change together.

## Running it

```console
$ python3 make_bustest.py -o bustest.dsk          # a standalone data volume
$ python3 make_bustest.py --inject fodos.dsk -o fodos-test.dsk
```

The first builds an 800 KB data-only volume (80 × 2 × 10, the MZ floppy) to
mount as a second drive. It is **not bootable** — boot your own FODOS system
disk. The second adds the same files to a volume that already boots, taking
space from the first free area large enough and leaving the image byte-size
unchanged.

Then, on the machine:

```
.@MZ0:STRESS
```

It prints nothing and checks nothing locally, because the machine has no
comparator — see below. Each pattern is copied down a chain of links and the
last link is kept. Hand the image back and the comparison happens here:

```console
$ python3 make_bustest.py --verify-outputs fodos-after.dsk --file-blocks 80
  WORST  -> OWORST  20480 words, all correct
  COUPLE -> OCOUPL  20480 words, all correct
  WALK   -> OWALK   20480 words, all correct
  ADDRS  -> OADDRS  20480 words, all correct
every chain output matches its pattern: no error anywhere in any link
```

`--device` sets the volume name baked into the procedure, `--iterations` the
chain depth, `--file-blocks` the size of each pattern. Pass the same
`--file-blocks` to `--verify-outputs` that you passed when building, since that
is how the expected pattern is regenerated.

## Why a chain, and why the comparison is off-machine

The first version compared each copy on the spot with `DIFFERENCES/BINARY`. That
cannot work on the volume this was built for: `?KMON-F-File not found
SY:BINCOM.SAV`. RT-11's binary compare lives in `BINCOM.SAV` and FODOS 3.0 does
not ship it, so no switch helps.

So the comparison moved off the machine, and the disk does something a missing
utility cannot stop it doing — it copies:

```
pattern -> A -> B -> A -> B -> ...        (deleting behind itself)
```

A corrupted word is copied forward faithfully by every subsequent link, so **an
error introduced by any link is still present in the last one.** Comparing only
the final file against its pattern therefore detects corruption from any pass,
not just the most recent. That buys unlimited soak depth for two files' worth of
free space, with no machine-side dependency beyond `COPY` and `DELETE` — both
already proven on this volume, `COPY` byte-exactly.

The one blind spot is a second error flipping the same bit of the same word
back. Two independent single-bit errors colliding like that is not a failure
mode worth designing around.

## Reading a failure

Note *which bits* differ, not just that something did. The original's V group
ran three gate delays where W ran one, so onerom's analysis predicted the **low
byte would fail before the high byte** as delays stretched with temperature. The
substitute makes both bytes about equally fast, so that asymmetry should now be
*absent*. Low-byte-only errors would mean something about this design still
reproduces the original's weakness; errors spread evenly across sixteen bits
point at the supply transient instead, and the fix for that is
[the series resistor pack](../docs/DESIGN.md#the-lost-asymmetry), not a logic
change.

## What it does not do

- **It cannot force nOE**, so it says nothing about the high-Z release timing
  that [DESIGN.md](../docs/DESIGN.md#timing) flags as the remaining un-analysed
  risk. That one needs a scope.
- **The chain reports nothing while running**, which is fine for an overnight
  soak and poor for watching. [`BUSTST.MAC`](BUSTST.MAC) is the answer to that;
  see below.
- **A floppy error and a bus error look alike.** Anything this finds is
  corruption somewhere between the disk surface and memory; D22 is the most
  interesting suspect but not the only one.
- **The patterns are proven; the full soak is not.** One pass of `WORST.DAT`
  round-tripped exactly — see
  [TESTING.md](../docs/TESTING.md#the-worst-case-measured-once). Nothing has yet
  run the chain to completion, and nothing has run it hot.

## Checking the checker

A test that cannot fail proves nothing, which is the argument `make mutants`
makes for the equivalence testbench. The same applies to a disk image written by
code that was never run against the real thing:

```console
$ python3 make_bustest.py --self-test
clean image
  reads back clean
  caught      one flipped bit in WORST.DAT
  caught      home block checksum wrong
  caught      directory start wrong
all mutants caught
```

The volume is parsed back through an independent reader rather than compared
against the writer's own idea of what it wrote, and three deliberate corruptions
confirm that reader notices. This caught a real bug on its first run: `BUSTEST`
is seven characters, RT-11 names are six, and the name was being silently
truncated to `BUSTES` — so the file would have been written and then not found
by the procedure that referenced it. Names are now rejected rather than trimmed.


# BUSTST.MAC — the same test, on the machine

The chain works but it is a blunt instrument: no feedback until the image comes
back, and a verdict rather than a diagnosis. The FODOS volume carries
`MACRO.SAV`, `LINK.SAV`, `SYSMAC.SML` and `SYSLIB.OBJ` — a complete MACRO-11
environment — so the test can simply run there instead.

`BUSTST.MAC` is injected onto the volume along with the patterns, converted to
CR/LF on the way in — RT-11 text files are CR/LF terminated and MACRO would
otherwise see one enormous line. So it is already there:

```
.MACRO BUSTST
.LINK BUSTST
.RUN BUSTST
```

Assembly needs about 60 blocks for the `.OBJ`, the `.SAV` and the scratch file.
The `.SAV` is large for what it does — some 34 blocks — because the two
comparison buffers are 8 KB each and live in the image.

It generates each pattern in memory, writes 16 blocks, reads them back into a
second buffer, and compares word by word. Both directions cross the bus, so both
are part of the test. One line per pass:

```
BUSTST - KR1801VP1-055 bus stress. Stop with CTRL-C.
PASS 000001 ERRS 000000
PASS 000002 ERRS 000000
```

and on a bad word, immediately:

```
ERR W BLK 000013 WRD 000101 EXP 177777 GOT 177737 XOR 000040
```

`EXP`/`GOT`/`XOR` are the point. The `XOR` column names the bits that went
wrong, and the letter after `ERR` says which pattern (`W`orst, `C`ouple, wal`K`,
`A`ddrs). Low byte alone means the V group — the half the original ran three
gate delays slower, and the signature predicted for the *failing* gate array. A
substitute whose bytes are equally fast should not show it. Bits spread across
all sixteen point at the supply transient instead.

Detail lines are capped at eight per pattern per pass so a wholly corrupt buffer
cannot print four thousand of them; `ERRS` still counts every bad word, so the
pass total is always the true figure.

Stop it with CTRL-C. The scratch file is deliberately never closed, so RT-11
discards it on exit and the volume is left exactly as it was found.

## How much of it is checked

**Not assembled, not run** — there is no UKNC and no FODOS here, and no MACRO-11
cross-assembler either. If MACRO rejects a line, the line is wrong.

What *is* checked is the part most likely to be subtly wrong, by re-implementing
each routine in Python exactly as the assembly does it:

| routine | checked |
|---|---|
| `PUTOCT` | exhaustively, all 65536 values, against `%06o` |
| the `BIC`/`BIS` xor | against `^` over a sweep of operand pairs |
| `SWAB`+mask block/word split | exhaustively, all 65536 indices |
| the four generators | lengths, and that `WORST` really reverses all sixteen lines on every transition |

Two bugs were caught this way before it shipped. The report routine read its
expected value from `4(SP)` when five pushed registers put it at `2(SP)`, so
every error line would have printed a saved register instead of the data. And
`XOR (SP),R0` is not a legal form — the PDP-11's `XOR` takes its source from a
register — so that line would not have assembled at all; it is now built from
`BIC` and `BIS`, which also drops any dependency on `XOR` existing on this CPU.
A third, cosmetic: the banner's `CTRL/C` contained the `.ASCIZ` delimiter and
would have truncated the string.
