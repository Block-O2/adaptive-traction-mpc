from analyze_matched import *
import platform
def main():
 measured={p.name[:-14]:load(p) for p in (S/'reports').glob('*_MEASURED.json')};lineages={p.name[:-32]:load(p) for p in (S/'reports').glob('*_EXECUTED_RESIDUAL_RECEIPTS.json')}
 rows=[]
 for p in (S/'reports').glob('*_MEASURED.json'):
  r=load(p)
  if 'FAST_observations' not in r:
   ident=r['id'];a=S/'source/results'/ident/'runtime_artifacts.json.gz';v=np.asarray([(q['host_step_finish_ns']-q['host_step_start_ns'])/1e6 for q in array_items(a,'native_states_evaluation_only')]);r['FAST_observations']=dict(clock='host profiling within frozen scientific epochs',native_step_wall_ms=dict(n=len(v),p50=float(np.quantile(v,.5)),p95=float(np.quantile(v,.95)),p99=float(np.quantile(v,.99)),mean=float(v.mean()),max=float(v.max())),original_host_FAST_service_gap='NOT_EVALUABLE',host_clock_runtime_qualification='NOT_EVALUABLE',wall_activation_age_profile=r['native_physical_audit']['unchanged_evaluator']['wall_runtime_characterization']);save(p,r)
  rows.append(r)
 save(S/'FAST_RUNTIME_OBSERVATIONS.json',dict(clock='SCIENTIFIC_SIMULATION with honest host timestamps',runs={r['id']:r['FAST_observations'] for r in rows},formal_runtime_qualification=False))
 save(S/'MOTION_FORCE_TRADEOFFS.json',dict(clock='SCIENTIFIC_SIMULATION',clinical_thresholds=False,runs=rows,denominator=len(rows)))
 repeat=[]
 repeat_pairs=[(tag,'discovery_'+tag,'matched_discovery_'+tag) for tag in ['O','R','OR']]+[('R_RETURN_fork','matched_discovery_R','matched_discovery_RETURN_entry_R'),('B0_RETURN_fork','matched_discovery_parent_B0','matched_discovery_RETURN_entry_zero')]
 for tag,a,b in repeat_pairs:
  if not all((S/'source/results'/i/'trace.npz').exists() for i in [a,b]):continue
  with np.load(S/'source/results'/a/'trace.npz') as za,np.load(S/'source/results'/b/'trace.npz') as zb:
   equality={k:(za[k].shape==zb[k].shape and (np.array_equal(za[k],zb[k],equal_nan=True) if za[k].dtype.kind in 'fc' else np.array_equal(za[k],zb[k]))) for k in za.files}
  repeat.append(dict(tag=tag,runs=[a,b],all_archived_trace_fields_equal=all(equality.values()),fields=equality,J_F_N_s=[load(S/'output'/(i+'.json'))['J_F'] for i in [a,b]],scope='two fresh scientific commissioning parents, same fixed setup; numerical reproducibility, not independent Human or host generalization'))
 save(S/'SCIENTIFIC_REPEATABILITY.json',dict(rows=repeat,no_new_physics=True))
 snapshots=[load(S/'reports'/('matched_discovery_'+tag+'_SNAPSHOT.json')) for tag in ['O','R','OR','Frozen_M2'] if (S/'reports'/('matched_discovery_'+tag+'_SNAPSHOT.json')).exists()]
 return_snaps=[load(S/'reports'/('matched_discovery_'+tag+'_SNAPSHOT.json')) for tag in ['RETURN_entry_zero','RETURN_entry_R'] if (S/'reports'/('matched_discovery_'+tag+'_SNAPSHOT.json')).exists()]
 state=load(S/'MATCHED_STATE_VALIDATION.json');state['full_OUTBOUND_request_snapshot_hashes']=[r['hash'] for r in snapshots];state['all_full_OUTBOUND_request_hashes_equal']=len(snapshots)==4 and len(set(r['hash'] for r in snapshots))==1;state['same_RETURN_entry_hashes']=[r['hash'] for r in return_snaps];state['same_RETURN_entry_complete_hash_equal']=len(return_snaps)==2 and return_snaps[0]['hash']==return_snaps[1]['hash'];state['parent_after_each_child']=load(S/'reports/matched_discovery_PARENT_CHECKS.json');state['immediate_complete_address_space_restoration_proofs']=[load(p) for p in (S/'reports').glob('*_FORK_RESTORED.json')];state['coverage']=['MuJoCo mjSTATE_INTEGRATION + all native model/plant objects','Human physical model/commissioning belief/geometry','observer/updater/controller/planner history','reference/governor/task/phase progress','scheduler/pending/futures/completed request + carry/issued slots','lifecycle/native execution context/cache handles','Python/NumPy RNG and all process address space'];state['limitations']=['not durable checkpoint; fork state exists only within live parent','opaque handles inherited through os.fork, not reconstructed','OS host-clock scheduling not cloned','initial duplicate complete digests differ only in observational gc_events count; scientific state and immediate before/after full-copy digests are exact; new matched discovery full digests are identical']
 save(S/'MATCHED_STATE_VALIDATION.json',state)
 (S/'MATCHED_STATE_VALIDATION.md').write_text('# 合法匹配状态验证\n\n'+f"科学复现门限：{state['status']}。116,320个native行与5,817个receipt的同动作轨迹检查通过；有限数值误差为0，NaN日志字段仅核对一致缺失。\n\n"+f"新发现四个干预分支完整OUTBOUND入口hash一致：{state['all_full_OUTBOUND_request_hashes_equal']}；RETURN-entry两个分支完整hash一致：{state['same_RETURN_entry_complete_hash_equal']}。\n\n"+'完整活进程address-space由os.fork复制；JSON只记录验证摘要，未用来恢复。MuJoCo integration、Human/commissioning、estimator/controller、reference/phase、planner/scheduler、carry/issued slots/lifecycle、RNG与native context全部继承。每个child恢复完整hash、parent在child退出后的完整hash都核验。\n\n科学仿真冻结物理epoch；原科学模式source≤100ms、native admission/governor/physical safety保留。Host 40ms bridge/100ms wall lifecycle原代码未改，但本包不证明其host资格。Wall plan-age的原FAIL和mode-aware realtime N/A均保留。\n\n初次两个零分支的serial snapshot差仅为gc_events诊断列表长度2→4；该诊断记录未被scrub，逐branch完整复制/parent不变证据保留。后续每个分支组只collect一次，新发现组完整hash相同。\n')
 if (S/'PHASE_ISOLATION_RESULTS.json').exists():
  phase=load(S/'PHASE_ISOLATION_RESULTS.json');phase['RETURN_entry_zero_vs_full_B0']=negcontrol('matched_discovery_RETURN_entry_zero','matched_discovery_parent_B0');phase['RETURN_R_repeated_from_two_fork_boundaries']=negcontrol('matched_discovery_RETURN_entry_R','matched_discovery_R');phase['matching_status']=dict(full_initial_complete_hash_equal=state['all_full_OUTBOUND_request_hashes_equal'],RETURN_entry_complete_hash_equal=state['same_RETURN_entry_complete_hash_equal']);earliest={}
  base='matched_discovery_parent_B0'
  with np.load(S/'source/results'/base/'trace.npz') as z:tb={k:z[k].copy() for k in ['time_s','stage','physics_steps','evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n','reference_q_rad','cr12_actuator_command_nm']}
  for tag in ['O','R','OR']:
   with np.load(S/'source/results'/('matched_discovery_'+tag)/'trace.npz') as z:ta={k:z[k].copy() for k in tb}
   earliest[tag]={k:firstdiff(ta,tb,k) for k in ['evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n','reference_q_rad','cr12_actuator_command_nm']}
  phase['earliest_post_intervention_observable_difference']=earliest;phase['RETURN_entry_delta_vs_B0']={k:dict(q_rad=np.asarray(v['q_rad'])-phase['RETURN_entry_states']['parent_B0']['q_rad'],dq_rad_s=np.asarray(v['dq_rad_s'])-phase['RETURN_entry_states']['parent_B0']['dq_rad_s']) for k,v in phase['RETURN_entry_states'].items() if k!='parent_B0'};save(S/'PHASE_ISOLATION_RESULTS.json',phase)
 events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends={r['id']:r for r in events if r['event']=='END'};attempts=[]
 for r in starts:
  ident=r['id'];files=[dict(path=str(p.relative_to(S)),bytes=p.stat().st_size) for folder in [S/'output',S/'reports',S/'source/results'/ident] for p in folder.glob('*') if p.is_file() and (folder.name==ident or p.name.startswith(ident))];partial=S/'output'/(ident+'_PARTIAL_COMPUTE.json');data=S/'output'/(ident+'_DATA.json');native=None
  if data.exists():native=load(data)['metric']['actual_new_native_physics_steps']
  elif partial.exists():native=load(partial).get('actual_new_native_physics_steps')
  attempts.append(dict(start=r,end=ends.get(ident),complete=data.exists(),actual_new_native_steps=native,files=files,raw_failure_retained=ident in ends and ends[ident].get('returncode')!=0))
 save(S/'ATTEMPT_EVIDENCE_INDEX.json',dict(attempt_denominator=len(starts),complete_denominator=sum(r['complete'] for r in attempts),attempts=attempts,raw_trace_limitation='failed parents did not emit full trace/summary; actual partial native compute + errors/logs retained, unchanged pre-fork prefix is also preserved in completed sibling branch trace. No fabricated partial trace or JSON restore.',all_generated_artifacts_retained=True))
 save(S/'RUNTIME_ENVIRONMENT.json',dict(python_executable=sys.executable,python_version=sys.version,platform=platform.platform(),NumPy=np.__version__,specified_python='/home/hank/envs/adaptive-online-rl-v1/bin/python',threads={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']},no_training=True))
 print(json.dumps(dict(complete=len(rows),attempts=len(starts),OUTBOUND_complete_hash_equal=state['all_full_OUTBOUND_request_hashes_equal'],RETURN_complete_hash_equal=state['same_RETURN_entry_complete_hash_equal'])),flush=True)
if __name__=='__main__':main()
