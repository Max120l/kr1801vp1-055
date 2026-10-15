#!/usr/bin/env python3
"""
Build an RT-11 volume of adversarial bus patterns, for stressing the
КР1801ВП1-055 site (D22) in an MS 0511.

Why patterns and not a memory test.  D22 sits between the inverted MPI AD bus
and the *peripheral* processor's internal bus, so it carries every word the PP
fetches or moves and nothing the central processor does on its own.  A CPU-side
RAM test therefore never touches it -- which onerom-1801re2's CPU-side canary
demonstrated by staying clean for hundreds of passes while the PP died.  The
way to drive traffic through D22 from a program running under FODOS (which runs
on the CP) is disk I/O, because that is what makes the PP work.

Why these patterns.  The one place the substitute knowingly departs from the
original is the delay stagger: the gate array spread its two bytes 7.5 ns apart
so that sixteen output drivers never switched at the same instant, and two
identical '245s switch together.  Nothing in the machine's own ТЕСТИРОВАНИЕ
deliberately produces that worst case.  A file whose words alternate 0000/FFFF
does: every transfer reverses all sixteen lines at once.

(The AD bus is active low, so 0000 in the file is FFFF on the bus.  Irrelevant
for this purpose -- either way all sixteen lines change together.)

The volume is data only and not bootable: boot from your own FODOS system disk
and mount this as a second drive.

Usage:
    make_bustest.py  -o bustest.dsk              # build the image
    make_bustest.py  --self-test                 # prove the checker can fail
"""

import argparse
import contextlib
import datetime
import io
import os
import tempfile
import struct
import sys

BLOCK = 512

# RT-11 on-disk geometry.  Block 0 is the boot block, block 1 the home block,
# 2-5 are reserved, and the directory starts at 6 by convention (the home block
# says so explicitly, but RT-11 only ever puts it there).
HOME_BLOCK = 1
DIR_START = 6
DIR_SEGMENTS = 4                      # 2 blocks each: 6-13
DIR_SEG_BLOCKS = 2
DATA_START = DIR_START + DIR_SEGMENTS * DIR_SEG_BLOCKS

ENTRY_WORDS = 7                       # with zero extra bytes per entry
E_MPTY = 0o1000                       # unused area
E_PERM = 0o2000                       # permanent file
E_EOS = 0o4000                        # end of segment marker

# RADIX-50: space, A-Z, $, ., unused, 0-9.  Three characters per 16-bit word.
R50 = " ABCDEFGHIJKLMNOPQRSTUVWXYZ$.\x00" + "0123456789"


def rad50(s):
    """Encode a 3-character group.  Shorter groups are space padded."""
    s = (s + "   ")[:3]
    v = 0
    for ch in s:
        try:
            v = v * 40 + R50.index(ch.upper())
        except ValueError:
            raise SystemExit(f"character {ch!r} has no RADIX-50 encoding")
    return v


def filename_words(name, ext):
    """RT-11 holds a 6.3 name as three words: two of name, one of type."""
    if len(name) > 6 or len(ext) > 3:
        raise SystemExit("%r.%r does not fit RT-11's 6.3 names; it would be "
                         "silently truncated and then not found" % (name, ext))
    name = (name + "      ")[:6]
    return [rad50(name[:3]), rad50(name[3:]), rad50(ext)]


def rt11_date(d):
    """
    bits 0-4 year-1972, 5-9 day, 10-13 month, 14-15 age.  The age field exists
    because five bits of year ran out in 2003; each unit adds 32 years.
    """
    age, year = divmod(d.year - 1972, 32)
    if age > 3:
        return 0                      # past 2099; a zero date is legal
    return (age << 14) | (d.month << 10) | (d.day << 5) | year


# --------------------------------------------------------------------------
# the patterns
# --------------------------------------------------------------------------

def pat_worst(nwords):
    """All sixteen lines reverse on every word.  The point of this volume."""
    return [0x0000 if i % 2 == 0 else 0xFFFF for i in range(nwords)]


def pat_couple(nwords):
    """Adjacent bits in opposition, then swapped: catches coupling, not timing."""
    return [0x5555 if i % 2 == 0 else 0xAAAA for i in range(nwords)]


def pat_walk(nwords):
    """
    A one walking through sixteen positions, then a zero doing the same.  One
    line changing at a time is the opposite extreme from WORST, and it is what
    finds a single stuck or swapped bit rather than a supply problem.
    """
    out = []
    while len(out) < nwords:
        for b in range(16):
            out.append(1 << b)
        for b in range(16):
            out.append(0xFFFF ^ (1 << b))
    return out[:nwords]


def pat_addrs(nwords):
    """
    Each word carries its own index, so a block that lands in the wrong place
    is visible as such instead of merely as a mismatch.
    """
    return [i & 0xFFFF for i in range(nwords)]


PATTERNS = [
    ("WORST", "DAT", pat_worst,
     "words alternate 0000/FFFF - all sixteen drivers switch together"),
    ("COUPLE", "DAT", pat_couple,
     "words alternate 5555/AAAA - adjacent-bit coupling"),
    ("WALK", "DAT", pat_walk,
     "walking one then walking zero - stuck or swapped bits"),
    ("ADDRS", "DAT", pat_addrs,
     "each word is its own index - misplaced blocks"),
]


def pattern_bytes(fn, blocks):
    nwords = blocks * BLOCK // 2
    return struct.pack("<%dH" % nwords, *fn(nwords))


# --------------------------------------------------------------------------
# the command procedure
# --------------------------------------------------------------------------

def out_name(name):
    """Where a pattern's chain ends up.  Six characters, like everything here."""
    return ("O" + name)[:6]


CHAIN_A, CHAIN_B = "CHAINA", "CHAINB"


def command_file(dev, iterations, names):
    """
    An RT-11 indirect command file that needs no comparator on the machine.

    The first version compared each copy with DIFFERENCES/BINARY, which cannot
    work on a FODOS volume without BINCOM.SAV -- and the one this was built for
    does not have it.  There is no switch for a missing utility.

    So the comparison moves off the machine, and the disk does something a
    missing utility cannot stop it doing: it copies a pattern down a chain.
    Pattern -> A -> B -> A -> B ..., deleting behind itself, and the last link
    is left on the volume.  A corrupted word is copied forward faithfully by
    every subsequent link, so it survives to the end: comparing only the final
    file against the pattern it came from detects an error introduced by ANY
    pass, not just the last.  (A second error flipping the same bit back would
    hide the first.  Two independent single-bit errors landing on the same bit
    of the same word is not a failure mode worth designing around.)

    That buys unlimited soak depth for two files' worth of free space, with no
    dependency on the machine beyond COPY and DELETE -- both of which are
    already proven on this volume, COPY byte-exactly.
    """
    L = [
        "! KR1801VP1-055 bus stress -- GENERATED FILE, do not edit",
        "!",
        "! Boot FODOS, then:   @%sSTRESS" % dev,
        "!",
        "! This prints nothing and checks nothing on the machine: there is no",
        "! BINCOM.SAV here, so DIFFERENCES cannot run.  Instead each pattern is",
        "! copied down a chain of %d links and the last link is kept.  An error" % iterations,
        "! in any link is copied forward by the rest, so it is still there at the",
        "! end.  Hand the image back and the comparison happens off the machine:",
        "!     make_bustest.py --verify-outputs <image>",
        "!",
        "! Expect silence and a long wait.  Anything printed is an error -- most",
        "! likely a full volume, which means fewer links or smaller patterns.",
        "!",
    ]
    for name, ext, _, _ in names:
        src = "%s%s.%s" % (dev, name, ext)
        a = "%s%s.DAT" % (dev, CHAIN_A)
        b = "%s%s.DAT" % (dev, CHAIN_B)
        L.append("! ======== %s.%s down %d links" % (name, ext, iterations))
        L.append("COPY/IMAGE/NOQUERY %s %s" % (src, a))
        for n in range(iterations):
            L.append("COPY/IMAGE/NOQUERY %s %s" % (a, b))
            L.append("DELETE/NOQUERY %s" % a)
            L.append("COPY/IMAGE/NOQUERY %s %s" % (b, a))
            L.append("DELETE/NOQUERY %s" % b)
        L.append("COPY/IMAGE/NOQUERY %s %s%s.DAT" % (a, dev, out_name(name)))
        L.append("DELETE/NOQUERY %s" % a)
    L.append("! ---- done.  Return the image; the outputs carry the verdict.")
    return ("\n".join(L) + "\n").encode("ascii")


def free_blocks(image):
    """Largest contiguous free area the directory knows about, in blocks."""
    first = locate_directory(image, strict=False)
    best, seg_no = 0, 1
    while seg_no:
        base = (first + (seg_no - 1) * DIR_SEG_BLOCKS) * BLOCK
        _t, nxt, _h, extra, _s = struct.unpack_from("<5H", image, base)
        esize = ENTRY_WORDS * 2 + extra
        off = base + 10
        while True:
            (status,) = struct.unpack_from("<H", image, off)
            if status == E_EOS:
                break
            ent = struct.unpack_from("<7H", image, off)
            if status & E_MPTY:
                best = max(best, ent[4])
            off += esize
        seg_no = nxt
    return best


def verify_outputs(path, file_blocks):
    """
    Check the chain outputs on a returned volume against the patterns they came
    from.  This is the comparator the machine does not have.
    """
    with open(path, "rb") as f:
        image = f.read()
    vol = {(n, e): d for n, e, _b, d in read_volume(image, strict=False)}

    found = False
    worst_mask = 0
    for name, ext, fn, _desc in PATTERNS:
        key = (out_name(name), "DAT")
        if key not in vol:
            print("  %-6s -> %-6s  not on the volume (chain did not finish)"
                  % (name, out_name(name)))
            continue
        found = True
        got = vol[key]
        want = pattern_bytes(fn, file_blocks)
        n = min(len(got), len(want))
        bad = [i for i in range(0, n, 2) if got[i:i + 2] != want[i:i + 2]]
        if not bad:
            print("  %-6s -> %-6s  %d words, all correct" % (name, out_name(name), n // 2))
            continue
        mask = 0
        for i in bad:
            wa = struct.unpack_from("<H", want, i)[0]
            wb = struct.unpack_from("<H", got, i)[0]
            mask |= wa ^ wb
        worst_mask |= mask
        print("  %-6s -> %-6s  %d of %d words WRONG"
              % (name, out_name(name), len(bad), n // 2))
        for i in bad[:8]:
            wa = struct.unpack_from("<H", want, i)[0]
            wb = struct.unpack_from("<H", got, i)[0]
            print("      block %4d word %3d  wrote %06o  read %06o  xor %06o"
                  % (i // BLOCK, (i % BLOCK) // 2, wa, wb, wa ^ wb))
        print("      bits ever wrong: %s" % format(mask, "016b"))

    if not found:
        print("no chain outputs at all -- the procedure did not run, or the"
              " volume filled before the first chain completed")
        return 1
    if not worst_mask:
        print("every chain output matches its pattern: no error anywhere in"
              " any link")
        return 0
    lo, hi = worst_mask & 0x00FF, worst_mask & 0xFF00
    print("\nlow byte %s, high byte %s"
          % ("AFFECTED" if lo else "clean", "AFFECTED" if hi else "clean"))
    if lo and not hi:
        print("low byte alone is the V group -- the half the original ran three"
              " gate delays slower, and the signature onerom predicted for the"
              " failing gate array.  On a substitute whose bytes are equally"
              " fast it should not appear.")
    elif hi and lo:
        print("both bytes affected: not the V/W asymmetry.  Sixteen drivers"
              " switching together is the thing this design does differently"
              " from the original -- see the series resistor pack in DESIGN.md.")
    return 1


# --------------------------------------------------------------------------
# the volume
# --------------------------------------------------------------------------

def build(total_blocks, file_blocks, dev, iterations):
    files = []                        # (name, ext, bytes)
    for name, ext, fn, _ in PATTERNS:
        files.append((name, ext, pattern_bytes(fn, file_blocks)))
    files.append(("STRESS", "COM", command_file(dev, iterations, PATTERNS)))

    image = bytearray(b"\x00" * (total_blocks * BLOCK))

    # ---- home block ----
    home = bytearray(BLOCK)
    struct.pack_into("<H", home, 0o700, 1)            # cluster size, always 1
    struct.pack_into("<H", home, 0o702, DIR_START)    # first directory segment
    struct.pack_into("<H", home, 0o704, rad50("V05"))  # "system version"
    home[0o706:0o706 + 12] = b"BUSTEST     "[:12]     # volume id
    home[0o722:0o722 + 12] = b"            "          # owner
    home[0o736:0o736 + 12] = b"DECRT11A    "          # system id, checked by some tools
    # The checksum is the sum of the first 255 words, mod 2^16, stored in the
    # 256th.  RT-11 itself is lax about it; tools that read images are not.
    csum = sum(struct.unpack_from("<255H", home, 0)) & 0xFFFF
    struct.pack_into("<H", home, 0o776, csum)
    image[HOME_BLOCK * BLOCK:(HOME_BLOCK + 1) * BLOCK] = home

    # ---- directory segment 1 ----
    seg = bytearray(DIR_SEG_BLOCKS * BLOCK)
    struct.pack_into("<5H", seg, 0,
                     DIR_SEGMENTS,    # segments allocated
                     0,               # next segment: none
                     1,               # highest segment in use
                     0,               # extra bytes per entry
                     DATA_START)      # first data block described here
    off = 10
    today = rt11_date(datetime.date.today())
    blk = DATA_START
    for name, ext, data in files:
        nblocks = (len(data) + BLOCK - 1) // BLOCK
        w = filename_words(name, ext)
        struct.pack_into("<7H", seg, off,
                         E_PERM, w[0], w[1], w[2], nblocks, 0, today)
        off += ENTRY_WORDS * 2
        image[blk * BLOCK:blk * BLOCK + len(data)] = data
        blk += nblocks

    free = total_blocks - blk
    if free < 0:
        raise SystemExit("volume too small: need %d blocks, have %d"
                         % (blk, total_blocks))
    # One empty entry covering the rest, so the scratch file has somewhere to go.
    struct.pack_into("<7H", seg, off, E_MPTY, 0, 0, 0, free, 0, 0)
    off += ENTRY_WORDS * 2
    struct.pack_into("<H", seg, off, E_EOS)
    off += 2
    if off > DIR_SEG_BLOCKS * BLOCK:
        raise SystemExit("directory segment overflow")

    image[DIR_START * BLOCK:DIR_START * BLOCK + len(seg)] = seg
    return bytes(image), files, free


# --------------------------------------------------------------------------
# reading it back
# --------------------------------------------------------------------------

def seg_plausible(image, blk):
    """Does block `blk` hold something shaped like a directory segment header?"""
    o = blk * BLOCK
    if o + 10 > len(image):
        return False
    tot, nxt, high, extra, start = struct.unpack_from("<5H", image, o)
    return (1 <= tot <= 31 and nxt <= tot and 1 <= high <= tot
            and extra <= 64 and 0 < start < len(image) // BLOCK)


def locate_directory(image, strict=True):
    """
    Find the directory.  The home block is supposed to say where it is, and on a
    DEC-written volume it does.

    FODOS does not fill the home block the same way: the fodos30 volume this was
    tested against has cluster size 0, a directory pointer of 0, a volume ID of
    0x55 filler and a checksum that does not match, yet carries a perfectly
    ordinary RT-11 directory at block 6.  So on a foreign volume, fall back to
    block 6 -- the only place RT-11 ever actually puts it -- and validate by
    reading the segment header rather than by trusting the home block.

    Nothing here ever writes the home block of a volume it did not create. That
    disk boots; its home block is none of this tool's business.
    """
    base = HOME_BLOCK * BLOCK
    (cluster,) = struct.unpack_from("<H", image, base + 0o700)
    (first,) = struct.unpack_from("<H", image, base + 0o702)

    if strict:
        if cluster != 1:
            raise ValueError("cluster size %d, expected 1" % cluster)
        if first != DIR_START:
            raise ValueError("directory at %d, expected %d" % (first, DIR_START))
        want = sum(struct.unpack_from("<255H", image, base)) & 0xFFFF
        (got,) = struct.unpack_from("<H", image, base + 0o776)
        if want != got:
            raise ValueError("home block checksum %06o, computed %06o" % (got, want))
        return first

    if cluster == 1 and 0 < first < len(image) // BLOCK and seg_plausible(image, first):
        return first
    if seg_plausible(image, DIR_START):
        return DIR_START
    raise ValueError("no directory segment at block %d, and the home block does "
                     "not point at one" % DIR_START)


def read_volume(image, strict=True):
    """
    Parse the directory the way a reader would, so the writer is checked
    against something other than itself.  Returns [(name, ext, blocks, data)].
    """
    if len(image) < (DIR_START + DIR_SEG_BLOCKS) * BLOCK:
        raise ValueError("image too short")
    first = locate_directory(image, strict)

    out = []
    seg_no = 1
    while seg_no:
        base = (first + (seg_no - 1) * DIR_SEG_BLOCKS) * BLOCK
        total, nxt, _high, extra, start = struct.unpack_from("<5H", image, base)
        esize = (ENTRY_WORDS * 2) + extra
        off = base + 10
        blk = start
        while True:
            (status,) = struct.unpack_from("<H", image, off)
            if status == E_EOS:
                break
            _s, n0, n1, nx, nblocks, _jc, _date = struct.unpack_from("<7H", image, off)
            if status & E_PERM:
                name = (unrad50(n0) + unrad50(n1)).rstrip()
                ext = unrad50(nx).rstrip()
                data = image[blk * BLOCK:(blk + nblocks) * BLOCK]
                out.append((name, ext, nblocks, data))
            blk += nblocks
            off += esize
            if off > base + DIR_SEG_BLOCKS * BLOCK:
                raise ValueError("ran off the end of segment %d" % seg_no)
        seg_no = nxt
        if seg_no > total:
            raise ValueError("segment chain points past the directory")
    return out


def unrad50(v):
    c = []
    for _ in range(3):
        v, r = divmod(v, 40)
        c.append(R50[r])
    return "".join(reversed(c))


def verify_preserved(original, new):
    """
    Confirm an injection did not disturb the volume it was added to.

    Every file that was on the disk before must still be there, byte for byte,
    and the home block and boot block must be untouched -- that disk boots, and
    a stress test that costs you your system volume is not a good trade.
    """
    problems = []
    if new[:BLOCK] != original[:BLOCK]:
        problems.append("boot block modified")
    if new[BLOCK:2 * BLOCK] != original[BLOCK:2 * BLOCK]:
        problems.append("home block modified")
    try:
        before = read_volume(original, strict=False)
        after = {(n, e): d for n, e, _b, d in read_volume(new, strict=False)}
    except ValueError as exc:
        return ["cannot re-read: %s" % exc]
    for name, ext, _blocks, data in before:
        key = (name, ext)
        if key not in after:
            problems.append("%s.%s lost" % (name, ext))
        elif after[key] != data:
            problems.append("%s.%s content changed" % (name, ext))
    return problems


def check(image, files, expect_ok=True, strict=True):
    """Verify the image parses and every pattern reads back byte for byte."""
    problems = []
    try:
        got = {(n, e): d for n, e, _b, d in read_volume(image, strict)}
    except ValueError as exc:
        problems.append("directory: %s" % exc)
        got = {}
    for name, ext, data in files:
        key = (name, ext)
        if key not in got:
            problems.append("%s.%s missing" % (name, ext))
            continue
        # Files are stored in whole blocks, so compare only what was written.
        if got[key][:len(data)] != data:
            problems.append("%s.%s content differs" % (name, ext))
    if expect_ok:
        for p in problems:
            print("  FAIL  %s" % p)
        return not problems
    return bool(problems)


def inject(image, files, force=False):
    """
    Add the pattern files to an existing RT-11 / FODOS volume, so the test can
    live on a disk that already boots instead of needing a second drive.

    Space comes from the first empty area in the directory that is large
    enough.  Entries are rewritten a whole segment at a time rather than
    shifted in place, because getting that wrong corrupts a disk that has
    something on it worth keeping.
    """
    image = bytearray(image)
    first = locate_directory(image, strict=False)
    if first != DIR_START:
        print("note: directory at block %d, not the usual %d" % (first, DIR_START))

    wanted = {"%s.%s" % (n, e) for n, e, _d in files}
    need = sum((len(d) + BLOCK - 1) // BLOCK for _n, _e, d in files)
    today = rt11_date(datetime.date.today())

    def segments():
        """Walk the segment chain, yielding (base, header, entries)."""
        seg_no, seen = 1, set()
        while seg_no:
            if seg_no in seen:
                raise SystemExit("directory segment chain loops at %d" % seg_no)
            seen.add(seg_no)
            base = (first + (seg_no - 1) * DIR_SEG_BLOCKS) * BLOCK
            hdr = list(struct.unpack_from("<5H", image, base))
            esize = ENTRY_WORDS * 2 + hdr[3]
            ents, off, blk = [], base + 10, hdr[4]
            while True:
                if off + 2 > base + DIR_SEG_BLOCKS * BLOCK:
                    raise SystemExit("segment %d has no end marker" % seg_no)
                (status,) = struct.unpack_from("<H", image, off)
                if status == E_EOS:
                    break
                ent = list(struct.unpack_from("<%dH" % (esize // 2), image, off))
                ents.append((off, ent, blk))
                blk += ent[4]
                off += esize
            yield base, hdr, esize, ents
            seg_no = hdr[1]

    # First sweep: names already present.  Clearing a collision only rewrites a
    # status word, so it needs no shifting and cannot move anything else.
    clashes = []
    for _base, _hdr, _esize, ents in segments():
        for off, ent, _blk in ents:
            if not ent[0] & E_PERM:
                continue
            nm = (unrad50(ent[1]) + unrad50(ent[2])).rstrip()
            ex = unrad50(ent[3]).rstrip()
            if "%s.%s" % (nm, ex) in wanted:
                clashes.append((off, "%s.%s" % (nm, ex)))
    if clashes and not force:
        raise SystemExit("already on the volume: %s\n(use --force to replace)"
                         % ", ".join(n for _o, n in clashes))
    for off, _n in clashes:
        struct.pack_into("<H", image, off, E_MPTY)

    # Second sweep: place the files in the first empty area that fits.
    for base, hdr, esize, ents in segments():
        for idx, (_off, ent, eblk) in enumerate(ents):
            if not (ent[0] & E_MPTY and ent[4] >= need):
                continue
            rebuilt = []
            for j, (_o, e, _b) in enumerate(ents):
                if j != idx:
                    rebuilt.append(e)
                    continue
                cur = eblk
                for name, ext, data in files:
                    nb = (len(data) + BLOCK - 1) // BLOCK
                    w = filename_words(name, ext)
                    e2 = [E_PERM, w[0], w[1], w[2], nb, 0, today]
                    e2 += [0] * (esize // 2 - ENTRY_WORDS)
                    rebuilt.append(e2)
                    image[cur * BLOCK:cur * BLOCK + len(data)] = data
                    tail = nb * BLOCK - len(data)
                    if tail:
                        image[cur * BLOCK + len(data):(cur + nb) * BLOCK] = b"\x00" * tail
                    cur += nb
                if ent[4] - need:
                    rest = [E_MPTY, 0, 0, 0, ent[4] - need, 0, 0]
                    rest += [0] * (esize // 2 - ENTRY_WORDS)
                    rebuilt.append(rest)
            size = 10 + len(rebuilt) * esize + 2
            if size > DIR_SEG_BLOCKS * BLOCK:
                raise SystemExit("no room for %d more entries in the directory "
                                 "segment; squeeze the volume first" % len(files))
            seg = bytearray(DIR_SEG_BLOCKS * BLOCK)
            struct.pack_into("<5H", seg, 0, *hdr)
            o = 10
            for e in rebuilt:
                struct.pack_into("<%dH" % (esize // 2), seg, o, *e)
                o += esize
            struct.pack_into("<H", seg, o, E_EOS)
            image[base:base + len(seg)] = seg
            return bytes(image)

    raise SystemExit("no single free area of %d blocks (%d KB) on the volume"
                     % (need, need * BLOCK // 1024))


def looks_like_text(data):
    sample = data[:4096]
    if not sample:
        return False
    printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13))
    return printable / len(sample) > 0.85


def list_volume(path, dump=True):
    """
    List what is on a volume and print anything that reads as text.

    This exists for the return trip: after a run, the interesting content is
    whatever the machine wrote -- BINCOM's .DIF listings above all -- and
    reading them off the image beats transcribing them off a screen.
    """
    with open(path, "rb") as f:
        image = f.read()
    print("%s: %d blocks" % (path, len(image) // BLOCK))
    files = read_volume(image, strict=False)
    for name, ext, blocks, data in files:
        kind = "text" if looks_like_text(data) else "binary"
        print("  %-6s.%-3s %5d blocks  %s" % (name, ext, blocks, kind))
    if not dump:
        return files
    for name, ext, _blocks, data in files:
        if ext in ("DIF", "LST", "LOG") or (ext == "COM" and name != "STRESS"):
            text = data.rstrip(b"\x00").decode("ascii", "replace")
            print("\n==== %s.%s ====" % (name, ext))
            print(text.rstrip() or "(empty)")
    return files


def compare_volumes(old_path, new_path):
    """
    Name what changed between two images of the same volume.  After a run this
    is the whole story: files added are what the machine produced, files
    changed are what it rewrote.
    """
    with open(old_path, "rb") as f:
        old = {(n, e): d for n, e, _b, d in read_volume(f.read(), strict=False)}
    with open(new_path, "rb") as f:
        newimg = f.read()
    new = {(n, e): d for n, e, _b, d in read_volume(newimg, strict=False)}

    added = [k for k in new if k not in old]
    gone = [k for k in old if k not in new]
    changed = [k for k in new if k in old and new[k] != old[k]]

    print("added:   %s" % (", ".join("%s.%s" % k for k in added) or "none"))
    print("removed: %s" % (", ".join("%s.%s" % k for k in gone) or "none"))
    print("changed: %s" % (", ".join("%s.%s" % k for k in changed) or "none"))

    # A pattern file that changed is the headline: it means the data on the
    # disk no longer matches what was written to it.
    patterns = {(n, e) for n, e, _f, _d in PATTERNS}
    for key in changed:
        if key not in patterns:
            continue
        a, b = old[key], new[key]
        bad = [i for i in range(0, min(len(a), len(b)), 2) if a[i:i+2] != b[i:i+2]]
        print("\n!! %s.%s differs on disk, %d words" % (key[0], key[1], len(bad)))
        for i in bad[:12]:
            wa = struct.unpack_from("<H", a, i)[0]
            wb = struct.unpack_from("<H", b, i)[0]
            print("   block %4d word %3d  wrote %06o  read %06o  xor %06o"
                  % (i // BLOCK, (i % BLOCK) // 2, wa, wb, wa ^ wb))
        if bad:
            xors = {struct.unpack_from("<H", a, i)[0] ^ struct.unpack_from("<H", b, i)[0]
                    for i in bad}
            mask = 0
            for x in xors:
                mask |= x
            print("   bits ever wrong: %016s" % format(mask, "016b"))
            print("   low byte %s, high byte %s"
                  % ("affected" if mask & 0x00FF else "clean",
                     "affected" if mask & 0xFF00 else "clean"))

    for key in added:
        if looks_like_text(new[key]):
            print("\n==== %s.%s ====" % key)
            print(new[key].rstrip(b"\x00").decode("ascii", "replace").rstrip())


def self_test():
    """
    A checker that cannot fail proves nothing -- the same argument `make
    mutants` makes for the equivalence testbench.  Build a volume, confirm it
    reads back clean, then break it three ways and confirm each is caught.
    """
    image, files, _free = build(1600, 8, "MZ1:", 2)
    ok = True

    print("clean image")
    if check(image, files):
        print("  reads back clean")
    else:
        ok = False

    cases = []

    bad = bytearray(image)                       # one flipped data bit
    off = (DATA_START * BLOCK) + 3
    bad[off] ^= 0x08
    cases.append(("one flipped bit in WORST.DAT", bytes(bad)))

    bad = bytearray(image)                       # corrupted home checksum
    struct.pack_into("<H", bad, HOME_BLOCK * BLOCK + 0o776, 0o123456)
    cases.append(("home block checksum wrong", bytes(bad)))

    bad = bytearray(image)                       # directory moved
    struct.pack_into("<H", bad, HOME_BLOCK * BLOCK + 0o702, 9)
    cases.append(("directory start wrong", bytes(bad)))

    for label, broken in cases:
        if check(broken, files, expect_ok=False):
            print("  caught      %s" % label)
        else:
            print("  NOT CAUGHT  %s" % label)
            ok = False

    # The chain outputs are checked off-machine, so that comparator needs the
    # same treatment: a clean run must verify, and a single flipped bit must not.
    print("chain verification")
    outs = [(out_name(n), "DAT", pattern_bytes(fn, 8)) for n, _e, fn, _d in PATTERNS]
    done = inject(image, outs)
    def verify(img):
        fd, path = tempfile.mkstemp(suffix=".dsk")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(img)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = verify_outputs(path, 8)
            return rc, buf.getvalue()
        finally:
            os.unlink(path)

    rc, text = verify(done)
    if rc == 0 and "no error anywhere" in text:
        print("  a clean chain verifies")
    else:
        print("  FAIL  a clean chain did not verify:\n%s" % text)
        ok = False

    broken = bytearray(done)
    # find OWORST.DAT on the volume and flip one bit in it
    first = locate_directory(broken, strict=False)
    base = first * BLOCK
    _t, _n, _h, extra, start = struct.unpack_from("<5H", broken, base)
    esize = ENTRY_WORDS * 2 + extra
    off, blk = base + 10, start
    target = None
    while True:
        (st,) = struct.unpack_from("<H", broken, off)
        if st == E_EOS:
            break
        e = struct.unpack_from("<7H", broken, off)
        nm = (unrad50(e[1]) + unrad50(e[2])).rstrip()
        if st & E_PERM and nm == out_name("WORST"):
            target = blk
            break
        blk += e[4]; off += esize
    if target is None:
        print("  FAIL  could not find %s.DAT to corrupt" % out_name("WORST"))
        ok = False
    else:
        broken[target * BLOCK + 40] ^= 0x01
        rc, text = verify(bytes(broken))
        if rc != 0 and "WRONG" in text:
            print("  caught      one flipped bit in a chain output")
        else:
            print("  NOT CAUGHT  a flipped bit in a chain output")
            ok = False

    print("all mutants caught" if ok else "self-test FAILED")
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-o", "--output", default="bustest.dsk")
    p.add_argument("--blocks", type=int, default=1600,
                   help="volume size in 512-byte blocks "
                        "(default 1600 = 800 KB, the 80x2x10 MZ floppy)")
    p.add_argument("--file-blocks", type=int, default=100,
                   help="blocks per pattern file (default 100 = 50 KB)")
    p.add_argument("--device", default="MZ1:",
                   help="how FODOS will name this volume (default MZ1:)")
    p.add_argument("--iterations", type=int, default=50,
                   help="chain links per pattern (default 50); each link is "
                        "two copies, so two reads and two writes of the file")
    p.add_argument("--self-test", action="store_true",
                   help="check the checker instead of building an image")
    p.add_argument("--inject", metavar="IMAGE",
                   help="add the files to an existing FODOS/RT-11 image "
                        "instead of building a fresh data volume")
    p.add_argument("--force", action="store_true",
                   help="with --inject, replace files of the same name")
    p.add_argument("--list", metavar="IMAGE", dest="list_image",
                   help="list a volume's files and print any that read as text")
    p.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                   help="name what changed between two images of a volume")
    p.add_argument("--verify-outputs", metavar="IMAGE", dest="verify_image",
                   help="check a returned volume's chain outputs against the "
                        "patterns they came from -- this is the comparator the "
                        "machine does not have")
    a = p.parse_args()

    if a.verify_image:
        return verify_outputs(a.verify_image, a.file_blocks)

    if a.list_image:
        list_volume(a.list_image)
        return 0

    if a.compare:
        compare_volumes(a.compare[0], a.compare[1])
        return 0

    if a.self_test:
        return self_test()

    if a.inject:
        with open(a.inject, "rb") as f:
            original = f.read()
        files = [(n, e, pattern_bytes(fn, a.file_blocks))
                 for n, e, fn, _d in PATTERNS]
        files.append(("STRESS", "COM",
                      command_file(a.device, a.iterations, PATTERNS)))
        image = inject(original, files, force=a.force)
        if not check(image, files, strict=False):
            raise SystemExit("refusing to write an image that does not read back")
        if len(image) != len(original):
            raise SystemExit("internal error: image size changed")
        kept = verify_preserved(original, image)
        if kept and not a.force:
            for p in kept:
                print("  FAIL  %s" % p)
            raise SystemExit("refusing to write: the original volume was disturbed")
        with open(a.output, "wb") as f:
            f.write(image)
        n_before = len(read_volume(original, strict=False))
        print("%s: %s with the test added (%d blocks, unchanged size)"
              % (a.output, a.inject, len(image) // BLOCK))
        print("  %d files already there, all intact; boot and home blocks untouched"
              % n_before)
        for name, ext, data in files:
            print("  %-6s.%-3s %4d blocks" % (name, ext,
                                              (len(data) + BLOCK - 1) // BLOCK))
        # The chain needs room at run time that injection does not reserve:
        # two live chain files plus one kept output per pattern.
        runtime = a.file_blocks * (2 + len(PATTERNS))
        spare = free_blocks(image)
        print("  free after injection: %d blocks; the chain needs %d at its peak"
              % (spare, runtime))
        if spare < runtime:
            print("  WARNING: not enough room.  Re-run with --file-blocks %d"
                  % (spare // (2 + len(PATTERNS))))
        print("boot it and run @%sSTRESS  (adjust %s if it mounts elsewhere)"
              % (a.device, a.device))
        print("then hand the image back:  --verify-outputs <image>")
        return 0

    image, files, free = build(a.blocks, a.file_blocks, a.device, a.iterations)
    if not check(image, files):
        raise SystemExit("refusing to write an image that does not read back")

    with open(a.output, "wb") as f:
        f.write(image)

    print("%s: %d blocks (%d KB)" % (a.output, a.blocks, a.blocks * BLOCK // 1024))
    for name, ext, data in files:
        nb = (len(data) + BLOCK - 1) // BLOCK
        note = dict((n, d) for n, _e, _f, d in PATTERNS).get(name, "the procedure")
        print("  %-7s.%-3s %4d blocks  %s" % (name, ext, nb, note))
    print("  %d blocks free (SCRTCH.DAT needs %d)" % (free, a.file_blocks))
    print("mount as %s and run @%sSTRESS" % (a.device, a.device))
    return 0


if __name__ == "__main__":
    sys.exit(main())
