from pathlib import Path
import sys, os, json, collections
sys.dont_write_bytecode=True
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_expanded_prefix_validation_v1')
sys.path.insert(0,str(S/'code'))
import numpy as np
def load(p):return json.loads(p.read_text())
def read_trace(ident):
    with np.load(S/'source/results'/ident/'trace.npz') as z:return {k:z[k].copy() for k in z.files}
def interval_metrics(z,a,b):
    mask=z['stage']=='TASK';t=z['time_s'][mask];dt=np.maximum(0,np.minimum(t[1:],b)-np.maximum(t[:-1],a));ix=dt>0;duration=float(dt.sum())
    f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1);e=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][mask,:2]-z['reference_q_rad'][mask])
    jf=float(f[:-1]@dt);mi=float(m[:-1]@dt)
    return dict(trace_duration_s=duration,J_F_N_s=jf,mean_force_N=jf/duration if duration else None,moment_integral_Nm_s=mi,mean_moment_Nm=mi/duration if duration else None,force_peak_N=float(f[:-1][ix].max()) if ix.any() else None,moment_peak_Nm=float(m[:-1][ix].max()) if ix.any() else None,time_weighted_true_reference_RMS_deg=np.sqrt((e[:-1]**2).T@dt/duration).tolist() if duration else None,measured_min_clearance_m=float(z['dev_d_measured_sleeve_gap_m'][mask][:-1][ix].min()) if ix.any() else None)
def main():
    paired=load(S/'PAIRED_HOST_RESULTS.json');lineage=load(S/'EXECUTION_LINEAGE.json');mapping={r['id']:r for r in lineage['runs']};segments=[];delta_groups=collections.defaultdict(list);selection_sources=collections.Counter();receipt_duplicates=[];prefix_execution=[]
    for p in paired['pairs']:
        if p['status']!='PASS':continue
        bid=p['B_id'];mid=p['M2_id'];zb=read_trace(bid);zm=read_trace(mid);bsummary=load(S/'source/results'/bid/'summary.json');msummary=load(S/'source/results'/mid/'summary.json');btrans={r['to']:r['time_s'] for r in bsummary['task']['phase_transitions']};mtrans={r['to']:r['time_s'] for r in msummary['task']['phase_transitions']}
        bstart=float(zb['time_s'][zb['stage']=='TASK'][0]);mstart=float(zm['time_s'][zm['stage']=='TASK'][0]);originsB={'OUTBOUND':bstart,'HOLD':btrans['HOLD'],'RETURN':btrans['RETURN']};originsM={'OUTBOUND':mstart,'HOLD':mtrans['HOLD'],'RETURN':mtrans['RETURN']}
        seen=set()
        for r in mapping[mid]['rows']:
            if not r['physically_executed_nonzero']:continue
            ph=r['phase'];a=r['execution_start_physics_s'];b=r['execution_end_physics_s'];ab=a-originsM[ph]+originsB[ph];bb=b-originsM[ph]+originsB[ph];actual=interval_metrics(zm,a,b);baseline=interval_metrics(zb,ab,bb)
            for receipt in r['receipts']:
                if receipt['receipt_index'] in seen:receipt_duplicates.append(dict(id=mid,request_id=r['request_id'],receipt_index=receipt['receipt_index']))
                seen.add(receipt['receipt_index'])
            deltaJ=actual['J_F_N_s']-baseline['J_F_N_s'];segments.append(dict(pair_id=p['pair_id'],M2_id=mid,B_id=bid,request_id=r['request_id'],phase=ph,M2_interval_physics_s=[a,b],B_same_phase_elapsed_interval_physics_s=[ab,bb],selected_K3=r['selected_K3'],native_delta_d=r['selected_delta_d'],selected_source=r['candidate_identity']['source'],M2=actual,B=baseline,descriptive_delta_J_F_N_s=deltaJ,scope='Post-execution same-phase-elapsed descriptive window; not a causal residual-only effect. Integrates TASK trace over actual receipt-owned window; phase overlaps/end gaps remain explicit.'))
            selection_sources[ph+':'+r['candidate_identity']['source']]+=1
            for d in r['selected_delta_d']:delta_groups[ph].append(float(d))
        # Public prefix interventions are native executions in both arms, separate from Q-selected residual denominator.
        for ident,summary in ((bid,bsummary),(mid,msummary)):
            for lr in summary['learning_records']:
                sp=lr.get('selected_plan',{});meta=sp.get('execution_screen',{}).get('coordination_residual_v2',{})
                if lr.get('selected_plan_activated') and meta.get('status')=='ACCEPTED' and abs(meta.get('delta',0))>1e-12:
                    prefix_execution.append(dict(id=ident,decision_index=lr.get('decision_index'),start_physics_s=lr.get('start_time_s'),end_physics_s=lr.get('end_time_s'),delta=meta['delta'],metadata=meta,scope='All activated native coordination residuals, including common prefix. Q-only actual-step denominator remains separate.'))
    assert not receipt_duplicates,receipt_duplicates
    out=dict(status='PASS',segments=segments,receipt_nonduplication='PASS',native_delta_d_by_phase={k:dict(n=len(v),values=v,min=min(v),max=max(v),mean=float(np.mean(v)),rounded6_frequency=dict(collections.Counter(str(round(x,6)) for x in v))) for k,v in delta_groups.items()},executed_selected_sources=dict(selection_sources),all_activated_coordination_metadata=prefix_execution,phase_window_descriptive={p:dict(n=sum(s['phase']==p for s in segments),lower_force_windows=sum(s['phase']==p and s['descriptive_delta_J_F_N_s']<0 for s in segments),sum_delta_J_F_N_s=sum(s['descriptive_delta_J_F_N_s'] for s in segments if s['phase']==p)) for p in ('OUTBOUND','RETURN')},no_causal_identification=True)
    (S/'reports/RETURN_EXECUTION_WINDOWS.json').write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    text='\n逐实际 receipt window 与 B 同阶段相对时间窗口的描述性对照：\n\n| phase | 非零 window数 | 较低 J_F window数 | window ΔJ_F合计 N·s |\n|---|---:|---:|---:|\n'
    for ph,v in out['phase_window_descriptive'].items():text+=f"| {ph} | {v['n']} | {v['lower_force_windows']} | {v['sum_delta_J_F_N_s']:.6f} |\n"
    text+='\n这些窗口不覆盖完整任务，且起点状态、commissioning 和先前残余不同；window 差值不能解释为独立处理效应。全阶段收益仍以对称乘积分解为准。实际 native Δd 的分布及按所选 source 的重复频率在 reports/RETURN_EXECUTION_WINDOWS.json，允许固定计划在不同 native 状态下实现不同 Δd，不能将此误称为 Q 的条件化排序。共同 prefix 的所有 activated native metadata 独立保留；Q-only 非零执行分母不包括公共 prefix。receipt 非重复核验 PASS。\n'
    with (S/'RETURN_ATTRIBUTION.md').open('a') as f:f.write(text)
    print(json.dumps(dict(status=out['status'],windows=out['phase_window_descriptive'],native_delta_d_by_phase=out['native_delta_d_by_phase'],executed_sources=out['executed_selected_sources'])))
if __name__=='__main__': main()
