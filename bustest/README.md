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
- **It reports nothing while running.** A chain gives no feedback until the
  image comes back, which is fine for an overnight soak and poor for watching.
  The volume carries `MACRO.SAV`, `LINK.SAV`, `SYSMAC.SML` and `SYSLIB.OBJ` — a
  complete MACRO-11 environment — so a program that generates, writes, reads
  and compares in a loop, printing the failing block, word and bit mask as it
  goes, could be assembled on the machine. That is the better instrument and it
  is not written yet.
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
