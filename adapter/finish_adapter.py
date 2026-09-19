#!/usr/bin/env python3
"""Import Freerouting's .ses into the board, check connectivity, DRC, save.

pcbnew's ImportSpecctraSES(path) works on the GUI's current board only, so
this parses the session file directly (it is a small s-expression) and
creates the tracks and vias itself.
"""
import re, sys
import pcbnew


def tokenize(text):
    return re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)


def parse(tokens):
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop(); stack[-1].append(node)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0]


def find_all(node, head):
    if isinstance(node, list):
        if node and node[0] == head:
            yield node
        for c in node:
            yield from find_all(c, head)


def main(board_in, ses, board_out):
    b = pcbnew.LoadBoard(board_in)
    tree = parse(tokenize(open(ses).read()))
    routes = next(find_all(tree, "routes"))
    res = next(find_all(routes, "resolution"))          # ['resolution', 'um', '10']
    unit_nm = {"um": 1000, "mm": 1000000, "mil": 25400}[res[1]] / int(res[2])
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    vias = {}
    for ps in find_all(routes, "padstack"):
        m = re.match(r"Via\[\d+-\d+\]_(\d+):(\d+)_um", ps[1])
        if m:
            vias[ps[1]] = (int(m.group(1)) * 1000, int(m.group(2)) * 1000)   # nm
    ntracks = nvias = 0
    for netnode in find_all(next(find_all(routes, "network_out")), "net"):
        net = b.FindNet(netnode[1])
        if net is None:
            print("unknown net", netnode[1]); continue
        for w in find_all(netnode, "wire"):
            path = next(find_all(w, "path"))
            layer = layers[path[1]]; width = int(float(path[2]) * unit_nm)
            pts = [(int(float(path[i]) * unit_nm), -int(float(path[i + 1]) * unit_nm)) for i in range(3, len(path), 2)]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(pcbnew.VECTOR2I(x1, y1)); t.SetEnd(pcbnew.VECTOR2I(x2, y2))
                t.SetWidth(width); t.SetLayer(layer); t.SetNet(net); b.Add(t); ntracks += 1
        for v in find_all(netnode, "via"):
            dia, drill = vias[v[1]]
            via = pcbnew.PCB_VIA(b)
            via.SetPosition(pcbnew.VECTOR2I(int(float(v[2]) * unit_nm), -int(float(v[3]) * unit_nm)))
            via.SetWidth(dia); via.SetDrill(drill); via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNet(net); b.Add(via); nvias += 1
    b.BuildConnectivity()
    unrouted = b.GetConnectivity().GetUnconnectedCount(True)
    print(f"imported {ntracks} track segments, {nvias} vias; unrouted connections: {unrouted}")
    b.Save(board_out)
    ok = pcbnew.WriteDRCReport(b, "drc.rpt", pcbnew.EDA_UNITS_MILLIMETRES, True)
    rpt = open("drc.rpt").read()
    viol = len(re.findall(r"^\[", rpt, re.M))
    print("DRC report written:", ok, "| violation lines:", viol)
    for line in rpt.splitlines():
        if line.startswith("[") or "Found" in line or "unconnected" in line.lower():
            print("  ", line[:110])
    return unrouted, viol


if __name__ == "__main__":
    main(*sys.argv[1:])
