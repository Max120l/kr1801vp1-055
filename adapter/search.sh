#!/bin/sh
# try placement nudges until Freerouting completes every connection
for n in 0 0.3 -0.3 0.6 -0.6; do
  echo "=== NUDGE=$n"
  NUDGE=$n python3 build_adapter.py >/dev/null
  python3 -c "import pcbnew; b=pcbnew.LoadBoard('adapter.kicad_pcb'); assert pcbnew.ExportSpecctraDSN(b,'adapter.dsn')"
  rm -f adapter.ses
  xvfb-run -a java -jar freerouting.jar -de adapter.dsn -do adapter.ses -mp 300 -dr >/dev/null 2>&1
  python3 finish_adapter.py adapter.kicad_pcb adapter.ses adapter_routed.kicad_pcb | grep "imported"
  if python3 finish_adapter.py adapter.kicad_pcb adapter.ses adapter_routed.kicad_pcb | grep -q "unrouted connections: 0"; then echo "COMPLETE with NUDGE=$n"; exit 0; fi
done
echo "no complete routing found"; exit 1
