from pathlib import Path
import os,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
A=P.parent/'m2_18d_t_second_round_coordination_v1'
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def load(root,ident):
 z=np.load(root/'motion_series'/(ident+'.npz'));tr=np.load(root/'source/results'/ident/'trace.npz');ix=tr['stage']=='TASK';origin=tr['time_s'][ix][0]
 out={k:z[k].copy() for k in z.files};out['t']=out['time_s']-origin;out['tf']=tr['time_s'][ix]-origin
 for key,field in [('f','physical_cuff_force_world_n'),('m','physical_cuff_moment_world_nm'),('rq','reference_q_rad'),('rv','reference_dq_rad_s'),('truth','evaluation_only_human_state_rad_rad_s')]:out[key]=tr[field][ix].copy()
 out['f']=np.linalg.norm(out['f'],axis=1);out['m']=np.linalg.norm(out['m'],axis=1);out['metric']=read(root/'reports'/(ident+'_MEASURED.json'));out['su']=read(root/'source/results'/ident/'summary.json');out['origin']=float(origin);out['trace_fields']=tr.files
 out['events']=[];counts={}
 for lr in out['su']['learning_records']:
  d=out['su']['decisions'][lr['decision_index']];ph=d['phase'];slot=counts.get(ph,0);counts[ph]=slot+1;sc=lr['selected_plan']['execution_screen'];schedule=lr['selected_plan']['schedule']
  out['events'].append(dict(index=lr['decision_index'],phase=ph,slot=slot,request=d['decision_request_time_s']-origin,activation=lr['start_time_s']-origin,splice=lr['start_time_s']-origin+.04,end=lr['end_time_s']-origin,duration=schedule['duration_s'],target=schedule.get('target_q_rad'),activated=lr.get('selected_plan_activated'),terminal=sc.get('terminal_duration_intervention'),posture=sc.get('second_round_posture'),residual=sc.get('coordination_residual_v2'),screen_keys=list(sc)))
 return out
Z={k:load(A,'W1_'+k) for k in ['B','E','T']};V=load(A,'dev_T');D=load(A,'refine_P_corridor');B=Z['B'];T=Z['T'];q=np.rad2deg(T['true_q_rad']);qb=np.rad2deg(B['true_q_rad']);n=len(q)
def intervals(t,mask):
 idx=np.flatnonzero(mask)
 if not len(idx):return []
 parts=np.split(idx,np.flatnonzero(np.diff(idx)>1)+1)
 return [dict(start=float(t[a[0]]),end=float(t[a[-1]]),samples=len(a),duration_s=float(len(a)*.00025)) for a in parts]
detail={}
for key,signal in [('velocity_deg_s','true_dq_rad_s'),('acceleration_deg_s2','acceleration_rad_s2')]:
 x=abs(np.rad2deg(T[signal][:,1]));xb=abs(np.rad2deg(B[signal][:,1]));limit=B['metric']['motion']['raw']['full'][key]['p95_abs'][1]*1.1;over=x>limit+1e-7;cum=np.cumsum(over);budget=int(np.ceil(.05*(n+400)))
 cut=next(e['request'] for e in T['events'] if e['phase']=='RETURN' and e['slot']==2)
 extra=over&(xb<=limit+1e-7);first_extra=None if not np.any(extra) else float(T['t'][np.flatnonzero(extra)[0]])
 detail[key]=dict(B_full_p95=B['metric']['motion']['raw']['full'][key]['p95_abs'][1],T_full_p95=float(np.quantile(x,.95)),limit=limit,first_exceedance=float(T['t'][np.flatnonzero(over)[0]]),first_T_above_limit_B_not=first_extra,first_exceedance_B_also_above=bool(xb[np.flatnonzero(over)[0]]>limit),intervals=intervals(T['t'],over),over_samples_by_phase={ph:int(np.sum(over&(T['phase']==ph))) for ph in ['OUTBOUND','HOLD','RETURN']},B_over_samples_by_phase={ph:int(np.sum((xb>limit+1e-7)&(T['phase']==ph))) for ph in ['OUTBOUND','HOLD','RETURN']},pre_D_samples=int(np.sum(over&(T['t']<=cut))),full_over_samples=int(over.sum()),irreversible_count_budget_with_duration_tolerance=budget,irreversible_crossing_task_s=None if cum[-1]<=budget else float(T['t'][np.flatnonzero(cum>budget)[0]]),peak_task_s=float(T['t'][np.argmax(x)]),peak=float(x.max()))
exc=np.maximum.accumulate(q,axis=0)-np.minimum.accumulate(q,axis=0);excb=np.maximum.accumulate(qb,axis=0)-np.minimum.accumulate(qb,axis=0);exlimit=np.ptp(qb,axis=0)+.5
excinfo=dict(full_T=np.ptp(q,axis=0).tolist(),full_B=np.ptp(qb,axis=0).tolist(),difference=(np.ptp(q,axis=0)-np.ptp(qb,axis=0)).tolist(),first_exceedance_of_final_B_excursion_plus_tolerance=[None if not np.any(exc[:,j]>exlimit[j]+1e-7) else float(T['t'][np.flatnonzero(exc[:,j]>exlimit[j]+1e-7)[0]]) for j in range(2)],extrema_T=[dict(min_task_s=float(T['t'][np.argmin(q[:,j])]),max_task_s=float(T['t'][np.argmax(q[:,j])]),min=float(q[:,j].min()),max=float(q[:,j].max())) for j in range(2)],pre_D_excursion=np.ptp(q[T['t']<=cut],axis=0).tolist())
diff={}
for tag,other in [('W1_E_vs_T',Z['E']),('V1_T_vs_W1_T',V)]:
 diff[tag]={}
 for field in ['true_q_rad','true_dq_rad_s','acceleration_rad_s2']:
  a=T[field];b=other[field];err=np.max(abs(a-b),axis=1);ii=np.flatnonzero(err>1e-10)
  diff[tag][field]=dict(max_abs_deg=float(np.rad2deg(err.max())),first_task_s=None if not len(ii) else float(T['t'][ii[0]]),by_phase_max_deg={ph:float(np.rad2deg(err[T['phase']==ph].max())) for ph in ['OUTBOUND','HOLD','RETURN']})
hist=[]
for study,conds in [('m2_18d_terminal_response_repair_v1',['N2','U1']),('m2_18d_terminal_expanded_prefix_validation_v1',['V1','V2']),('m2_18d_t_second_round_coordination_v1',['W1'])]:
 root=P.parent/study;plan=read(root/'RUN_PLAN.json')
 for c in conds:
  for arm in ['B','E','T']:
   m=read(root/'reports'/(c+'_'+arm+'_MEASURED.json'));hist.append(dict(condition=c,arm=arm,source=str(root),J_F=m['J_F_N_s'],velocity_p95=m['motion']['raw']['full']['velocity_deg_s']['p95_abs'],acceleration_p95=m['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'],excursion=m['dose']['excursion_deg'],tracking=m['tracking_RMS_deg'],moment=m['moment_integral_Nm_s'],clearance=m['clearance'],task=m['axes'],safety=m['native_physical_audit']['pass_']))
out=dict(status='HISTORICAL_DIAGNOSIS_COMPLETE_NO_NEW_PHYSICS',unix=time.time(),source=str(A),p95=detail,excursion=excinfo,differences=diff,W1_events={k:z['events'] for k,z in Z.items()},V1_T_events=V['events'],V1_D_events=D['events'],historical_conditions=hist,trace_fields=T['trace_fields'],summary_keys=list(T['su']),first_D_request_task_s=cut,causal_limit='W1 changes OUTBOUND0 and RETURN0 jointly. Timing localization is descriptive; no individual-factor causal attribution before matched controls.',observed_same_pre_D_bounds_not_irreversible=all(x['pre_D_samples']<=x['irreversible_count_budget_with_duration_tolerance'] for x in detail.values()) and all(np.array(excinfo['pre_D_excursion'])<=exlimit))
put('audit/W1_DIAGNOSTIC_NUMBERS.json',out)
signals={}
for tag in ['B','E','T']:
 tr=np.load(A/'source/results'/('W1_'+tag)/'trace.npz');ix=tr['stage']=='TASK';tt=tr['time_s'][ix]-T['origin'];fields={}
 for field in ['robot_torque_component_allocator_nm','robot_torque_component_clipping_nm','cr12_actuator_command_nm','allocated_wrench_world','session_shank_clearance_m','dev_d_session_envelope_clearance_m','dev_d_measured_sleeve_gap_m','shank_bed_contact_evaluation_only']:
  x=tr[field][ix];fields[field]={}
  for ph,lo,hi in [('OUTBOUND',0,9.005),('HOLD',9.005,10.025),('RETURN',10.025,19.031)]:
   y=x[(tt>=lo-1e-8)&(tt<hi-1e-8)];finite=y[np.isfinite(y)] if y.dtype.kind in 'fc' else y
   fields[field][ph]=dict(min=None if not finite.size else float(np.min(finite)),max=None if not finite.size else float(np.max(finite)),rms=None if not finite.size else float(np.sqrt(np.mean(finite.astype(float)**2))),nonzero_count=int(np.count_nonzero(finite)))
 signals[tag]=fields
put('audit/W1_COMPENSATION_SIGNALS.json',dict(status='OBSERVATIONAL_ONLY',signals=signals,interpretation='Clipping, allocator, tracking, clearance and contact are post-treatment signals; their co-occurrence does not identify mediation or a unique cause.'))
fig,ax=plt.subplots(11,1,figsize=(15,24),sharex=True,layout='constrained')
for tag,co in [('B','#666666'),('E','#d95f02'),('T','#0072b2')]:
 z=Z[tag];t=z['t'];tf=z['tf'];v=np.rad2deg(z['true_dq_rad_s'][:,1]);a=np.rad2deg(z['acceleration_rad_s2'][:,1]);qq=np.rad2deg(z['true_q_rad'][:,1]);ref=np.rad2deg(z['rq'][:,1]);rfv=np.rad2deg(z['rv'][:,1]);truth=np.rad2deg(z['truth'][:,:2]);tracking=np.linalg.norm(truth-np.rad2deg(z['rq']),axis=1)
 ax[0].plot(tf,z['f'],c=co,label=tag);ax[1].plot(tf,np.r_[0,np.cumsum(z['f'][:-1]*np.diff(tf))],c=co);ax[2].plot(t[::8],qq[::8],c=co);ax[2].plot(tf,ref,c=co,ls='--',alpha=.45);ax[3].plot(t[::8],v[::8],c=co);ax[3].plot(tf,rfv,c=co,ls='--',alpha=.45);ax[4].plot(t[::4],a[::4],c=co)
 ax[5].plot(t,np.cumsum(abs(v)>detail['velocity_deg_s']['limit']),c=co);ax[5].plot(t,np.cumsum(abs(a)>detail['acceleration_deg_s2']['limit']),c=co,ls='--');ax[6].plot(t,(np.maximum.accumulate(np.rad2deg(z['true_q_rad']),axis=0)-np.minimum.accumulate(np.rad2deg(z['true_q_rad']),axis=0))[:,1],c=co)
 ax[7].plot(tf,tracking,c=co);ax[8].plot(tf,z['m'],c=co)
 for i,(key,mark) in enumerate([('request','|'),('activation','o'),('splice','x')]):ax[10].scatter([e[key] for e in z['events']],np.full(len(z['events']),i+.14*list(Z).index(tag)),c=co,marker=mark,s=18)
ax[9].plot(T['t'],exc[:,1]-excb[:,1],label='T - matched B',c='#0072b2');ax[9].axhline(.5,c='r',ls=':');ax[4].axhline(detail['acceleration_deg_s2']['limit'],c='r',ls=':');ax[4].axhline(-detail['acceleration_deg_s2']['limit'],c='r',ls=':');ax[3].axhline(detail['velocity_deg_s']['limit'],c='r',ls=':');ax[3].axhline(-detail['velocity_deg_s']['limit'],c='r',ls=':');ax[5].axhline(.05*n,c='r',ls=':')
for axis,label in zip(ax,['Force N','Cumulative J_F N s','Knee q deg actual/ref','Knee dq deg/s actual/ref','Knee raw acceleration deg/s2','Cumulative high samples\nsolid v / dashed a','Cumulative knee excursion deg','Tracking norm deg','Moment norm Nm','Excursion delta deg','Request / activation / splice']):
 axis.set_ylabel(label);axis.grid(alpha=.2);axis.set_xlim(0,19.03);axis.axvline(cut,c='#6a3d9a',ls='--',lw=.8)
 for boundary in [9.005,10.025]:axis.axvline(boundary,c='.5',lw=.6)
 for e in T['events']:
  if e['terminal']:axis.axvspan(e['splice'],e['splice']+e['duration'],color='#4daf4a',alpha=.10)
ax[0].legend(ncol=3);ax[-1].set_xlabel('Task seconds | purple: first possible D request (D historically not executed) | green: T suffix schedule')
fig.suptitle('W1 historical failure: full task / absolute safety / causal PASS, original motion FAIL\nRed levels are full matched-B diagnostic references; qualification evaluated on complete task')
fig.savefig(P/'figures/W1_failure_timeline.png',dpi=140);plt.close(fig)
text=['# W1 运动失败诊断（新 physics 前冻结）','','本诊断只读取历史真实 native 数据。W1 中 B/E/T 已执行；D 尚无 W1 结果。时间均相对完整 TASK 起点。','','## 直接观察',f"膝速度超过完整 B p95×1.10 的第一个样本：{detail['velocity_deg_s']['first_exceedance']:.6f}s；膝加速度：{detail['acceleration_deg_s2']['first_exceedance']:.6f}s。超限样本不是瞬时资格门，原门评价全程 p95。",f"速度高值样本按 OUT/HOLD/RETURN 为 {list(detail['velocity_deg_s']['over_samples_by_phase'].values())}；加速度为 {list(detail['acceleration_deg_s2']['over_samples_by_phase'].values())}。",f"全程 excursion 差 hip/knee={excinfo['difference']}°；超过最终 B excursion+0.5° 的首次时刻={excinfo['first_exceedance_of_final_B_excursion_plus_tolerance']}。",f"D 首个计划请求 {cut:.6f}s。其前缀 p95 计数和 excursion 不可逆下界均未证明必失败；不能把 T 的失败改写为 D 的失败。",'', '## 源码与执行合同','matched_harness.control 在每 phase 的 prefix 槽优先执行合法图残差；W1 OUTBOUND0 在共同冷父里真实执行后完整地址空间 fork，RETURN0 在每个子臂中按同一规则通过原检查执行。后续策略造成的活状态可以不同，名义相同 RETURN0 不表示实际 RETURN 入态完全相同。冻结 D 只在 RETURN2/3 改内部姿态目标，每槽 [+0.3,-0.3]°，保持各活态原选择 duration/pass velocity；18D 参数、RETURN plateau 和 T1.5 不变。', '', '## 归因限制与下一项最小实验','W1 相对 V1 同时改变 OUTBOUND 与 RETURN 背景，且正向 OUTBOUND 改变了后续 planner/plant 的整段历史。失败所在 phase 不识别原因。E/T 的受控差异仅能归因于冻结末段时长合同及其后续闭环响应。精确时段、峰、所有决策及证书/激活记录见 audit/W1_DIAGNOSTIC_NUMBERS.json。','需要以同一 seed 和 W1 OUTBOUND0 固定，单独移除 RETURN0；以及固定 W1 RETURN0、将 OUTBOUND0 换回 V1 合法图的两个配对条件。每个条件各自完整 B/T/D；它们估计整个背景规则的受控效果，不能把入态、allocator 或接触中介再拆成独立原因。D 是否能影响 RETURN 高值和后段 excursion 需要实际执行；OUTBOUND 历史不可由后段 D 改写，但既有下界未阻止全程门通过。', '', '## 尚未识别','具体 allocator/contact/FAST 中介尚未识别；reference、tracking、moment、clearance 和请求/激活时间是可核验的相关响应。没有独立干预支持将其中任一项称唯一原因。N2/U1/V1/V2 仅证明同一 Human 的有限 prefix 条件，不证明任意合法状态。']
(P/'W1_FAILURE_DIAGNOSIS.md').write_text('\n'.join(text)+'\n')
with (P/'W1_FAILURE_DIAGNOSIS.md').open('a') as f:
 f.write('\n## 共同高值与新增负担\n\n')
 for key,x in detail.items():f.write(f"{key}: 第一个高值样本 B 也超该参照={x['first_exceedance_B_also_above']}；T 超而 B 未超的最早时刻={x['first_T_above_limit_B_not']:.6f}s。B 各阶段高值计数={x['B_over_samples_by_phase']}。因此最早高值不等于首次策略差异，更不等于原完整资格门的瞬时失败。\n\n")
 f.write('allocator 分量、clipping、命令、allocated wrench、clearance 与接触的完整阶段范围已保存 audit/W1_COMPENSATION_SIGNALS.json；只作相关解释，不用它们重定义资格或宣称唯一中介。\n')
print(json.dumps(dict(status=out['status'],p95=detail,excursion=excinfo,differences=diff,terminal=[e for e in T['events'] if e['terminal']],first_D_request=cut)),flush=True)
