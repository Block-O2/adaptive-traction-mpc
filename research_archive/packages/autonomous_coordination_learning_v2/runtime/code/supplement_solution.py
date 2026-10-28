from pathlib import Path
import json,hashlib
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 catalog={c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']}
 c=catalog['C4_1_5'];s=c['phases']['RETURN'][2]
 line=json.loads((S/'reports/discovery_resume_C4_1_5_EXECUTED_RESIDUAL_RECEIPTS.json').read_text());executed=[r for r in line['rows'] if r['physically_executed_nonzero']];assert len(executed)==1
 e=executed[0];delta=e['native_coordination_metadata'][0]['delta']
 solution=dict(id=c['id'],scope='RETURN-only, third existing issued interior slot (zero-based index 2)',registered_policy=c,remaining_progress_node_fractions=[.1,.145,.55,.955,1.],node_values=[0.,-.035,-.021,-.007,0.],native_delta_observed=delta,nonzero_native_plans=1,associated_native_steps=e['actual_native_steps'],first_native_execution_physics_s=e['first_execution_physics_s'],all_other_slots='zero residual through original B; HOLD and terminal B-owned',native_sampling='absolute nodes use s + (1-s)*fraction, where s is current causal reference common progress; native samples at original B nominal target m; modified progress = p_B + [delta,-delta]',physical_coordinates='dimensionless normalized phase progress; negative RETURN delta leads knee and delays hip in phase direction; no direct torque/time/velocity authority',discovery_gain_percent=.7387616975226481,independent_gains_percent=[.7462125626930302,.7379623888290919],scientific_only=True,no_Q_training=True)
 p=S/'MAIN_COORDINATION_SOLUTION.json';p.write_text(json.dumps(solution,indent=2,ensure_ascii=False)+'\n')
 report=S/'REPORT.md';text=report.read_text();needle='主发现门限固定为'
 addition=f'''主方案 `C4_1_5`：只在 RETURN 的第3个既有 issued interior slot（index=2）提案，其余 slot 为原 B 零残差，HOLD/terminal 仍由 B 拥有。设当前因果参考公共进度为 s、r=1−s，PWL 结点为 `(0,0)、(s+0.1r,0)、(s+0.145r,−0.035)、(s+0.55r,−0.021)、(s+0.955r,−0.007)、(1,0)`。值的单位是归一化阶段进度，不是角度或 torque。native 在原 B nominal target 的公共进度 m 处采样，并执行反对称 `[delta,−delta]` 分配；RETURN 的负 delta 对应 knee 在阶段方向领先、hip 延后。

发现 trace 的实际 delta 为 `{delta:.12f}`；唯一非零 native 计划关联 `{e['actual_native_steps']}` 个物理步，首次实际执行 physics t=`{e['first_execution_physics_s']:.6f}s`。完整任务收益包含其后全部原生续跑、carry/fallback，而非仅此窗口。完整参数与执行证据见 MAIN_COORDINATION_SOLUTION.json。

'''
 text=text.replace(needle,addition+needle,1);report.write_text(text)
 manifest_path=S/'FINAL_MANIFEST.json';manifest=json.loads(manifest_path.read_text())
 for q in [p,report,Path(__file__)]:manifest[str(q.relative_to(S))]=dict(bytes=q.stat().st_size,sha256=sha(q))
 manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(dict(main=c['id'],actual_delta=delta,actual_nonzero_steps=e['actual_native_steps'],parameters_unchanged=True)),flush=True)
if __name__=='__main__':main()
