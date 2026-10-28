from pathlib import Path
import json,numpy as np
P=Path(__file__).resolve().parents[1];g='COORD_R2';rows=[r for r in json.loads((P/'data'/f'{g}.json').read_text()) if r['horizon_s']==.5];out=[]
for r in rows:
 path=P/'history'/(r['id']+'_OBSERVED_HISTORY_AUDIT.json');assert path.exists(),'MISSING_LIVE_FEATURE_AUDIT:'+r['id'];d=json.loads(path.read_text());assert d['available'],d
 error=np.array(d['features'])-np.array(r['history_risk_features']);out.append(dict(id=r['id'],features=len(error),max_abs_error=float(abs(error).max()),available_before_tail=True));assert abs(error).max()<1e-7,('LIVE_CAUSAL_HISTORY_REPLAY_MISMATCH',r['id'],error.tolist())
(P/'audit/LIVE_WHOLE_HISTORY_FEATURE_REPLAY.json').write_text(json.dumps({'status':'PASS','rows':out,'scope':'development-only H capture, before model/test freeze; original trace observer/wrench and completed guard events only'},indent=2)+'\n');print('LIVE_HISTORY_REPLAY_PASS',len(out),flush=True)
