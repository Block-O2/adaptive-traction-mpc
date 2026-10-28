from pathlib import Path
import json, shutil, os, time, hashlib
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
S=Path('/home/hank/ihear-lab/autonomous_learning_smoothness_v7/runtime');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_lowforce_repair_explore_10h_v1_review');C=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_lowforce_repair_explore_10h_v1_control')
def load(n):return json.loads((S/n).read_text())
def put(n,x):
 p=S/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n');t.replace(p)
x=load('SEARCH_AND_VALIDATION.json');ev=x['all_evaluations'];dev=x['development'];val=[r for r in ev if r['id'].startswith(('V1_','V2_','V3_'))];best=x['best_development'];chains=load('REPAIR_CHAIN_SUMMARY.json')['rows'];figdir=S/'figures';plt.rcParams.update({'font.size':9,'axes.grid':True})
fig,ax=plt.subplots(figsize=(8,4.5))
for cid,label in [('C4_1_5','C4: qualified'),('NATIVE_SCALAR_18','New best: qualified'),('NATIVE_SCALAR_01','Motion margin: qualified'),('repair2_2_0','High gain: motion FAIL (diagnostic)')]:
 rr=[r for r in val if r['candidate_id']==cid];ok=all(r['comparison']['acceptance_pass'] for r in rr)
 ax.plot([int(r['id'][1]) for r in rr],[r['comparison']['gain_percent'] for r in rr],marker='o' if ok else 'x',ls='-' if ok else '--',label=label)
ax.set(xticks=[1,2,3],xticklabels=['V1','V2','V3'],ylabel='Full TASK force gain vs own B (%)',title='Frozen candidates; same known Human, new legal prefixes');ax.axhline(.5,color='grey',ls=':');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(figdir/'heldout_effect.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(10,4.5))
def family(stage):return 'Reference' if stage=='REFERENCE' else 'Mechanism' if stage.startswith('MECHANISM') else 'Repair' if stage.startswith('REPAIR') else 'Reexploration'
colors={'Reference':'#777777','Mechanism':'#da8b00','Repair':'#007daa','Reexploration':'#a0459e'}
for group,color in colors.items():
 rr=[r for r in dev if family(r['stage'])==group]
 for ax in axs:ax.scatter([r['continuous_constraints']['worst_ratio'] for r in rr],[r['comparison']['gain_percent'] for r in rr],s=18,c=color,label=group,alpha=.8)
for chain in chains:
 before=next(r for r in dev if r['id']=='baseline_'+chain['seed']);after=next(r for r in dev if r['candidate_id']==chain['repair']);a=(before['continuous_constraints']['worst_ratio'],before['comparison']['gain_percent']);b=(after['continuous_constraints']['worst_ratio'],after['comparison']['gain_percent'])
 axs[0].annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#333333',lw=.8,alpha=.75))
for ax in axs:
 ax.axvline(1,color='black',ls='--');ax.axhline(2,color='grey',ls=':');ax.axhline(5,color='grey',ls=':');ax.set(xlabel='Worst normalized constraint (1 = gate)',ylabel='Full TASK force gain vs matched B (%)')
axs[0].set_title('Development; arrows = chain representatives');axs[1].set(xlim=(.90,1.16),ylim=(.45,1.8),title='Boundary detail (same points)');axs[0].legend(fontsize=7,loc='upper left')
bx=best['continuous_constraints']['worst_ratio'];by=best['comparison']['gain_percent'];axs[1].scatter([bx],[by],s=90,marker='*',c='black');axs[1].annotate('New best',xy=(bx,by),xytext=(.912,1.55),arrowprops=dict(arrowstyle='->',lw=.8),fontsize=8)
fig.tight_layout();fig.savefig(figdir/'repair_tradeoff.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4.5))
for ident,label in [('baseline_C4_1_5','C4: qualified'),('recovery2_Frozen_M2','M2: motion FAIL'),('baseline_C2_pair_1_2','C2: motion FAIL'),(best['id'],'New best: qualified')]:
 r=next(r for r in ev if r['id']==ident);seq=r['actual_execution_signature'];ax.scatter([z[3] for z in seq],[z[2][0].get('delta',0) for z in seq],label=label)
ax.set(xlabel='First actual native execution time (s)',ylabel='Native differential (normalized progress)',title='Actually activated nonzero plans; original issued slots');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(figdir/'actual_execution.png',dpi=150);plt.close(fig)
report=(S/'REPORT.md').read_text();report+=f"\n最终资源补充：新包约{load('PACKAGE_VERIFICATION.json')['package_bytes']/2**30:.2f} GiB，略超过建议12 GiB但低于20 GiB硬限；全部新raw保留。最后资源采样宿主D空余{load('PACKAGE_VERIFICATION.json')['resources'][-1]['D_free_bytes']/2**30:.2f} GiB。\n";(S/'REPORT.md').write_text(report)
# Preserve the continuation and analysis scripts, hash their exact versions for reproducibility.
evidence=S/'code/closeout_evidence';evidence.mkdir(exist_ok=True)
version={}
for n in ['validation_only_owner.py','closeout.py','qa_finish.py']:
 shutil.copy2(C/n,evidence/n);version[n]=hashlib.sha256((C/n).read_bytes()).hexdigest()
p=load('PROTOCOL_AND_ATTEMPTS.json');p['continuation_and_closeout_versions']=version;put('PROTOCOL_AND_ATTEMPTS.json',p)
v=load('PACKAGE_VERIFICATION.json');v['final_visual_QA']='five figures inspected; FAIL diagnostics explicitly labelled; no smoothing or evaluation change';v['closeout_elapsed_s']=time.time()-load('SEARCH_PROTOCOL.json')['t0_unix'];v['time_elapsed_s']=v['closeout_elapsed_s'];v['hard_time_limit_pass']=v['closeout_elapsed_s']<=36000;v['package_bytes']=sum(p.stat().st_size for p in S.rglob('*') if p.is_file());v['package_suggested_12GiB_exceeded']=v['package_bytes']>12*2**30;v['storage_hard_limit_pass']=v['package_bytes']<20*2**30
owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name)==os.getpid():continue
 try:
  cmd=(q/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if str(S)+'/code/' in cmd:owned.append(dict(pid=int(q.name),cmd=cmd))
 except (FileNotFoundError,PermissionError):pass
assert not owned;v['final_process_absence']=owned;v['final_process_check_unix']=time.time();put('PACKAGE_VERIFICATION.json',v)
put('PROGRESS.json',dict(unix=time.time(),phase='STOPPED',status='COMPLETE_WITH_RECORDED_DEVIATIONS',attempts=v['attempt_count'],no_new_dispatch=True,no_followup=True))
for n in ['REPORT.md','PACKAGE_VERIFICATION.json','PROTOCOL_AND_ATTEMPTS.json','PROGRESS.json','FINALIZED.json']:shutil.copy2(S/n,W/n)
shutil.copytree(figdir,W/'figures',dirs_exist_ok=True)
print(json.dumps(dict(verification_integrals=load('INDEPENDENT_DERIVED_CHECKS.json')['denominator'],verification_dense=sum('dense_acceleration_error' in r for r in load('INDEPENDENT_DERIVED_CHECKS.json')['rows']),git_equal=v['git_exact_state_equal'],changed_protected=v['protected_reused_source_bytes_changed'],elapsed_h=v['time_elapsed_s']/3600,package_GiB=v['package_bytes']/2**30,owned_processes=owned),ensure_ascii=False))
