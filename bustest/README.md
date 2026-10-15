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
.@MZ1:STRESS
```

Each iteration copies a pattern, compares the copy back, and deletes it — three
passes of the data across the bus per file. **Silence is a pass.** Any
`DIFFERENCES` output at all is a finding.

`--device` sets the volume name baked into the procedure if it does not mount as
`MZ1:`, `--iterations` the number of passes, `--file-blocks` the size of each
pattern.

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
- **`DIFFERENCES/BINARY` does not work on the FODOS 3.0 volume this was tried
  on.** The first run stopped there. It stopped *after* the copy, though, and
  the scratch file it left behind was byte-for-byte identical to `WORST.DAT` —
  so the data is good and only the comparator is missing. See
  [TESTING.md](../docs/TESTING.md#the-worst-case-measured-once).

  The volume in question carries `MACRO.SAV` and `LINK.SAV`, so the fix is to
  assemble the comparison on the machine rather than depend on a utility that
  may not be there.
- **The patterns are proven; the procedure is not.** One pass of `WORST.DAT`
  round-tripped exactly. Nothing has yet run the full soak, and nothing has run
  it hot.

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
