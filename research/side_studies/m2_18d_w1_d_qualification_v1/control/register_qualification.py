from pathlib import Path
import os,sys,json,time,shutil,ast,hashlib,difflib,copy
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
REVIEW=Path(__file__).resolve().parents[1];A=P.parent/'m2_18d_t_second_round_coordination_v1'
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
assert (P/'ENVIRONMENT.json').exists(),'BOOTSTRAP_NOT_COMPLETE'
assert not (P/'ATTEMPTS.jsonl').exists(),'NO_POSTPHYSICS_REGISTRATION'
assert read(P/'audit/W1_DIAGNOSTIC_NUMBERS.json')['status']=='HISTORICAL_DIAGNOSIS_COMPLETE_NO_NEW_PHYSICS'
shutil.copy2(P/'W1_FAILURE_DIAGNOSIS.md',P/'provenance/PREPHYSICS_W1_FAILURE_DIAGNOSIS.md')
shutil.copy2(P/'audit/W1_DIAGNOSTIC_NUMBERS.json',P/'provenance/PREPHYSICS_W1_DIAGNOSTIC_NUMBERS.json')
for d in ['control','analysis']:
 for f in (REVIEW/d).glob('*.py'):shutil.copy2(f,P/d/f.name)
old=(A/'control/campaign.py').read_text();s=old
s=s.replace("assert n<(30 if MODE=='development' else 40),'START_CAP_WITH_10_VALIDATION_RESERVE'","assert n<PLAN['physics_budget'],'START_CAP_20'")
s=s.replace("   for c in CONFIG['arms']:\n", "   for c in CONFIG['arms']:\n    if c.get('conditional_repeat'):\n     prior=next(r for r in self.results if r['candidate']['id']=='D')\n     if not (prior['all_original_qualifications'] and prior['motion']['gain_percent']>=1.0 and prior['J_F_N_s']<next(r['J_F_N_s'] for r in self.results if r['candidate']['id']=='T')):\n      put(GROUP+'_REPEAT_NOT_STARTED.json',dict(reason='D did not pass every original qualification and retain force advantage',new_START=False));continue\n")
s=s.replace("    self.results.append(row);append", "    su=json.loads((P/'source/results'/ident/'summary.json').read_text());postures=[lr['selected_plan']['execution_screen']['second_round_posture'] for lr in su['learning_records'] if 'second_round_posture' in lr['selected_plan']['execution_screen']]\n    row['posture_execution']=postures;row['intervention_executed']=len(postures)==len(c.get('posture',[])) and all(x['status']=='ACCEPTED' for x in postures)\n    row['all_original_qualifications']=bool(comp['acceptance_pass'] and row['task']=='PASS' and row['receipt']=='PASS' and row['absolute_safety'] and row['intervention_executed'])\n    self.results.append(row);append")
s=s.replace("    if c['id']=='T':assert comp['acceptance_pass'],'T_MOTION_BASELINE_FAIL'", "    # New prospectively registered qualification contract permits D evaluation\n    # despite T motion failure; unchanged motion gates still qualify every arm.\n    if GROUP=='W1' and c['id'] in ['B','T']:\n     gate=bc.compare_raw(P/'source/results'/ident,P.parent/'m2_18d_t_second_round_coordination_v1/source/results'/ident);put('audit/'+ident+'_HISTORICAL_GATE.json',gate);assert gate['status']=='PASS','W1_REPRODUCTION_FAIL'")
assert s!=old and 'T_MOTION_BASELINE_FAIL' not in s
(P/'control/campaign.py').write_text(s)
put('audit/HARNESS_DIFF.json',dict(source=str(A/'control/campaign.py'),source_sha256=sha(A/'control/campaign.py'),diff=''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True))),reason='user-authorized new version: W1 D qualification even when T motion fails; original candidate parameters, execution and qualification thresholds unchanged; 20 START cap; branch-conditioned repeat only'))
w1=read(A/'W1_PLAN.json');d=copy.deepcopy(next(c for c in w1['arms'] if c['id']=='P_corridor'));d['id']='D';d.pop('repeat_of',None)
dr=copy.deepcopy(d);dr.update(id='D_repeat',repeat_of='D',conditional_repeat=True)
base=[dict(id=x,base=x,posture=[],changes=[]) for x in ['B','T']]+[d]
conds=[('W1',w1['condition']['prefix'],'fixed historical W1 qualification',True),('R0',{'OUTBOUND':[[.08,.04,.03]]},'W1 OUTBOUND fixed, RETURN0 background removed',False),('O0',{'OUTBOUND':[[-.045,-.075,-.055]],'RETURN':[[.04,.02,.03]]},'W1 RETURN fixed, OUTBOUND0 replaced by legal V1 prefix',False),('W2',read(A/'W2_PLAN.json')['condition']['prefix'],'new legal prefix only if W1 D and repeat fully qualify and retain force advantage',False)]
for name,prefix,role,repeat in conds:
 cfg=dict(frozen_unix=time.time(),condition=dict(name=name,seed=2026102001 if name!='W2' else 2026102002,prefix=prefix,role=role),fork_after_prefix=1,arms=copy.deepcopy(base)+([copy.deepcopy(dr)] if repeat else []),D_frozen_source_sha256=sha(A/'W1_PLAN.json'),no_reselection=True)
 put(name+'_PLAN.json',cfg)
protocol='''# Frozen W1 diagnosis and D qualification protocol v1

Frozen after historical diagnosis and before any new physical START. Scientific simulation only, same Human/plant as historical packages. W1 is an exposed diagnostic condition, not an untouched held-out test; D was selected before W1 and remains frozen. R0/O0 are controlled background experiments; W2 was previously registered but never executed and is reserved for conditional new-prefix validation. No learning or search.

## Question and unchanged contract
Does frozen D pass every original task/safety/motion/causal gate in W1, preserve the T force advantage vs same-condition B, and improve actual motion relative to T? D is the exact prior P_corridor: frozen 18D parameters/RETURN plateau, T suffix factor1.5 aligned upward to5ms after final OUTBOUND goal selection, RETURN slots2/3 (0-based) each [+0.3,-0.3] degrees. Each live originally selected duration/pass velocity is retained. Downstream live planning may respond causally. No D/T parameter or selection-rule changes.

B, plant/Human/robot/contact/gravity/actuator/ROM/torque/task/HOLD, original safety/motion thresholds, truth firewall,40ms bridge,100ms lifecycle,current-state admission,source age,receipt/native ownership,carry/fallback remain frozen. No Human qpos/qvel assignment/replay, bypass or shortened task. Evaluation truth is only read after execution, never feeds fixed actions.

## Legal matching and background controls
Each registered group starts a real cold parent with the registered seed, executes OUTBOUND0 through the original certificate/admission chain, then serial complete live-address-space forks B/T/D. Full native state, controller history, beliefs, lifecycle, PRNG and native ownership are inherited. Every fork hash must match and parent must stay unchanged; parent completes B and must exactly reproduce its B child. Complete J_F includes inherited prefix. RETURN0 is executed independently in each arm by the same background rule and original checks. Same background rule is not a claim of identical post-treatment RETURN entry states.

W1: seed2026102001; O0 graph[.08,.04,.03], R0 graph[.04,.02,.03]. R0 control removes RETURN graph while retaining W1 OUTBOUND. O0 control uses V1 OUTBOUND[-.045,-.075,-.055] while retaining W1 RETURN. Both controls use seed2026102001. Each has its own matched B/T/D; absolute J_F from unmatched backgrounds is never used to rank candidates. Control effects are conditional changes in the background rule plus its downstream causal response; the missing fourth factorial corner prevents a full interaction decomposition. K3 graph timings are .1/.4/.7 of remaining causal progress, not imposed Human states. Runtime refusal is a preserved failed attempt, never retried by bypassing admission.

## Order, qualification and branches
1. W1 parent/B/T/D, with B/T raw archive reproduction required before D. T motion failure is retained and no longer prevents D START under this new user-authorized contract. Absolute safety/task/causal or pairing failure stops related physics.
2. If W1 D fully passes all original gates, both posture intents actually execute and force gain>=1% vs B with J_F(D)<J_F(T), one deterministic D repeat is run in the same parent. Repeat must match every scientific raw/native/receipt field; it adds no new state.
3. Run the two registered controlled backgrounds R0 then O0 to identify conditional background effects, including their failures. No tuning, reselection or threshold adjustment. Motion failure alone is a result; each D still receives all original gates.
4. Only if W1 D and repeat qualify and retain force, and no global stop, run W2 matched B/T/D: seed2026102002, O[.11,-.035,.045], R[-.04,.025,-.035]. If not, no W2 START. A failure does not authorize modifying or renaming D as repaired original D.

Full qualification: complete TASK and all phases; original dense raw velocity/acceleration(max,p95,RMS), jerk(p95,RMS), excursion/cumulative dose/endpoint/boundaries, tracking/moment/ROM/clearance/force and moment peaks; unchanged original absolute limits; receipt/current admission/source/version/native ownership. Full and phase J_F, native derivatives plus SG5/SG21 sensitivity, actual issued reference/Human alignment are reported. Gates are byte-identical MOTION_ACCEPTANCE_PROTOCOL.json and frozen original evaluator formulas. Full force gain with failed motion is unqualified. D posture rejection/fallback is preserved but does not establish frozen-D execution qualification.

Retained force advantage means at least the existing1% research gain vs matched B; incremental gain vs T is reported separately as signed full-task J_F delta. Motion vs T uses full combined velocity TV, acceleration variation, jerk RMS, per-joint raw stats and dose; signs/magnitude are reported without declaring comprehensive improvement when tradeoffs remain. Existing prior selection thresholds stay frozen and are not used to reselect a candidate. No clinical threshold or baseline promotion is inferred from a small force gain or deterministic repeat alone.

## Budget and stopping
T0 2026-10-17T17:34:07+08:00; no new START after20:49:07; hard STOP21:34:07. Every parent/fork/failure/partial/repeat counts, maximum20 START, physics serial. Per-arm timeout900s, an additional900s dispatch reserve precedes the cutoff. Planned maxima: W1 up to5, R0 4, O0 4, conditional W2 4 =17; remaining3 are unused and do not authorize extra search/retries. Final45minutes are reserved for independent arithmetic, protection and delivery. Stop early with clear findings; no need to consume time or attempts. All artifacts and negative records retained; no Git write operations. All owned workers joined and START/END closed before final STOP.
'''
(P/'FROZEN_EXPERIMENT_PROTOCOL.md').write_text(protocol)
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'control'),str(P/'code')]
import study_common as sc,matched_harness as mh,analyze_matched as am
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','SELECTION_RULE.json','FROZEN_SELECTION.json']:assert sha(P/n)==sha(A/n),n
for n in ['code/terminal_repair.py','control/round_planner.py']:assert sha(P/n)==sha(A/n),n
for root in ['source','code','deps','weights','control']:
 for f in (P/root).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
files={str(f.relative_to(P)):sha(f) for root in ['source','code','deps','weights','control'] for f in (P/root).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','SELECTION_RULE.json','FROZEN_SELECTION.json','FROZEN_EXPERIMENT_PROTOCOL.md','RUN_PLAN.json','output/SHARED_COORDINATION_ACTION_CONTRACT.json','W1_PLAN.json','R0_PLAN.json','O0_PLAN.json','W2_PLAN.json']:files[n]=sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=files,frozen_unix=time.time(),base_manifest_sha256=sha(A/'EXECUTION_CODE_MANIFEST.json'),D_parameters_and_execution_contract_unchanged=True))
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',unix=time.time(),no_physics_started=True,imports_isolated=True,original_parameters_T_D_motion_byte_identical=True,AST=True,diagnosis_before_freeze=True,legal_prefixes_registered_before_START=True,harness_change='new contract permits D despite T motion failure; all original gates unchanged'))
for n in ['FROZEN_EXPERIMENT_PROTOCOL.md','W1_FAILURE_DIAGNOSIS.md','RUN_PLAN.json','PREPHYSICAL_CHECKS.json']:
 shutil.copy2(P/n,REVIEW/n)
(REVIEW/'figures').mkdir(exist_ok=True);shutil.copy2(P/'figures/W1_failure_timeline.png',REVIEW/'figures/W1_failure_timeline.png')
print(json.dumps(dict(status='PASS',registered_groups=[c[0] for c in conds],manifest_files=len(files),frozen_unix=time.time(),physics_starts=0)),flush=True)
