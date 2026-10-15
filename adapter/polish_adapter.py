#!/usr/bin/env python3
"""Post-route polish: wider power traces where clearance allows, GND pours on
both layers, DRC.  Runs on the routed board in place.

    python3 polish_adapter.py adapter_routed.kicad_pcb
"""
import re, sys, collections
import pcbnew
from build_adapter import TRACK, CLEAR, VIA, VIA_DRILL

POWER_WIDTH = 0.3      # mm, VCC/GND where the neighbours allow it
POUR_CLEAR = 0.2       # mm, pour to other copper
POUR_MIN = 0.25        # mm, thinnest pour sliver kept
POUR_INSET = 0.5       # mm, pour edge inside the board edge


def rules(b):
    ds = b.GetDesignSettings()
    ds.m_TrackMinWidth = pcbnew.FromMM(TRACK); ds.m_MinClearance = pcbnew.FromMM(CLEAR)
    ds.m_ViasMinSize = pcbnew.FromMM(VIA); ds.m_MinThroughDrill = pcbnew.FromMM(VIA_DRILL)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetTrackWidth(pcbnew.FromMM(TRACK)); nc.SetClearance(pcbnew.FromMM(CLEAR))
    nc.SetViaDiameter(pcbnew.FromMM(VIA)); nc.SetViaDrill(pcbnew.FromMM(VIA_DRILL))


def drc(b, tag):
    pcbnew.WriteDRCReport(b, "drc.rpt", pcbnew.EDA_UNITS_MILLIMETRES, True)
    r = open("drc.rpt").read()
    c = collections.Counter(l.split(":")[0] for l in r.splitlines() if l.startswith("[") and "lib_footprint" not in l)
    print(tag, "->", dict(c) or "clean;", [l for l in r.splitlines() if "unconnected pads" in l][0].strip("* "))
    return r, c


def main(path):
    b = pcbnew.LoadBoard(path)
    rules(b)
    drc(b, "as routed")

    # power traces: widen, then put back any segment that now violates clearance
    power = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() in ("VCC", "GND")]
    for t in power: t.SetWidth(pcbnew.FromMM(POWER_WIDTH))
    for _ in range(8):
        rpt, _c = drc(b, "  widening")
        bad = set()
        for m in re.finditer(r"@\(([-\d.]+) mm, ([-\d.]+) mm\): Track \[(?:VCC|GND)\]", rpt):
            bad.add((float(m.group(1)), float(m.group(2))))
        n = 0
        for t in power:
            if t.GetWidth() <= pcbnew.FromMM(TRACK): continue
            for p in (t.GetStart(), t.GetEnd()):
                if (round(pcbnew.ToMM(p.x), 4), round(pcbnew.ToMM(p.y), 4)) in bad:
                    t.SetWidth(pcbnew.FromMM(TRACK)); n += 1; break
        if n == 0: break
    wide = sum(1 for t in power if t.GetWidth() > pcbnew.FromMM(TRACK))
    print(f"power segments at {POWER_WIDTH} mm: {wide}/{len(power)}")

    # GND pours, both layers, thermal reliefs on pads
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = pcbnew.ToMM(bb.GetLeft()) + POUR_INSET, pcbnew.ToMM(bb.GetTop()) + POUR_INSET
    x1, y1 = pcbnew.ToMM(bb.GetRight()) - POUR_INSET, pcbnew.ToMM(bb.GetBottom()) - POUR_INSET
    gnd = b.FindNet("GND")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(gnd)
        z.SetLocalClearance(pcbnew.FromMM(POUR_CLEAR)); z.SetMinThickness(pcbnew.FromMM(POUR_MIN))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(pcbnew.FromMM(0.25)); z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        o = z.Outline(); o.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    # a crowded SMD pad may only get one thermal spoke; every GND pad is
    # already trace-routed, so such a pad simply stays off the pour
    for _ in range(4):
        rpt, c = drc(b, "  pour")
        starved = re.findall(r"\[starved_thermal\][^\n]*\n[^\n]*\n[^\n]*\n\s*@\([^)]*\): Pad (\S+) \[\w+\] of (\S+)", rpt)
        if not starved: break
        for num, ref in starved:
            b.FindFootprintByReference(ref).FindPadByNumber(num).SetZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
            print(f"  {ref} pad {num}: starved thermal, disconnected from pour (trace-routed)")
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    for z in b.Zones():
        print(f"GND pour on {pcbnew.LayerName(z.GetLayer())}: {z.GetFilledArea() / 1e12:.0f} mm2")
    _r, c = drc(b, "final")
    b.Save(path)
    return 0 if not c else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
