"""Actual loaded scientific-module origin audit; no environment reset."""
from pathlib import Path
import os,sys,json
from research_common import ROOT,RUNTIME,atomic,sha,now

def audit_loaded():
    expected=json.loads((RUNTIME/'FROZEN_CONTRACT_MANIFEST.json').read_text())['files']
    rows=[];bad=[]
    for name,module in sorted(list(sys.modules.items())):
        if not name.startswith(('traction_mpc_stage3','traction_mpc_stage4','traction_mpc_stage5')):continue
        file=getattr(module,'__file__',None)
        if not file:continue
        p=Path(file).resolve();inside=p.is_relative_to(RUNTIME/'source')
        rel=str(p.relative_to(RUNTIME)) if p.is_relative_to(RUNTIME) else None
        actual=sha(p);want=expected.get(rel) if rel else None
        x=dict(module=name,path=str(p),inside_isolated_source=inside,
               expected_sha256=want,actual_sha256=actual,pass_=inside and want==actual)
        rows.append(x)
        if not x['pass_']:bad.append(x)
    return dict(time_utc=now(),pass_=bool(rows) and not bad,modules=len(rows),loaded=rows,
         mismatches=bad,scope='Actual imported traction modules in this process; non-scientific installed dependencies tracked separately; no physics executed by this audit')

if __name__=='__main__':
    os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
    sys.path.insert(0,str(RUNTIME));import common
    from runtime_setup import install
    install()
    from pilot_env import PilotEnv
    from cloud_case_audit import audit
    from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1
    result=audit_loaded();result['key_runtime_path']=runtime_sac_expert_v1.__file__
    result['interpreter']=sys.executable;result['physics_attempts']=0
    atomic(ROOT/'audit/ACTUAL_IMPORT_IDENTITY.json',result)
    print(json.dumps({k:result[k] for k in ['pass_','modules','mismatches','key_runtime_path','physics_attempts']}))
    raise SystemExit(0 if result['pass_'] else 1)
