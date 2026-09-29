#!/usr/bin/env python3
"""Generate the KR1801VP1-055 replacement adapter as a KiCad board.

Two 74AHCT245 + one 74AHCT125 (TSSOP) on top, a 42-pin field underneath in
the geometry of the original's four-row through-hole site.  Run with the
KiCad 7 python (pcbnew).  Then: export DSN, autoroute with Freerouting,
import SES, DRC, gerbers - see run.sh.

Site geometry measured on the machine (see README).
"""
import math, sys
import pcbnew
from pcbnew import VECTOR2I_MM as MM

# ---------------------------------------------------------------- geometry
G = dict(               # measured on the MS 0511 board, September 2026
    n_side=21,          # pins per side (42 total)
    pitch=1.25,         # along the side, consecutive pin numbers (each row has 2.5 mm pitch)
    row_offset=2.5,     # inner row to outer row, same side
    side_outer=25.0,    # outer row to outer row across the package
    hole=1.0,           # drill: 0.5 mm square pins, machined receptacles fit
    pad=1.7,            # annular pad diameter
    first_outer=False,  # pin 1 (dimple corner, top-left) sits in the INNER row
    margin=3.0,         # board edge beyond the outer rows / end pins
)
REV = "C"
# numbering: pins 1..21 run down the LEFT side (top to bottom), alternating
# rows; pins 22..42 run UP the right side (DIP-like).
# The two sides are TRANSLATED copies, not mirror images.  Counted on the
# socketed site with pin 1 top-left, the rows read 10-11-10-11 from left to
# right: the 11-pin row (the one reaching the end positions) is the INNER row
# on the pin-1 side and the OUTER row on the pin-22 side.  So pins 1 and 21
# are inboard, pins 22 and 42 outboard.
# Rev A had 11-10-10-11 (mirrored), rev B 11-10-11-10 (right idea, wrong
# parity); neither fits.

TRACK = 0.2    # mm
CLEAR = 0.15
VIA = 0.7      # 0.2 mm annular ring on a 0.3 drill
VIA_DRILL = 0.3

# --------------------------------------------------------------- pin map
# original pin -> net name (k1801 project's pin description)
PIN = {}
for i in range(8):  PIN[1 + i] = f"V{i}"
for i in range(8):  PIN[9 + i] = f"W{i}"
for i in range(3):  PIN[17 + i] = f"A{i}"
PIN[20] = "DIR"; PIN[21] = "GND"
for i in range(16): PIN[22 + i] = f"nA{i}"
for i in range(3):  PIN[38 + i] = f"C{i}"
PIN[41] = "nOE"; PIN[42] = "VCC"

# 74AHCT245 (TSSOP-20): 1 DIR, 2-9 A1..A8, 10 GND, 11-18 B8..B1, 19 /OE, 20 VCC
def u245(base_nA, base_B):
    m = {1: "DIR", 10: "GND", 19: "nOE", 20: "VCC"}
    for i in range(8):
        m[2 + i] = f"nA{base_nA + i}"        # A side <- bus (nA)
        m[18 - i] = f"{base_B}{i}"           # B side <- V/W
    return m

# 74AHCT125 (TSSOP-14): 1 /1OE 2 1A 3 1Y, 4 /2OE 5 2A 6 2Y, 7 GND, 8 3Y 9 3A 10 /3OE, 11 4Y 12 4A 13 /4OE, 14 VCC
U125 = {1: "GND", 2: "C0", 3: "A0", 4: "GND", 5: "C1", 6: "A1", 7: "GND",
        8: "A2", 9: "C2", 10: "GND", 11: None, 12: "GND", 13: "GND", 14: "VCC"}

LIB_SO = "/usr/share/kicad/footprints/Package_SO.pretty"
LIB_C = "/usr/share/kicad/footprints/Capacitor_SMD.pretty"


def pin_xy(n):
    """Position (mm) of original pin n, board centred on the site."""
    s = G["n_side"]; p = G["pitch"]
    half_len = (s - 1) * p / 2
    if n <= s:                       # left side, top to bottom
        k = n - 1; x_sign = -1
        outer = (k % 2 == 0) == G["first_outer"]
    else:                            # right side, bottom to top
        k = (s - 1) - (n - s - 1); x_sign = 1
        outer = (k % 2 == 0) != G["first_outer"]     # translated copy, not mirrored
    y = -half_len + k * p
    x = x_sign * (G["side_outer"] / 2 - (0 if outer else G["row_offset"]))
    return x, y


def main(out="adapter.kicad_pcb"):
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = pcbnew.FromMM(TRACK)
    ds.m_ViasMinSize = pcbnew.FromMM(VIA)
    ds.m_MinThroughDrill = pcbnew.FromMM(VIA_DRILL)
    ds.m_MinClearance = pcbnew.FromMM(CLEAR)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetTrackWidth(pcbnew.FromMM(TRACK)); nc.SetClearance(pcbnew.FromMM(CLEAR))
    nc.SetViaDiameter(pcbnew.FromMM(VIA)); nc.SetViaDrill(pcbnew.FromMM(VIA_DRILL))

    nets = {}
    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
        return nets[name]
    for name in list(PIN.values()):
        net(name)

    # --- the 42-pin field (its own footprint, J1) ---
    j1 = pcbnew.FOOTPRINT(board); j1.SetReference("J1"); j1.SetValue("VP1-055 site")
    j1.SetFPID(pcbnew.LIB_ID("adapter", "VP1-055_site"))
    for n in range(1, 43):
        pad = pcbnew.PAD(j1)
        pad.SetNumber(str(n)); pad.SetName(str(n))
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE if n != 1 else pcbnew.PAD_SHAPE_RECT)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetSize(MM(G["pad"], G["pad"])); pad.SetDrillSize(MM(G["hole"], G["hole"]))
        pad.SetLayerSet(pad.PTHMask())
        x, y = pin_xy(n); pad.SetPosition(MM(x, y)); pad.SetPos0(MM(x, y))
        pad.SetNet(net(PIN[n]))
        j1.Add(pad)
    board.Add(j1)
    j1.SetPosition(MM(0, 0))
    j1.Reference().SetVisible(False); j1.Value().SetVisible(False)

    # --- ICs and caps on top, in the clear lane between the inner rows ---
    inner = G["side_outer"] / 2 - G["row_offset"]          # inner row x
    lane = 2 * inner - 2 * G["pad"] / 2 - 0.6                  # usable width between inner pads
    print(f"lane between inner rows: {lane:.2f} mm wide")
    def place(ref, value, lib, name, x, y, rot, pinmap):
        fp = pcbnew.FootprintLoad(lib, name)
        fp.SetReference(ref); fp.SetValue(value)
        board.Add(fp)
        fp.SetPosition(MM(x, y)); fp.SetOrientationDegrees(rot)
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
        for num, nn in pinmap.items():
            if nn: fp.FindPadByNumber(str(num)).SetNet(net(nn))
        return fp
    tssop20 = "TSSOP-20_4.4x6.5mm_P0.65mm"; tssop14 = "TSSOP-14_4.4x5mm_P0.65mm"
    L = (G["n_side"] - 1) * G["pitch"]                          # site length
    # one column, rotated so the A side (nA bus, pins 2-9) faces the right-hand
    # pin rows (nA on pins 22-37) and the B side faces V/W on the left
    dy = float(__import__("os").environ.get("NUDGE", "0"))   # placement variant for the router
    place("U1", "74AHCT245", LIB_SO, tssop20, 0, -6.6 - dy, 180, u245(0, "V"))
    place("U2", "74AHCT245", LIB_SO, tssop20, 0, 0.6 + dy, 180, u245(8, "W"))
    place("U3", "74AHCT125", LIB_SO, tssop14, 0, 7.0 + dy, 180, U125)
    cap = "C_0603_1608Metric"
    # each 100n sits in the left lane next to its chip's VCC pin (pin 20 / 14,
    # which the 180-degree rotation puts at the chip's bottom-left corner)
    for ref, x, y in (("C1", -6.0, -6.6 - dy), ("C2", -6.0, 0.6 + dy), ("C3", -6.0, 7.0 + dy)):
        place(ref, "100n", LIB_C, cap, x, y, 90, {1: "VCC", 2: "GND"})
    place("C4", "10u", LIB_C, "C_0805_2012Metric", 0, 11.2, 0, {1: "VCC", 2: "GND"})

    # --- outline ---
    w = G["side_outer"] + 2 * G["margin"]; h = L + 2 * G["margin"] + 1.0
    def line(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(MM(x1, y1)); s.SetEnd(MM(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.1)); board.Add(s)
    line(-w/2, -h/2, w/2, -h/2); line(w/2, -h/2, w/2, h/2)
    line(w/2, h/2, -w/2, h/2); line(-w/2, h/2, -w/2, -h/2)
    print(f"board {w:.1f} x {h:.1f} mm, site {G['side_outer']:.1f} x {L:.1f} mm")
    # silk: board label in the bottom margin, pin-1 marker at the dimple corner
    def text(txt, x, y, size, layer, angle=0):
        t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetPosition(MM(x, y))
        t.SetTextSize(MM(size, size)); t.SetTextThickness(pcbnew.FromMM(0.15))
        t.SetLayer(layer); t.SetTextAngleDegrees(angle); board.Add(t)
    text("VP1-055 ADAPTER", 0, h / 2 - 1.3, 1.0, pcbnew.F_SilkS)
    text("REV " + REV, 0, -h / 2 + 1.3, 1.0, pcbnew.F_SilkS)
    x1, y1 = pin_xy(1)
    text("1", x1, y1 - 1.6, 1.0, pcbnew.F_SilkS)        # directly above pin 1
    t = pcbnew.PCB_TEXT(board); t.SetText("REV " + REV); t.SetPosition(MM(0, -h / 2 + 1.3))
    t.SetTextSize(MM(1.0, 1.0)); t.SetTextThickness(pcbnew.FromMM(0.15))
    t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True); board.Add(t)
    for i, line in enumerate(("U1 U2 74AHCT245", "U3 74AHCT125", "C1-C3 100n  C4 10u")):
        t = pcbnew.PCB_TEXT(board); t.SetText(line); t.SetPosition(MM(0, -3.0 + 2.0 * i))
        t.SetTextSize(MM(1.0, 1.0)); t.SetTextThickness(pcbnew.FromMM(0.15))
        t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True); board.Add(t)

    board.Save(out)
    print("wrote", out)


if __name__ == "__main__":
    main(*sys.argv[1:])
