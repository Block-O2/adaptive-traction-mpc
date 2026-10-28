"""Allocate finite comparison budgets from measured server throughput."""
from pathlib import Path
import json,time,copy
import numpy as np
from acl2_shared import P,R,read,put,sha,utc,records,decision
def main():
 gate=read('audit/RETIMED_INTERFACE_GATE.json')
 if not gate['new_modes_executable']:
  put('CORE_ALLOCATION_BLOCKED.json',dict(utc=utc(),reason='RETIMED_INTERFACE_NOT_FULLY_EXECUTABLE',gate=gate));return
 A=read('ACTIVATION.json');base=read('history/RECOVERY_TEST_PLAN.json');strong=[.8245887463260377,-.9835625245511301]
 # Public completed causal-reference export; native/evaluation Human states
 # are intentionally absent from this optimizer input archive.
 ident='RETIMED_STRONG';raw=R/'source/results'/ident
 su=json.loads((raw/'summary.json').read_text())
 with np.load(raw/'trace.npz') as z:
  idx=z['stage']=='TASK';t=z['time_s'][idx];q=z['reference_q_rad'][idx];v=z['reference_dq_rad_s'][idx];a=z['reference_ddq_rad_s2'][idx]
 phase=np.full(len(t),'OUTBOUND',dtype='<U10')
 for tr in su['task']['phase_transitions']:
  if tr['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=tr['time_s']-1e-9]=tr['to']
 np.savez_compressed(P/'history/CAUSAL_STRONG_REFERENCE_TEMPLATE.npz',time_s=t,q=q,dq=v,ddq=a,phase=phase)
 put('audit/STRONG_CAUSAL_TEMPLATE_EXPORT.json',dict(utc=utc(),source_trace_sha256=sha(raw/'trace.npz'),output_sha256=sha(P/'history/CAUSAL_STRONG_REFERENCE_TEMPLATE.npz'),allowlist=['time_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','phase'],future_candidate_truth_used=False,completed_public_prior=True))
 from acl2_proxy import build
 build()
 events=records();starts=[r for r in events if r['event']=='START' and not r['id'].endswith('_parent')]
 deltas=[b['unix']-a['unix'] for a,b in zip(starts,starts[1:]) if a.get('group')==b.get('group') and 20<b['unix']-a['unix']<600]
 measured=float(np.median(deltas));per=max(30.,measured*1.10);available=A['t0_unix']+7.8*3600-time.time()-600
 coordinate_per=8;ppo_episodes=64
 feasible=[n for n in [32,48,64] if (3*n+ppo_episodes+2*coordinate_per+14)*per<=available]
 n=max(feasible) if feasible else 32
 if not feasible:ppo_episodes=max(32,min(64,8*int((available/per-3*n-2*coordinate_per-14)//8)))
 allocations=dict(utc=utc(),median_complete_branch_start_interval_s=measured,planning_s_per_attempt=per,remaining_development_seconds=available,main_attempts_per_arm=n,PPO_max_training_episodes=ppo_episodes,coordinate_attempts_per_arm=coordinate_per,locked_validation_time_reserve_s=A['hard_stop_unix']-(A['t0_unix']+7.8*3600),local_and_global_deadlines_remain_authoritative=True,not_a_fixed_WSL_estimate=True)
 put('CORE_ALLOCATION_LOCK.json',allocations)
 def register(group,algorithm,order,extra,branches):
  cond=copy.deepcopy(base['condition']);cond['name']=group;c=dict(group=group,condition=cond,B=base['arms'][0],H150=base['arms'][1],algorithm=algorithm,mode='development',family='modal8_retimed',center_legacy=strong,interface_gate='audit/RETIMED_INTERFACE_GATE.json',local_stop_unix=A['t0_unix']+8.0*3600,**extra)
  put('jobs/'+group+'_CONFIG.json',c);put('runtime/'+group+'_TEST_PLAN.json',dict(condition=cond,arms=base['arms']))
  timeout=min(int(branches*per*1.30+600),int(A['hard_stop_unix']-time.time()-600))
  put('queue/'+order+'_'+group+'.json',dict(id=order+'_'+group,script='acl2_worker_owned.py',args=['jobs/'+group+'_CONFIG.json'],timeout_s=timeout,latest_start_unix=A['t0_unix']+7.3*3600,requires=['CORE_ALLOCATION_LOCK.json']))
 register('CORE','acl2_search','006',dict(checkpoints=[k for k in [16,32,48,64] if k<=n],search_seed=2026102209),3*n+4)
 register('PPO_SCRATCH','acl2_ppo','007',dict(train_episodes=ppo_episodes,batch_size=8,checkpoints=[k for k in [16,32,48,64,96,128] if k<=ppo_episodes],epochs=8,mean_lr=.01,std_lr=.002,ppo_seed=2026102211),ppo_episodes+8)
 register('COORDINATE','acl2_coordinate_search','008',dict(per_arm=coordinate_per),2*coordinate_per+3)
 put('PPO_REWARD_CONTRACT.json',dict(utc=utc(),source_sha256=sha(P/'source/acl2_ppo.py'),new_semantics=True,actor='8 pre-tanh mean and log-std parameters for one fixed causal context; scalar value',initial_mu=[0.]*8,initial_std=[.2]*8,scratch_base='same public strong fixed plan as every other method',complete_qualified_reward='5*tanh((same-chain strong JF - actual full JF)/5), strictly rank-preserving',complete_unqualified_reward='-10-min(5,max(0,actual original-motion ratio -1))',incomplete_reward=-20.,objective='retain complete original qualification and reduce full JF; original scorer unchanged',ratio_clip=.2,KL_early_stop=.03,pre_tanh_entropy_coefficient=.002,logSTD_projection='[log(.05),log(.7)] after Adam, never clipping sampled executed actions',minibatch='one complete generation of up to8 whole tasks; no pending old-policy samples',one_RL_decision_per_episode=True))
 decision('Measured throughput can support a competitive finite same-space comparison','Allocate direct/physics/learning, scratch PPO and same-family coordinates',allocations,'Retimed execution gate passed; engineering priors are shared, own-arm optimization feedback isolated','Run main fixed checkpoints and preserve locked-validation time',['CORE_ALLOCATION_LOCK.json','PPO_REWARD_CONTRACT.json','audit/RETIMED_INTERFACE_GATE.json'])
 print('CORE_ALLOCATED',json.dumps(allocations),flush=True)
if __name__=='__main__':main()
