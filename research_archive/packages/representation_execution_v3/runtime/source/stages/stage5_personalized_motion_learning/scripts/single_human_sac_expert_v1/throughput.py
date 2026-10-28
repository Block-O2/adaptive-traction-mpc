"""Benchmark final environment and SB3 CUDA mechanics; never produce formal policy evidence."""
import sys,time,json,subprocess,threading,resource,copy,os,traceback,math
import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import BaseCallback
from qualify import *
torch.set_num_threads(1)
class Resources:
    def __init__(self):self.samples=[];self.stop=threading.Event();self.thread=None
    def sample(self):
        memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        try:gpu=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],text=True,timeout=10).strip()
        except Exception as error:gpu=str(error)
        self.samples.append(dict(unix=time.time(),rss_bytes=Process().memory_info().rss,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,available_ram_bytes=int(memory['MemAvailable'].split()[0])*1024,gpu=gpu,process_cpu_s=time.process_time(),disk_written_bytes=Process().io_counters().write_bytes))
    def run(self):
        while not self.stop.wait(2.):self.sample()
    def start(self):self.sample();self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def close(self):self.stop.set();self.thread.join();self.sample()
def summarize(stage,start,cpu,steps,sim_s,resources):
    host=time.monotonic()-start;first=resources.samples[0];last=resources.samples[-1]
    return dict(stage=stage,agent_steps=steps,wall_s=host,agent_steps_s=steps/host,physics_steps_s=sim_s/.0005/host,control_steps_s=sim_s/.005/host,simulated_seconds_s=sim_s/host,task_simulated_seconds=sim_s,cpu_core_utilization_percent=100*(time.process_time()-cpu)/host,cpu_machine_percent=100*(time.process_time()-cpu)/host/os.cpu_count(),rss_bytes=last['rss_bytes'],peak_rss_bytes=max(x['peak_rss_bytes'] for x in resources.samples),disk_bytes_s=(last['disk_written_bytes']-first['disk_written_bytes'])/host,resources=resources.samples)
class CollectionCallback(BaseCallback):
    def __init__(self):super().__init__();self.sim_s=0.;self.previous_t=0.;self.episodes=[]
    def _on_step(self):
        info=self.locals['infos'][0];now=info.get('physics_task_s',info.get('duration_s',self.previous_t))
        self.sim_s+=max(0.,now-self.previous_t);self.previous_t=now
        if self.locals['dones'][0]:self.episodes.append(info);self.previous_t=0.
        return True
def distribution(xs):
    xs=np.asarray(xs,float)
    return dict(n=len(xs),mean=float(np.mean(xs)),p50=float(np.percentile(xs,50)),p90=float(np.percentile(xs,90)),p95=float(np.percentile(xs,95)),p99=float(np.percentile(xs,99)),max=float(np.max(xs)))
def env_benchmark():
    case,options=load_case_options();env=SACExpertEnv(O/'throughput/env',case,options,.02,retain_trace=False);res=Resources();res.start();start=time.monotonic();cpu=time.process_time();steps=0;sim=0.;episodes=[]
    try:
        for i in range(2):
            obs,info=env.reset(seed=20261003);previous=0.
            for k in range(1600):
                obs,reward,term,trunc,info=env.step(policy('reference',env,obs,info));steps+=1;now=info.get('physics_task_s',info.get('duration_s',previous));sim+=max(0.,now-previous);previous=now
                if term or trunc:episodes.append(info);break
    finally:env.close();res.close()
    result=summarize('env stepping without learning; compact final configuration including resets',start,cpu,steps,sim,res);result['episodes']=episodes
    result['wall_per_complete_episode_s']=float(np.mean([e['host_s'] for e in episodes if e['success']]))
    save('THROUGHPUT_ENV_RAW.json',result);return result
def sac_benchmark():
    case,options=load_case_options();env=SACExpertEnv(O/'throughput/sac',case,options,.02,retain_trace=False)
    config=json.loads((D/'SAC_TRAINING_CONFIG.json').read_text());kwargs={k:config[k] for k in ('learning_rate','batch_size','buffer_size','tau','ent_coef','target_entropy','replay_buffer_kwargs')}
    model=SAC('MlpPolicy',env,device='cuda',learning_starts=32,train_freq=1,gradient_steps=1,gamma=gamma_for(.02),policy_kwargs=dict(net_arch=[256,256]),seed=20261003,verbose=0,**kwargs)
    assert model.device.type=='cuda';res=Resources();res.start();start=time.monotonic();cpu=time.process_time();callback=CollectionCallback()
    try:
        model.learn(total_timesteps=256,callback=callback)
        result=summarize('SAC collection + CUDA optimization; nonformal integration benchmark',start,cpu,model.num_timesteps,callback.sim_s,res)
        result['benchmark_learning_starts']=32;result['formal_learning_starts']=5000;result['warmup_difference']='Mechanical benchmark starts updates early to measure CUDA compute. It is not used as formal data or initialization; final scientific environment/reward/scales/action/network/optimizer otherwise identical.'
        result['episodes']=callback.episodes;result['gradient_updates']=model._n_updates
        result['finite_parameters']=all(bool(torch.isfinite(p).all().item()) for p in model.policy.parameters())
        result['device']=str(model.device)
        result['gradient_loss_metrics']={k:float(v) for k,v in model.logger.name_to_value.items() if k.startswith('train/') and np.isscalar(v)}
        save('THROUGHPUT_SAC_RAW.json',result)
        model.save(O/'throughput/benchmark_policy_NOT_FORMAL')
        actor_gpu=model.actor;actor_cpu=copy.deepcopy(actor_gpu).to('cpu');raw=np.zeros((1,55),np.float32);profile={}
        for device,actor in (('cpu',actor_cpu),('cuda',actor_gpu)):
            tensor=torch.as_tensor(raw,device=device);durations=[]
            with torch.no_grad():
                for i in range(1100):
                    if device=='cuda':torch.cuda.synchronize()
                    ts=time.perf_counter_ns();actor(tensor,deterministic=True)
                    if device=='cuda':torch.cuda.synchronize()
                    ms=(time.perf_counter_ns()-ts)/1e6
                    if i>=100:durations.append(ms)
            profile['actor_'+device+'_ms']=distribution(durations)
        # Full chain with deterministic actor on an independent reset, no optimizer/replay update.
        obs,info=env.reset(seed=20261003)
        for k in range(100):
            action,_=model.predict(obs,deterministic=True);obs,reward,term,trunc,info=env.step(action)
            if term or trunc:break
        profile['observation_to_reference_ready_ms']=distribution([r['full_chain_ms'] for r in env.action_records])
        profile['realization_and_safety_validation_ms']=distribution([r['realization_validation_ms'] for r in env.action_records])
        profile['scope']='Initial benchmark actor, scientific host characterization; not hardware realtime qualification.'
        save('SAC_RUNTIME_PROFILE.json',profile)
        (D/'SAC_RUNTIME_PROFILE.md').write_text('# Runtime characterization\n\nCPU/GPU actor inference and observation-ready to actor/action-realization/safety/reference-ready distributions are in JSON. GPU timings synchronize explicitly. This uses the nonformal mechanical benchmark actor; repeat with best formal checkpoint at closeout. No hardware realtime claim.\n')
        return result
    finally:env.close();res.close()
def main():
    status('THROUGHPUT_AND_CUDA_QUALIFICATION')
    try:
        env=env_benchmark();sac=sac_benchmark()
        evaluation=json.loads((D/'RUN_final_reference_20ms_NATIVE.json').read_text())
        deterministic=dict(stage='Independent deterministic complete physical evaluation including retained evidence',agent_steps=evaluation['steps'],wall_s=evaluation['host_s'],agent_steps_s=evaluation['steps']/evaluation['host_s'],simulated_seconds_s=evaluation['result']['duration_s']/evaluation['host_s'],wall_per_complete_episode_s=evaluation['host_s'],peak_rss_bytes=evaluation['peak_rss_bytes'],disk_bytes_s=evaluation['disk_written_bytes']/evaluation['host_s'])
        observed=sac['agent_steps_s'];estimates={str(n):dict(hours=n/observed/3600,includes_qualification_benchmark_reset_and_optimization_mix=True,uncertainty='256-step benchmark is short; task-acquisition failures/reset frequency can change throughput materially.') for n in (100000,300000,500000,1000000,2000000)}
        save('SAC_THROUGHPUT.json',dict(status='PASS' if sac['finite_parameters'] and sac['gradient_updates']>0 else 'FAIL',environment=env,sac=sac,deterministic_evaluation=deterministic,estimates=estimates,environments=1,no_multiworker_test=True,physics='CPU MuJoCo',optimization='CUDA SB3',rss_unit='bytes'))
        (D/'SAC_THROUGHPUT.md').write_text('# Final environment throughput\n\nEnvironment stepping, actual SAC collection with CUDA gradient updates, deterministic physical evaluation and 100k/300k/500k/1M/2M estimates are in JSON. Final environment is fixed; only the nonformal benchmark learning-start threshold is 32 rather than formal 5000, to measure optimization within a bounded check. Benchmark checkpoints/data never initialize or count toward formal learning. One active environment, no parallel collection. Native physics is CPU MuJoCo. CPU, GPU/VRAM, RAM/peak RSS, write rate and completed episode wall times are separately recorded. Extrapolations are estimates, not promises.\n')
        assert sac['finite_parameters'] and sac['gradient_updates']>0
        status('ALL_QUALIFICATION_GATES_PASS',next_action='Freeze exact final contract, source/config/model hashes and bounded seed budgets; automatically begin main SB3 SAC CUDA training.')
        print(json.dumps(dict(env_steps_s=env['agent_steps_s'],sac_steps_s=observed,estimated_300k_h=estimates['300000']['hours'],gradient_updates=sac['gradient_updates'])),flush=True)
    except Exception as error:
        save('THROUGHPUT_EXCEPTION.json',dict(error=str(error),traceback=traceback.format_exc()))
        status('QUALIFICATION_STOP',status='SINGLE_HUMAN_SAC_EXPERT_V1_BLOCKED',blocker=str(error),next_action='Stop without formal training; preserve benchmark failure.')
        print(traceback.format_exc(),flush=True)
if __name__=='__main__':main()
