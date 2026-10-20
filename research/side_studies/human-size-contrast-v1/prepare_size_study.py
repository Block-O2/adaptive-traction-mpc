"""Read-only source extraction; writes only the authorized independent study."""
from pathlib import Path
import ast, json, hashlib, subprocess, shutil, sys, time
from datetime import datetime, timezone
R=Path('/home/hank/coding/adaptive-traction-mpc-learning')
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/human-size-contrast-v1')
S='stages/stage5_personalized_motion_learning/'
C='41cdddef117caa4b191a52129c4ff83e481fd5a8'
def git(*args): return subprocess.check_output(['git','-C',str(R),*args])
def sha(b): return hashlib.sha256(b).hexdigest()
def save(name,x): (W/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
W.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,W/'prepare_size_study.py')
F=W/'snapshot'; F.mkdir()
finger=json.loads((R/S/'docs/adaptive_human_online_interface_v1/SOURCE_FINGERPRINTS.json').read_text())
integrity=json.loads((R/S/'docs/adaptive_human_online_interface_v1/FINAL_SOURCE_INTEGRITY.json').read_text())
assert integrity['protected_source_unchanged'] and integrity['source_commit']==C
tree=git('ls-tree','-r','--name-only',C).decode().splitlines()
records={}; missing=[]
def extract(p):
    if p in records: return (F/p).read_bytes()
    if p in finger:
        a=(R/p).read_bytes(); b=(R/p).read_bytes()
        if a!=b or sha(a)!=finger[p]: raise RuntimeError('Manifest mismatch: '+p)
        provenance='verified_1544_file_manifest'
    elif p in tree:
        a=git('show',C+':'+p); provenance='git_object:'+C
    else: missing.append(p); return None
    out=F/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(a)
    assert sha(out.read_bytes())==sha(a)
    records[p]={'sha256':sha(a),'bytes':len(a),'provenance':provenance}
    return a
roots={f'traction_mpc_stage{n}':f'stages/{stage}/src' for n,stage in [(3,'stage3_full3d'),(4,'stage4_adaptive_control'),(5,'stage5_personalized_motion_learning')]}
pending=['traction_mpc_stage5.full3d_adaptive_integration_v1.runtime']; seen=set()
def module_path(m):
    root=roots.get(m.split('.')[0]);
    if not root:return None
    p=root+'/'+m.replace('.','/')
    for x in (p+'.py',p+'/__init__.py'):
        if x in finger or x in tree:return x
    return None
while pending:
    mod=pending.pop()
    if mod in seen:continue
    seen.add(mod);p=module_path(mod)
    if not p:continue
    data=extract(p)
    if data is None:continue
    for i in range(1,len(mod.split('.'))):pending.append('.'.join(mod.split('.')[:i]))
    package=mod if p.endswith('/__init__.py') else mod.rsplit('.',1)[0]
    for node in ast.walk(ast.parse(data)):
        if isinstance(node,ast.Import):pending.extend(x.name for x in node.names)
        elif isinstance(node,ast.ImportFrom):
            base=node.module or ''
            if node.level: base='.'.join(package.split('.')[:len(package.split('.'))-node.level+1])+('.'+base if base else '')
            pending.append(base);pending.extend(base+'.'+x.name for x in node.names if x.name!='*')
# Only runtime configs/models; no historical results or campaign corpus.
for p in sorted(set(tree)|set(finger)):
    if p.startswith(S+'configs/') and p.endswith('.json') and ('stage5_geometry_mechanics_v1' in p or 'stage5_goal_task' in p or 'incremental_clearance_terminal_v9' in p):extract(p)
    if p==S+'models/cr12_v0.xml' or (p.startswith(S+'vendor/rokae_ros2_xmatecr12/meshes/') and p.endswith('.stl')):extract(p)
for name in ['summarize_phase_b.py','evaluate_execution_mode.py','score_return_endpoint_v2.py','sensor_time_integrity_v3.py']:
    extract(S+'scripts/high_rom_v1/'+name)
for p in [S+'docs/high_rom_v1/PHASE_B_MATRIX.json',S+'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json',S+'docs/adaptive_human_online_interface_v1/EXPERIMENT_CONTRACT.json']:
    extract(p)
# Preserve harness as reviewable evidence; new paths will be explicit in study wrapper.
hp=R/S/'scripts/adaptive_human_online_interface_v1/human_qualification.py'
local=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/adaptive_human_online_work/human_qualification.py')
assert hp.read_bytes()==local.read_bytes()
shutil.copy2(hp,W/'human_qualification_inherited.py')
save('SOURCE_PROVENANCE.json',{'source_commit':C,'source_branch_observed':git('branch','--show-current').decode().strip(),'manifest_sha256':sha((R/S/'docs/adaptive_human_online_interface_v1/SOURCE_FINGERPRINTS.json').read_bytes()),'verification':integrity,'files':records,'missing':missing,'harness_sha256':sha(hp.read_bytes()),'harness_basis':'matching prior Windows evidence copy and WSL campaign script; core source from verified manifest/commit only','not_copied':['results','archives','active_training_data','git','Python_environment','shared_STOP'],'snapshot_bytes':sum(x['bytes'] for x in records.values())})
for name in ['ADAPTIVE_HUMAN_ONLINE_INTERFACE_V1_REPORT.md','CURRENT_HUMAN_ADAPTATION_DATAFLOW.md','FINAL_SOURCE_INTEGRITY.json']:
    d=W/'prior_evidence';d.mkdir(exist_ok=True);shutil.copy2(R/S/'docs/adaptive_human_online_interface_v1'/name,d/name)
policy=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/cleanup_archive_v1/FUTURE_RESEARCH_DATA_POLICY.md')
shutil.copy2(policy,W/'prior_evidence'/policy.name)
old=json.loads((R/S/'docs/adaptive_human_online_interface_v1/EXPERIMENT_CONTRACT.json').read_text())
cases=[]
for h in [1.60,1.72,2.00]:
    case=json.loads(json.dumps(old['cases'][0]['case']));case['physical']['height_m']=h;case['case_key']=f'human_size_{h:.2f}_v1';case['evidence_category']='synthetic_height_scaling_v1';case['cell']['family']='synthetic_height_scaling'
    path=W/'cases'/f'{h:.2f}.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(case,indent=2)+'\n');cases.append({'height_m':h,'path':str(path),'sha256':sha(path.read_bytes()),'case':case})
contract={'version':'Human Size Contrast v1','frozen_utc':datetime.now(timezone.utc).isoformat(),'questions':['A: value of initial individual identification over fixed population','B: incremental value of continual over commissioning-only','C: physical feasibility, geometry prior, identifier range, or model/control error'],'source_commit':C,'cases':cases,'arms':['fixed_population','commissioning_only','continual_adaptive'],'runtime':'traction_mpc_stage5.full3d_adaptive_integration_v1.runtime (original four-Human chain)','online_gym_used':False,'reference_interface':'inherited waypoint reference for all arms','options_path':old['options_path'],'options_sha256':old['options_sha256'],'task_timeout_s':30.0,'execution_mode':'SCIENTIFIC_SIMULATION','scientific_host_delay_s':0.0,'simulate_planning_latency':True,'dev_a_recovery':True,'dev_c_bumpless_transfer':False,'dev_d_rigid_table_reference':True,'primary_budget':9,'diagnostic_budget':3,'dynamic_budget':12,'harness_repairs_max':2,'effective_hours_target':[2,4],'total_hours_cap':6,'threads':1,'max_side_simulations':1,'CPU_only':True,'rendering':False,'training':False,'shared_state_mutation':False,'primary_task':[ [5,10],[120,120] ],'pilot_selection':'Only an existing lower-ROM common protocol selected from static feasibility before any arm results; preserve 120-degree failures; no threshold/bound/placement change','noise_and_probes':'Unchanged runtime MeasurementCase default and identical inherited commissioning waypoints; fresh process per arm, no cross-arm data','truth_firewall':'Full truth only for plant generation and evaluation; nominal model and measured observations only for controllers','arm_semantics':{'A':'Fixed reference beta/residual/geometry; inherited fixed_population flag, audited before release','B':'Individual measured commissioning; freeze geometry/beta/residual in TASK','C':'Same commissioning protocol; geometry remains frozen; existing legal beta/residual continual updates'},'criteria':'Inherited physical predicates independently of mode-aware scientific verdict; wall-age characterization only','comparison_rules':['B-A and C-B within each height','No short failed integral versus full success ranking','No absolute J_F ranking across heights','Prediction evidence over beta versions or mixed-unit L2','No separated geometry/dynamics attribution without ablation','Synthetic scaling, not real adult distribution'],'resource_gate':{'WSL_reserve_GiB':2,'Windows_reserve_GiB':4,'peak_evidence_required':'aggregate parent and planner children + conservative margin','formal_SAC_throughput_or_latency_blocks_launch':True,'resource_deterioration':'Stop only side-study owner/children gracefully and persist partial evidence; never signal SAC','parallel_wall_time':'characterization, not clean benchmark'},'retention':'Compact summaries and source; key success/neutral/failure trajectories and necessary handoff checkpoints only; manifest every retained file; no historical raw copies'}
save('CONTRACT.json',contract)
save('STATE.json',{'status':'PREPARING_STATIC_AUDIT','started_utc':contract['frozen_utc'],'primary_runs':0,'diagnostic_runs':0,'harness_repairs':0,'source_missing':missing,'next_action':'Verify isolated imports and static feasibility; no time integration before resource gate'})
print(json.dumps({'study':str(W),'snapshot_files':len(records),'bytes':contract and sum(x['bytes'] for x in records.values()),'missing':missing}))
