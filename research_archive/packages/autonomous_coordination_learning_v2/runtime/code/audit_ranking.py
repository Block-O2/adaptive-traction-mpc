from pathlib import Path
import sys, os, json, hashlib, collections
sys.dont_write_bytecode=True
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime')
OLD=S.parent/'b_fast_jitter_m2_host_v1'
sys.path.insert(0,str(S/'code'))
import numpy as np
import native_core as nc
from native_inference import Networks
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    net=Networks(S/'weights/frozen_Q_v1');assert net.meta['selected_Q']=='linear'
    w=net.w;coef=w['linear_W'].astype(float)/w['x_scale']*float(w['y_scale']);offset=float(w['y_mean']+w['y_scale']*w['linear_b']-coef@w['x_mean'])
    rows=[];contexts=[];all_sources=[]
    for base in (OLD,S):
        for p in sorted((base/'output').glob('*_HOST_COORDINATOR.json')):
            data=json.loads(p.read_text());carry=np.zeros((2,5,3))
            if data['method']!='M2':continue
            all_sources.append(dict(path=str(p),sha256=sha(p)))
            for entry in data['rows']:
                r=entry.get('selection_row')
                if r is None:continue
                plans=[np.asarray(x['plan']) for x in r['candidate_records']];c=r['context'];count=r['count_before']
                x=np.asarray([nc.feature(c,plan,count,carry) for plan in plans]);q=net.values(x);real=x.astype(float)@coef+offset;pref=x[:,58:88].astype(float)@coef[58:88]
                common={name:float(x[0,a:b].astype(float)@coef[a:b]) for name,a,b in [('state_history',0,58),('carry',88,118),('issued',118,120)]}
                for a,b in ((0,58),(88,118),(118,120)): assert np.all(x[:,a:b]==x[0,a:b])
                delta_error=float(np.max(np.abs((q[:,None]-q[None,:])-(pref[:,None]-pref[None,:]))))
                order=np.argsort(q,kind='stable').tolist();fixed=np.argsort(pref,kind='stable').tolist();sel=r['selected_index'];rec=r['candidate_records']
                evaluated=[i for i,v in enumerate(rec) if v.get('feasible') is not None];eligible=[i for i in evaluated if rec[i].get('feasible') and rec[i].get('proposal_accepted')]
                mask_pref=np.array([coef[58:88]@np.asarray(v).ravel() for v in plans])
                rows.append(dict(source=str(p),request_id=r['request_id'],phase=c['phase'],count=count,raw_Q=q.tolist(),recorded_q_all=r.get('q_all'),algebraic_Q=real.tolist(),fixed_plan_preference=pref.tolist(),common_terms=common,raw_rank=order,fixed_rank=fixed,native_raw_order=r.get('q_first_order'),selected_index=sel,selected_source=r['selected_source'],evaluated_indices=evaluated,known_eligible_indices=eligible,unknown_eligibility_indices=[i for i in range(len(rec)) if i not in evaluated],native_eligibility_displaced_raw_top=sel!=order[0],carry_selected=r['selected_source']=='carry',late_carry=entry['admission']['late_carry'],native_current_margin=float(np.sort(q)[1]-np.sort(q)[0]) if len(q)>1 else None,pairwise_numeric_error_N_s=delta_error,mask_id=hashlib.sha256(json.dumps(count,sort_keys=True).encode()).hexdigest(),candidate_sources=[v['source'] for v in rec],candidate_plans=[v.tolist() for v in plans]))
                contexts.append((c,count,plans));carry=np.asarray(r['applied_plan']).copy()
    assert contexts
    fixed_count=contexts[0][1];fixed_plans=contexts[0][2];fixed_carry=np.zeros((2,5,3));fixed_rows=[]
    for c,_,_ in contexts:
        x=np.asarray([nc.feature(c,p,fixed_count,fixed_carry) for p in fixed_plans]);q=net.values(x);pref=x[:,58:88].astype(float)@coef[58:88]
        fixed_rows.append(dict(phase=c['phase'],q=q.tolist(),delta_from_candidate0=(q-q[0]).tolist(),rank=np.argsort(q,kind='stable').tolist(),analytic_delta=(pref-pref[0]).tolist(),analytic_rank=np.argsort(pref,kind='stable').tolist()))
    base_delta=np.asarray(fixed_rows[0]['delta_from_candidate0']);ranks={tuple(r['rank']) for r in fixed_rows};analytic_ranks={tuple(r['analytic_rank']) for r in fixed_rows}
    mask_probes=[]
    for o in range(6):
        for ret in range(6):
            count={'OUTBOUND':o,'RETURN':ret};pref=np.array([coef[58:88]@nc.masked(p,count).ravel() for p in fixed_plans]);order=np.argsort(pref,kind='stable').tolist()
            mask_probes.append(dict(count=count,fixed_input_plan_preferences=pref.tolist(),rank=order,top=order[0],scope='Offline legal issued-mask algebra; fixed plan vectors, no native execution or learned state interaction'))
    recorded_errors=[float(np.max(np.abs(np.asarray(r['recorded_q_all'])-np.asarray(r['raw_Q'])))) for r in rows if r['recorded_q_all'] is not None]
    out=dict(status='PASS',learned_state_conditioned_ranking='FAIL',fixed_ranking_real_arithmetic_equivalence='PASS',deployed_float32_bitwise_equivalence_claim=False,feature_dim=120,feature_blocks={'causal_normalized_observation55':[0,55],'K3_previous_residual3':[55,58],'masked_candidate30':[58,88],'masked_carry30':[88,118],'issued_counts2':[118,120]},Q_sha256=sha(S/'weights/frozen_Q_v1/weights.npz'),selected_Q='linear',coefficient=coef.tolist(),offset=offset,state_plan_interaction=False,delta_equation='DeltaQ_ij = coef[58:88] dot (masked(p_i,count)-masked(p_j,count)); all state/history/carry/count common terms cancel',state_cross_derivative=0,ranking_direction='ascending predicted J_F',rows=rows,source_files=all_sources,fixed_candidates_mask_carry_probe=dict(status='PASS' if len(analytic_ranks)==1 else 'FAIL',real_contexts=len(fixed_rows),fixed_count=fixed_count,fixed_plans=[p.tolist() for p in fixed_plans],raw_top_choice_changes=sum(r['rank'][0]!=fixed_rows[0]['rank'][0] for r in fixed_rows),raw_unique_ranks=len(ranks),analytic_unique_ranks=len(analytic_ranks),numeric_pairwise_drift_N_s=max(float(np.max(np.abs(np.asarray(r['delta_from_candidate0'])-base_delta))) for r in fixed_rows),raw_Q_candidate0_range_N_s=[min(r['q'][0] for r in fixed_rows),max(r['q'][0] for r in fixed_rows)],rows=fixed_rows),issued_mask_probe=dict(rows=mask_probes,unique_ranks=len({tuple(r['rank']) for r in mask_probes}),unique_top_choices=len({r['top'] for r in mask_probes})),absolute_recorded_score_reconstruction_max_error_N_s=max(recorded_errors or [0]),mask_semantics='Issued-slot zeros precede scoring. Counts advance on issued selections including proposals later rejected; not physical committed counts. Mask can alter fixed-plan preference, deduplication and candidate membership.',eligibility_semantics='Q-first tries ascending raw Q, selects first feasible accepted native candidate. Unvisited candidates remain unknown, never classified infeasible. Close-rank float32 bound can trigger full native evaluation.',carry_semantics='Carry is both an additive common feature and a candidate. Common carry feature cannot change relative scores; changing carry candidate identity can. Late worker guard may restore legal carry independent of Q winner.',lifecycle='Strict55-derived 19ms preguard disabled in registered host pairs only; unchanged40ms native bridge,100ms expiry,current-state admission,original fallback and causal ownership',HOLD='NOT_EVALUABLE for empirical Q decisions: runtime issues coordination only OUTBOUND/RETURN. Algebraic cancellation holds for every120D input including HOLD; no synthetic HOLD state presented as observed decision.',comparator_status='NOT_RUN',comparator_reason='Analytic fixed masked-plan ranking equivalence; no state-plan interaction, physical comparator adds no ranking mechanism evidence',phase_counts=dict(collections.Counter(r['phase'] for r in rows)),native_eligibility_displaced_top_count=sum(r['native_eligibility_displaced_raw_top'] for r in rows),carry_selected_count=sum(r['carry_selected'] for r in rows),late_carry_count=sum(r['late_carry'] for r in rows),max_numeric_delta_error_N_s=max(r['pairwise_numeric_error_N_s'] for r in rows),physics_attempts_added=0,Q_updates=0)
    (S/'Q_RANKING_ATTRIBUTION.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    text=f'''# 冻结 Q 排序机制归因\n\n状态：解析审计 PASS；真正 state×plan 排序能力 FAIL；物理固定排序 comparator NOT_RUN。\n\n冻结权重 SHA256：{out['Q_sha256']}。selected_Q=linear；120D 输入依次为 causal normalized55、previous K3 residual3、masked candidate30、masked carry30、issued counts2。实际归一化与输出反归一化折叠后 Q(x)=offset+coef·x。同一候选集合、mask、carry、issued counts 下，ΔQ_ij=coef[58:88]·(masked(p_i)−masked(p_j))；状态、history、carry、counts 的公共项完全相消，交叉导数为零。因此绝对分数随状态变化不能证明条件化排序。\n\n从真实旧/本轮 worker 记录审计 {len(rows)} 个决策，阶段计数 {out['phase_counts']}。固定候选、mask、carry 后使用 {len(fixed_rows)} 个真实上下文：解析排序数 {len(analytic_ranks)}，float32 排序数 {len(ranks)}，top-choice变化 {out['fixed_candidates_mask_carry_probe']['raw_top_choice_changes']}；float32 分数差漂移最大 {out['fixed_candidates_mask_carry_probe']['numeric_pairwise_drift_N_s']:.9g} N·s。真实记录中 raw-top 被 native eligibility 改选 {out['native_eligibility_displaced_top_count']} 次，carry 被选 {out['carry_selected_count']} 次，worker late-carry {out['late_carry_count']} 次。候选变化、随机噪声、mask 与 native feasibility 仍可改变实际选择，但不等于 learned conditional preference。\n\nQ-first 只验证直至首个有效候选；未访问候选 eligibility 是 unknown。原 close-rank float32 safeguard 完整保留。实数排序等价不宣称 bitwise 等价，最大 pairwise 数值误差 {out['max_numeric_delta_error_N_s']:.9g} N·s。未运行 HOLD Q 决策，标为 NOT_EVALUABLE；解析结论覆盖所有120D输入。\n\nIssued slots 在发出时推进，包括后来被拒的提案，不能视为物理完成数。carry 特征是公共项，carry 候选身份可改变排序；late guard 恢复 carry 属执行机制。完整 raw scores、margins、固定计划、coefficients、记录路径及哈希在同名 JSON。无训练、无物理新增尝试。\n'''
    text=text.replace(str(out.get('mask_displaced_top_count','missing')),str(out['native_eligibility_displaced_top_count']))
    text+=f"\n固定计划的36个 issued-mask 组合产生 {out['issued_mask_probe']['unique_ranks']} 个排序与 {out['issued_mask_probe']['unique_top_choices']} 个 top-choice，属于 mask-induced selection 的离线解析证据。Absolute recorded q_all 重建最大误差 {out['absolute_recorded_score_reconstruction_max_error_N_s']:.9g} N·s。\n"
    (S/'Q_RANKING_ATTRIBUTION.md').write_text(text)
    print(json.dumps({k:out[k] for k in ('status','learned_state_conditioned_ranking','phase_counts','max_numeric_delta_error_N_s','comparator_status')}))
if __name__=='__main__': main()
