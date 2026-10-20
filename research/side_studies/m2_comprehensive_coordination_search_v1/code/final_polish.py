from analyze_matched import *
import shutil
def main():
 snapshots=[]
 for path in (S/'reports').glob('*_EXECUTED_RESIDUAL_RECEIPTS.json'):
  r=load(path);ident=r['id'];dec=load(S/'output'/(ident+'_DECISIONS.json'));labels=dec['rows'];select=S/'output'/(ident+'_SELECTIONS.json');selection=load(select)['rows'] if select.exists() else []
  with np.load(S/'source/results'/ident/'trace.npz') as z:start=float(z['time_s'][np.flatnonzero(z['stage']=='TASK')[0]])
  for row in r['rows']:
   matches=[x for x in labels if x['phase']==row['phase'] and row['proposal_physics_s'] is not None and abs(start+x['task_s']-row['proposal_physics_s'])<1e-8]
   assert len(matches)<=1,'AMBIGUOUS_PROPOSAL_LABEL'
   row['causal_K3_proposal']=matches[0] if matches else None
   selected=[x for x in selection if x['request_id']==row['request_id']];assert len(selected)<=1
   row['frozen_M2_selection']=selected[0] if selected else None
   if row['physically_executed_nonzero']:assert len(matches)==1 and np.any(abs(np.asarray(matches[0]['action']))>1e-12),'NONZERO_WITHOUT_PROPOSAL_LINEAGE'
  r['proposal_lineage_verified']=True;save(path,r);snapshots.append(r)
 save(S/'NATIVE_EXECUTION_LINEAGE.json',dict(clock='SCIENTIFIC_SIMULATION',HOST_EXECUTION_CAUSAL_VALID='NOT_EVALUABLE',runs=snapshots,denominator=len(snapshots),proposal_admission_receipt_physical_steps_complete=True))
 m2=load(S/'output/matched_discovery_Frozen_M2_SELECTIONS.json')
 save(S/'FROZEN_M2_DYNAMIC_TABLE_EVIDENCE.json',dict(source='output/matched_discovery_Frozen_M2_SELECTIONS.json',selections=m2['rows'],Q_calls=m2['Q_calls'],Q_updates=0,G_calls=0,note='raw DATA.table is initial static container; this arm delegates to unmodified NativeInterface M2, actual applied dynamic tables/candidate identities are in these selections and linked native requests. No raw DATA field rewritten.'))
 protocol=load(S/'EXPERIMENT_PROTOCOL.json');selection=load(S/'CANDIDATE_SELECTION.json');assert selection['selected'] is None,'This final negative-result polish cannot replace a heldout run'
 val=load(S/'VALIDATION_RESULTS.json');val['registered_conditions_not_run']=protocol['validation']['conditions'];val['reason']='all O/R/OR motion-force acceptance PASS but none meet frozen>=0.5% total force-gain discovery gate; no validation dispatch or candidate reselection';val['old_host_validation_preserved']=dict(package='m2_coordination_space_exploration_v1',PASS=0,denominator=2);save(S/'VALIDATION_RESULTS.json',val)
 from report import main as report_main
 report_main()
 report=S/'REPORT.md';text=report.read_text();text=text.replace('随后commissioning beta/residual/geometry、TASK入口与native activation/等待机会均不同。','随后commissioning beta/residual/geometry、TASK入口与native activation/等待机会均不同。五个candidate/B-zero对照的早期force差都早于首个aligned estimator更新，初始population beta/residual相同；后续模型拟合差不能作为已证实的最早外生原因。')
 text=text.replace('2×2交互收益 G_OR−G_O−G_R=', '2×2交互收益近似为0，本固定组合呈数值上的近似加性。G_OR−G_O−G_R=')
 text=text.replace('STOP。保护核验及进程退出后停止；无自动后续工作。','![Matched scientific force and motion](MATCHED_FORCE_MOTION.png)\n\nSTOP。保护核验及进程退出后停止；无自动后续工作。')
 report.write_text(text)
 save(S/'FINAL_POLISH.json',dict(unix=time.time(),scope='proposal lineage joins, failure/validation status clarification, source-clock wording and figure link; no physical or scientific parameter change',new_physical_attempts=0))
 print(json.dumps(dict(proposal_lineages=len(snapshots),scientific_parameter_change=False)),flush=True)
if __name__=='__main__':main()
