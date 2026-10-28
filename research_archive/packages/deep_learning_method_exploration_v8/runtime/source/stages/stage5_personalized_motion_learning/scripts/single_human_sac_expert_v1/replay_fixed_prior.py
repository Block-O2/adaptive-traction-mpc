"""Transfer the previously preregistered strongest nominal fixed hip-leading reference."""
from final_qualification import *
def run(scope):
    source=S/'results/best_known_coordination_search_v2/runs/A_sync_120_NATIVE_fixed_0/rollout_result.json'
    prior=json.loads(source.read_text());descriptor=prior['planned_segments'];case,options=load_case_options();env=SACExpertEnv(O/'comparators'/f'prior_fixed_hip_lead_{scope}',case,options,.02,scope,True)
    try:
        obs,info=env.reset(seed=20261003)
        for k in range(1600):
            items=descriptor.get(info['phase'],[]);target=env.soft_target.copy()
            if items:
                elapsed=float(obs[47]*10.);selected=next((x for x in reversed(items) if elapsed>=x['phase_elapsed_s']-1e-10),items[0]);target=np.asarray(selected['target_q_rad'])
            obs,reward,term,trunc,info=env.step(target_to_action(target,env.spec).astype(np.float32))
            if term or trunc:break
        record=metric_record(env,'prior_fixed_hip_lead_transfer',scope)
        record['source_reference']=dict(path=str(source.relative_to(R)),sha256=sha(source),historical_J_F=prior['J_F_task_n_s'],descriptor=descriptor,pattern=prior.get('pattern'))
        record['reference_semantics']='Same new-interface transfer rule as CEM comparator; prior preregistered nominal fixed hip-leading descriptor, no search or fitting in this campaign.'
        save(f'COMPARATOR_prior_fixed_hip_lead_{scope}.json',record);return record
    finally:compact_archive(env);env.close()
def main():
    rows=json.loads((D/'SAC_COMPARATOR_TABLE.json').read_text())['rows']
    for scope in ('NATIVE','MATCHED'):
        r=run(scope);rows.append(r);print(json.dumps({k:r.get(k) for k in ('name','scope','valid','J_F','duration_s')}),flush=True)
    save('SAC_COMPARATOR_TABLE.json',dict(status='PASS',rows=rows,historical_numbers_not_directly_ranked=True,strongest_simple_rule='For each scope report lowest valid J_F among current constant, old nominal, preregistered prior fixed transfer and explicit simple hip-leading comparator; all fixed before formal SAC comparisons.'))
    table('SAC_COMPARATOR_TABLE.csv',[{k:r.get(k) for k in ('name','scope','valid','J_F','force_mean','force_rms','force_peak','moment_integral','moment_peak','duration_s','clearance','physical_clearance','rejections','modification_fraction','trace','trace_sha256')} for r in rows])
if __name__=='__main__':main()
