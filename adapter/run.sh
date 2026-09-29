#!/bin/sh
# Adapter build pipeline: board -> DSN -> Freerouting -> SES -> DRC -> gerbers.
# Needs KiCad 7 (pcbnew python + kicad-cli), Java, freerouting.jar, xvfb-run.
set -e
python3 build_adapter.py
python3 -c "import pcbnew; b=pcbnew.LoadBoard('adapter.kicad_pcb'); assert pcbnew.ExportSpecctraDSN(b,'adapter.dsn')"
rm -f adapter.ses
xvfb-run -a java -jar freerouting.jar -de adapter.dsn -do adapter.ses -mp ${PASSES:-200} -dr 2>&1 | grep -i "completed\|not routed" || true
python3 finish_adapter.py adapter.kicad_pcb adapter.ses adapter_routed.kicad_pcb
rm -rf gerbers && mkdir gerbers
kicad-cli pcb export gerbers -o gerbers/ --layers F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge_Cuts --subtract-soldermask adapter_routed.kicad_pcb
kicad-cli pcb export drill -o gerbers/ --format excellon --excellon-units mm adapter_routed.kicad_pcb
kicad-cli pcb export svg -o top.svg --layers F.Cu,F.SilkS,Edge.Cuts --page-size-mode 2 adapter_routed.kicad_pcb
kicad-cli pcb export svg -o bottom.svg --layers B.Cu,Edge.Cuts --page-size-mode 2 --mirror adapter_routed.kicad_pcb
(cd gerbers && zip -q ../vp1-055-adapter-gerbers.zip *)
echo "done: vp1-055-adapter-gerbers.zip"
