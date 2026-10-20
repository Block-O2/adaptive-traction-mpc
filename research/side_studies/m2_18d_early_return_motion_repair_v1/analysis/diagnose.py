from pathlib import Path
import os,json,time,ast
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
A=P.parent/'m2_18d_w1_d_qualification_v1'
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
old=(A/'analysis/diagnose.py').read_text();tree=ast.parse(old)
exec(ast.get_source_segment(old,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load')))
historical_load=load
def load(root,ident):
 z=historical_load(root,ident)
 for e in z['events']:
  d=z['su']['decisions'][e['index']];comp=d.get('rolling_composite')
  e['splice']=e['activation']+(float(comp['splice_elapsed_s']) if comp else 0.)
  e['rolling_composite']=comp
 return z
Z={k:load(A,'W1_'+k) for k in ['B','T','D']};B=Z['B'];D=Z['D'];n=len(D['t']);budget=int(np.ceil(.05*(n+400)))
vlim=B['metric']['motion']['raw']['full']['velocity_deg_s']['p95_abs'][1]*1.1;alim=B['metric']['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'][1]*1.1;exlim=B['metric']['dose']['excursion_deg'][1]+.5
events=[]
for e in D['events']:
 if e['phase']!='RETURN':continue
 t=e['request'];ix=D['t']<=t+1e-8;v=np.abs(np.rad2deg(D['true_dq_rad_s'][:,1]));a=np.abs(np.rad2deg(D['acceleration_rad_s2'][:,1]));q=np.rad2deg(D['true_q_rad'][:,1]);exc=float(np.ptp(q[ix]));events.append({**e,'knee_v_high_before_request':int(np.sum((v>vlim)&ix)),'knee_a_high_before_request':int(np.sum((a>alim)&ix)),'knee_excursion_before_request_deg':exc,'v_p95_irreversible_lower_bound':bool(np.sum((v>vlim)&ix)>budget),'a_p95_irreversible_lower_bound':bool(np.sum((a>alim)&ix)>budget),'excursion_irreversible':bool(exc>exlim)})
out=dict(status='HISTORICAL_NATIVE_ONLY_NO_NEW_PHYSICS',unix=time.time(),source=str(A),original_full_matched_B_relative_limits=dict(knee_v_p95=vlim,knee_a_p95=alim,knee_excursion=exlim,max_high_samples_with_duration_tolerance=budget),RETURN_events=events,background=read(A/'derived/BACKGROUND_CONTROL_EFFECTS.json'),terminal_lower_bounds=read(A/'derived/W1_D_IRREVERSIBLE_PREFIX_BOUNDS.json'))
put('derived/EARLY_RETURN_DIAGNOSIS.json',out)
fig,axs=plt.subplots(11,1,figsize=(15,25),sharex=True,layout='constrained')
for tag,co in [('B','#777777'),('T','#0072b2'),('D','#d55e00')]:
 z=Z[tag];t=z['t'];tf=z['tf'];v=np.rad2deg(z['true_dq_rad_s'][:,1]);a=np.rad2deg(z['acceleration_rad_s2'][:,1]);q=np.rad2deg(z['true_q_rad'][:,1]);j=np.rad2deg(z['jerk_rad_s3'][:,1]);exc=np.maximum.accumulate(q)-np.minimum.accumulate(q)
 axs[0].plot(tf,np.rad2deg(z['rv'][:,1]),c=co,ls='--');axs[0].plot(t[::8],v[::8],c=co,label=tag)
 axs[1].plot(t[::4],a[::4],c=co);axs[2].plot(t[::8],j[::8],c=co);axs[3].plot(t,np.cumsum(abs(v)>vlim),c=co);axs[3].plot(t,np.cumsum(abs(a)>alim),c=co,ls='--');axs[4].plot(t,exc,c=co);axs[5].plot(tf,z['f'],c=co);axs[6].plot(tf,np.r_[0,np.cumsum(z['f'][:-1]*np.diff(tf))],c=co);axs[7].plot(tf,np.linalg.norm(np.rad2deg(z['truth'][:,:2]-z['rq']),axis=1),c=co);axs[8].plot(tf,z['m'],c=co)
 tr=np.load(A/'source/results'/('W1_'+tag)/'trace.npz');ix=tr['stage']=='TASK';axs[9].plot(tf,np.linalg.norm(tr['robot_torque_component_allocator_nm'][ix],axis=1),c=co)
 for k,mark in enumerate(['|','o','x']):axs[10].scatter([e[['request','activation','splice'][k]] for e in z['events']],[k+.12*list(Z).index(tag)]*len(z['events']),c=co,marker=mark,s=16)
for ax,lab in zip(axs,['Knee dq deg/s\nsolid actual, dash ref','Knee raw a deg/s²','Knee raw jerk deg/s³','High sample count\nsolid v, dash a','Cumulative excursion deg','Force N','Cumulative J_F N s','Tracking norm deg','Moment norm Nm','Allocator torque norm Nm','Request / activation / splice']):
 ax.set_ylabel(lab);ax.grid(alpha=.2);ax.set_xlim(0,19.03)
 for e in events:ax.axvline(e['request'],c='.6',lw=.6)
 ax.axvspan(events[1]['splice'],events[1]['splice']+events[1]['duration'],color='#009e73',alpha=.12)
axs[3].axhline(budget,c='r',ls=':');axs[4].axhline(exlim,c='r',ls=':');axs[0].legend(ncol=3);axs[-1].set_xlabel('Task time (s); green = proposed RETURN1 intervention interval; red = complete matched-B diagnostic bounds')
fig.suptitle('W1 B/T/D native historical evidence — early RETURN repair rationale\nNo new physics; instantaneous exceedance is not a complete-task p95 failure')
fig.savefig(P/'figures/W1_early_return_timeline.png',dpi=140);plt.close(fig)
lines=['# W1 早期 RETURN 运动诊断（物理前）','','历史来源与 SHA 保护见 audit/HISTORICAL_MANIFESTS_VERIFIED.json；本文件不重跑诊断 physics。所有时间相对完整 TASK。','', '|槽|request|activation|splice|duration|此前 v 高样本|此前 a 高样本|此前膝 excursion°|','|---|---:|---:|---:|---:|---:|---:|---:|']
for e in events:lines.append(f"|RETURN{e['slot']}|{e['request']:.3f}|{e['activation']:.3f}|{e['splice']:.3f}|{e['duration']:.3f}|{e['knee_v_high_before_request']}|{e['knee_a_high_before_request']}|{e['knee_excursion_before_request_deg']:.6f}|")
lines+=['','## 直接物理观察','W1 D 完整 task/safety/causal PASS、motion FAIL。首段膝速度高值约 11.992–12.473 s，落在 RETURN1；其前缀尚未达到不可逆 p95/excursion 下界。RETURN5 请求16.540 s时，既有计数和excursion已超可补救下界；16.700 s终末峰值不是全部失败的充分解释。加速度高样本更早已在OUTBOUND出现；进入RETURN并非原因识别。','', '## 可验证背景影响','R0 固定W1 OUTBOUND、移除RETURN0背景后T/D通过；但某些绝对p95和excursion反而高于W1，完整B分母也变化。O0固定W1 RETURN、更换OUTBOUND后，T/D RETURN实际轨迹几乎重合，完整p95资格仍因OUTBOUND负担及匹配B改变；D终末尖峰仍存在。这识别整个背景规则的条件效应，尚不能分解allocator等中介或完整交互。','', '## 源码与执行合同','优先干预RETURN1的选后suffix duration，保留其原选target及pass velocity，使用原plan_fixed_duration_reference_contract重建quintic与独立证书。完整phase9.005/1.020/9.005 s合同通过原endpoint等待保持，不能缩短任务。桥接40ms、lifecycle100ms、当前状态和source age准入、fallback均沿原代码执行。原接口已支持，不扩展正式安全语义。','', '## 数学假设与未识别','固定端点速度的延时可能降低内部速度峰，但不保证所有极值单调改善，也可能改变后续选择、终末反馈及力矩。因此先重做连续性、ROM、几何、力学、当前准入预检，再以完整配对physics检验。D RETURN2/3规则不变，后续活态选择允许因果响应。','p95是同条件完整B的统计比，不是绝对临床阈值；高值计数是不可逆下界工具，不替代原quantile门。到候选真实splice之前的历史、最大值、累计行程、excursion不能被后段删除；p95可修复性还依赖剩余样本预算。任何模型预检都不构成物理通过证据。','原reference近零而16.695s allocator/torque脉冲先于Human峰值只是相关序列，尚未证明唯一机制。','', '完整事件/计数见 derived/EARLY_RETURN_DIAGNOSIS.json；共同图见 figures/W1_early_return_timeline.png。']
(P/'W1_EARLY_RETURN_DIAGNOSIS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(status='PASS',RETURN_events=events)),flush=True)
