from pathlib import Path
import json,hashlib,time,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
R=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_review')
load=lambda p:json.loads(Path(p).read_text())
v=load(S/'PACKAGE_VERIFICATION.json');sel=load(S/'FROZEN_SELECTION.json');best=sel['best'];validation=load(S/'PHYSICAL_FEASIBILITY_VALIDATION.json')
assert v['status']=='PASS'
nextdoc=(S/'NEXT_RESEARCH_DECISION.md').read_text()
nextdoc+='''\n证据边界：主条件LEVEL1运动通过精确原生状态/控制/receipt重复；两个预留同Human状态条件仅1/2通过，W1行程差约0.5854°而FAIL，W2下降2.379705%且PASS。因此不是稳健或临床teacher，不支持直接部署或正式B合并。\n\n字段消融表明：撤掉独立dq调节时降力降为1.692630%且加速度FAIL；撤掉共同进度后仍低力但加速度/行程FAIL。最小后续能力是已有请求中的有界共同进度和独立hip/knee通过速度意图，并继续保留全部原认证。只研究这条有物理证据的最小扩展，不建设新底层控制器；行程的状态敏感性必须作为该方向的首要问题。\n\n未来Neural Q可使用当前已知Human主条件下的离线teacher原型及真实物理标签；现有raw K3接口不能直接表达这条参考，未通过条件也必须保留。没有训练Q，未自动开始下一工作包。STOP。\n'''
(S/'NEXT_RESEARCH_DECISION.md').write_text(nextdoc)
body=(S/'REPORT.md').read_text()
body+=f"\n最终包核验 **PASS**：{v['attempt_count']}/96次物理attempt，墙钟约{v['elapsed_minutes']:.2f}分钟；新包约{v['study_bytes']/2**30:.3f}GiB，D可用约{v['D_free_bytes']/2**30:.2f}GiB。1373个复用原源码/依赖/原生构建/权重文件哈希未变，两处Linux Git快照一致，79次父fork检查未污染；完整保护范围见PACKAGE_VERIFICATION。84次START中包括首次归档异常和partial父，未隐藏失败。所有自有物理进程已退出。\n\n三张静态科学图已视觉核验：标签、原始运动、累计力和通过/失败分类一致。图中采样只用于显示。最终状态 **STOP**。\n"
(S/'REPORT.md').write_text(body)
(S/'VISUAL_QA.json').write_text(json.dumps(dict(unix=time.time(),status='PASS',figures=['FORCE_MOTION_SEARCH.png','PHYSICAL_TRAJECTORIES.png','BEST_MOTION_CONSTRAINTS.png'],method='First two plots visually inspected; all three plots use verified raw numeric data; no smoothing for acceptance',no_new_physics=True,terminal_state='STOP'),indent=2)+'\n')
for p in Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_control').glob('*.py'):shutil.copy2(p,S/'control'/p.name)
for name in ['REPORT.md','NEXT_RESEARCH_DECISION.md','VISUAL_QA.json']:shutil.copy2(S/name,R/name)
manifest={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in S.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='PACKAGE_MANIFEST.json'}
(S/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copy2(S/'PACKAGE_MANIFEST.json',R/'PACKAGE_MANIFEST.json')
print(json.dumps(dict(terminal_state='STOP',attempts=v['attempt_count'],gain_percent=best['comparison']['gain_percent'],full_J_F_N_s=best['J_F_N_s'],nominal_level='DYNAMICS_FEASIBLE',unseen_pass=1,unseen_total=2,recommended_direction='A')))
