"""Authorized exact-path local staging only; never commit, push or merge."""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,hashlib,ast
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/v_horizon_continuation_audit_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1';W=S/'scripts/adaptive_human_online_interface_v1';OUT=S/'results/adaptive_human_online_interface_v1'
def git(*args):return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
def save(name,data):(D/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def manifest():
    p=D/'RAW_DATA_MANIFEST.json';data=json.loads(p.read_text());entries=[]
    for root,kind in ((OUT,'raw_campaign_data'),(W,'reproducibility_script'),(D,'campaign_evidence'),(S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1','new_research_source')):
        for path in sorted(root.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.name=='RAW_DATA_MANIFEST.json':continue
            if kind=='new_research_source' and path.name not in ('online_reference.py','runtime_online_v1.py','online_gym.py'):continue
            entries.append(dict(path=str(path.relative_to(R)),bytes=path.stat().st_size,sha256=sha(path),kind=kind))
    data.update(entries=entries,total_bytes=sum(x['bytes'] for x in entries),generated_utc=datetime.now(timezone.utc).isoformat());save('RAW_DATA_MANIFEST.json',data)
def main():
    state=json.loads((D/'STATE.json').read_text());assert state['status']=='ADAPTIVE_HUMAN_ONLINE_INTERFACE_V1_COMPLETE' and all(state['gates'].values())
    assert git('branch','--show-current')==state['branch'] and git('rev-parse','HEAD')==state['source_commit']
    changes=git('diff','--name-status','HEAD').splitlines()
    roots=[str(x.relative_to(R))+'/' for x in (D,W)]+[str((S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1').relative_to(R))+'/online',str((S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_online_v1.py').relative_to(R))]
    assert all(x.startswith('A\t') and any(x.split('\t',1)[1].startswith(root) for root in roots) for x in changes), 'Original tracked files changed'
    expected=['CURRENT_HUMAN_ADAPTATION_DATAFLOW.md','CURRENT_HUMAN_ADAPTATION_SOURCE_EVIDENCE.json','CURRENT_HUMAN_ADAPTATION_VALIDATION.md','CURRENT_HUMAN_ADAPTATION_VALIDATION.json','CURRENT_HUMAN_ADAPTATION_COMPARISON.csv','ONLINE_ACTION_INTERFACE_SPEC.md','ONLINE_ACTION_INTERFACE_VALIDATION.md','ONLINE_ACTION_INTERFACE_VALIDATION.json','ONLINE_INTERFACE_BLOCKER_RETEST.md','ONLINE_INTERFACE_BLOCKER_RETEST.json','ONLINE_INTERFACE_RATE_TEST.csv','ONLINE_INTERFACE_RATE_TEST.json','ONLINE_INTERFACE_ADVERSARIAL_TEST.md','ONLINE_INTERFACE_ADVERSARIAL_TEST.json','OLD_RSS_VS_ONLINE_INTERFACE.md','OLD_RSS_VS_ONLINE_INTERFACE.json','CR12_ONLINE_INTERFACE_CLOSED_LOOP.md','CR12_ONLINE_INTERFACE_CLOSED_LOOP.json','DIRECT_RL_GYM_READINESS.md','DIRECT_RL_GYM_READINESS.json','CUDA_RL_ENV_READINESS.md','CUDA_RL_ENV_READINESS.json','ADAPTIVE_HUMAN_ONLINE_INTERFACE_V1_REPORT.md','RAW_DATA_MANIFEST.json','STATE.json']
    assert all((D/n).is_file() for n in expected)
    sources=[S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1'/n for n in ('online_reference.py','runtime_online_v1.py','online_gym.py')]
    for path in sources+list(W.glob('*.py')):ast.parse(path.read_text())
    paths=[p for p in D.iterdir() if p.is_file() and (p.suffix in ('.md','.json','.csv') or p.name in ('UNIT_TESTS.txt','RL_ENV_FREEZE.txt','CUDA_PIP_CHECK.txt'))]+[p for p in W.iterdir() if p.is_file() and p.suffix in ('.py','.sh')]+sources
    paths=sorted(paths)
    for path in paths:subprocess.check_call(['git','-C',str(R),'add','--',str(path.relative_to(R))])
    subprocess.check_call(['git','-C',str(R),'diff','--cached','--check'])
    names=git('diff','--cached','--name-status').splitlines();assert all(x.startswith('A\t') for x in names)
    state.update(staged=True,staged_file_count=len(paths)+1,last_completed='Final source integrity, scientific physical checks, Gym/CUDA readiness and exact-path staging',git_index_checked=True)
    save('STATE.json',state)
    final=dict(branch=git('branch','--show-current'),HEAD=git('rev-parse','HEAD'),staged_paths=[str(p.relative_to(R)) for p in paths]+[str((D/'FINAL_GIT_STATE.json').relative_to(R))],staged_new_files_only=True,raw_traces_staged=False,individual_path_staging=True,cached_diff_whitespace_check='PASS',AST_parse='PASS',commit_performed=False,push_performed=False,merge_performed=False,reset_performed=False,stash_performed=False,untracked_local_artifacts='New raw results and original request/installation logs/derived runtime patch remain local and SHA256-inventoried.',terminal_status=state['status'])
    save('FINAL_GIT_STATE.json',final);manifest()
    for name in ('STATE.json','FINAL_GIT_STATE.json','RAW_DATA_MANIFEST.json'):subprocess.check_call(['git','-C',str(R),'add','--',str((D/name).relative_to(R))])
    subprocess.check_call(['git','-C',str(R),'diff','--cached','--check'])
    assert not git('diff','--name-only'), 'Staged files differ from working tree'
    actual=git('diff','--cached','--name-only').splitlines();assert sorted(actual)==sorted(final['staged_paths'])
    print(json.dumps(dict(status=state['status'],staged_files=len(actual),HEAD=final['HEAD'],branch=final['branch'],checks='PASS',commit_push_merge=False)))
if __name__=='__main__':main()
