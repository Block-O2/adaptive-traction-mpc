from pathlib import Path
import sys,json,time,gzip,traceback
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_coordination_space_exploration_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_gym import DirectOnlineSmokeEnv
def main():
    case=json.loads((S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text());c=json.loads((D/'EXPERIMENT_CONTRACT.json').read_text());options=json.loads((R/c['options_path']).read_text())
    rows=[]
    for pattern in ('deterministic','random_safe'):
        out=S/'results/adaptive_human_online_interface_v1/gym'/pattern;env=DirectOnlineSmokeEnv(out,case,options);start=time.monotonic();record=dict(pattern=pattern,seed=20261002,period_s=.02,reward='zero API smoke',training_steps=0,truth_exposed=False,observation_fields=env.observation_fields)
        try:
            obs,info=env.reset(seed=20261002);assert env.observation_space.contains(obs) and np.all(np.isfinite(obs));record['reset_pass']=True
            invalid_rejected=False
            try:env.step(np.array([2.,0.]))
            except ValueError:invalid_rejected=True
            record['invalid_action_rejected']=invalid_rejected;record['observation_shape']=list(obs.shape)
            rng=np.random.default_rng(20261002);terminated=truncated=False
            for k in range(1600):
                t=info.get('physics_task_s',0.)
                action=np.zeros(2)
                if .5<=t<.9:
                    action=np.array([-.4,-.1]) if pattern=='deterministic' else rng.uniform(-.1,.1,2)
                assert env.action_space.contains(action)
                obs,reward,terminated,truncated,info=env.step(action)
                assert env.observation_space.contains(obs) and np.all(np.isfinite(obs)) and reward==0.
                if terminated or truncated:break
            record.update(steps=env.step_count,terminated=terminated,truncated=truncated,final=info,status='PASS' if info.get('physics_complete') and terminated and not truncated else 'FAILED_OR_TRUNCATED',post_terminal_step_rejected=False)
            try:env.step(np.zeros(2))
            except RuntimeError:record['post_terminal_step_rejected']=True
        except Exception as error:record.update(status='EXCEPTION',error=str(error),traceback=traceback.format_exc())
        finally:env.close()
        record['host_s']=time.monotonic()-start;rows.append(record)
        for p in out.rglob('*.json'):
            with gzip.open(str(p)+'.gz','wb',compresslevel=3) as f:f.write(p.read_bytes())
            p.unlink()
        print(json.dumps({k:record.get(k) for k in ('pattern','status','steps','terminated','truncated','host_s','error')}),flush=True)
    (D/'DIRECT_RL_GYM_READINESS.json').write_text(json.dumps(dict(status='SMOKE_PASS' if all(x['status']=='PASS' for x in rows) else 'PARTIAL',runs=rows,no_training=True,reward_contract_ready=False,serious_SAC_campaign_ready=False,reason='Physical API smoke only; scientific reward, throughput, normalization and SAC experiment contract remain unqualified.'),indent=2)+'\n')
if __name__=='__main__':main()
