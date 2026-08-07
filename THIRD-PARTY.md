# Third-party material

## 1801BM1/k1801

<https://github.com/1801BM1/k1801> — Copyright (c) 2013–2014 1801BM1@gmail.com,
licensed **Creative Commons Attribution 3.0 (CC-BY 3.0)**.

That project reverse engineered the 1801ВП1 gate arrays from die photographs and
published the results. This repository depends on three pieces of it:

| what | where it is used |
|---|---|
| `lib/rtl/lib_1801.v` — the gate-array cell library, with per-cell delays | **vendored unmodified** as `rtl/lib_1801.v`, original copyright header intact |
| `055/sch/055.pdf` — the die-level schematic of the КР1801ВП1-055 | read, not redistributed; `rtl/vp1_055_orig.v` is a transcription of it |
| `055/readme.md` — the pin description | quoted and cross-checked in `docs/LOGIC.md` |

**Changes made.** `rtl/vp1_055_orig.v` is an adaptation: it is a Verilog
structural netlist written here from the published schematic diagram, which the
original project supplies only as a drawing — there is no RTL for the 055
upstream, and that is consistent with it being a transceiver with nothing to
synthesise. The cell library itself is used as published, with no modification.

`docs/LOGIC.md` reaches one conclusion the upstream text does not state
explicitly: that the part is non-inverting. That is derived here from the cell
semantics in `lib_1801.v` and the pad outputs used in `055.pdf`, and the
derivation is shown so it can be checked. Any error in it is this repository's,
not theirs.

## Everything else

Original work in this repository is MIT licensed — see [LICENSE](LICENSE).
