"""Read-only recovery entry point, no simulator imports."""
import json
from research_common import ROOT,read,same_pid,resources,HARD_STOP
import time
l=read(ROOT/'LEDGER.json',{});print(json.dumps(dict(state=read(ROOT/'RESEARCH_STATE.json'),ledger={k:v for k,v in l.items() if k!='attempts'},open_attempts=[x for x in l.get('attempts',[]) if not x['settled']],campaign_alive=same_pid(read(ROOT/'CAMPAIGN_PROCESS.json',{}).get('identity')),resources=resources(),remaining_seconds=max(0,HARD_STOP-time.time()),closed=(ROOT/'END.json').exists()),indent=2))
