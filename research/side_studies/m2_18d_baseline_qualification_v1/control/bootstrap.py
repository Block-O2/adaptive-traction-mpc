"""Create a fresh canonical qualification package; never execute physics."""
from pathlib import Path
import os,sys,json,time,hashlib,shutil,subprocess,platform
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
H=S/'ihear_overnight_research_retrospective_v1'
P=S/'m2_18d_baseline_qualification_v1'
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
LOCAL=Path(__file__).resolve().parents[1]
assert not P.exists(), 'Existing canonical package: audit and version, never overwrite'
P.mkdir()
for n in ['audit','provenance','control','reports','output','motion_series','logs','derived','tmp']:(P/n).mkdir()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def git():
 return {k:subprocess.check_output(['git','-C',str(MAIN),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()}
put('audit/GIT_BEFORE.json',git())
# Metadata for all historical files, byte hashes for production and source/weights/contracts/key raw.
inventory={};protected={}
for root in [MAIN,S]:
 for f in root.rglob('*'):
  if P in f.parents or '.git' in f.parts or '__pycache__' in f.parts:continue
  if f.is_symlink():inventory[str(f)]=dict(symlink=os.readlink(f));continue
  if not f.is_file():continue
  st=f.stat();inventory[str(f)]=dict(size=st.st_size,mtime_ns=st.st_mtime_ns)
  rel=f.relative_to(root)
  keyraw=root==S and f.parent.name in ['development_repair2_B0_original','development_repair2_quality_NATIVE_SCALAR_18_063','V1_frozen_best','V2_frozen_best','V3_frozen_best','V4_frozen_best'] and H in f.parents
  if root==MAIN or (root==S and ('results' not in rel.parts and f.suffix in ['.py','.xml','.json','.md','.npz','.npy','.pt','.pth','.so'])) or keyraw:protected[str(f)]=sha(f)
put('audit/HISTORY_METADATA_BEFORE.json',inventory);put('audit/PROTECTED_SHA_BEFORE.json',protected)
env=dict(t0_unix=time.time(),python=sys.executable,python_realpath=str(Path(sys.executable).resolve()),version=sys.version,platform=platform.platform(),cwd=str(Path.cwd()),main=str(MAIN.resolve()),side_studies=str(S.resolve()),disk=shutil.disk_usage(S)._asdict(),meminfo=Path('/proc/meminfo').read_text(),processes=subprocess.check_output(['ps','-eo','pid,ppid,pgid,args']).decode(),history_metadata_count=len(inventory),protected_sha_count=len(protected))
put('ENVIRONMENT.json',env)
for folder in ['source','code','deps','weights']:
 shutil.copytree(H/folder,P/folder,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
(P/'source/results').mkdir()
rebase=[]
for folder in ['source','code','deps']:
 for f in (P/folder).rglob('*'):
  if not f.is_file() or f.suffix not in ['.py','.json','.xml','.yaml','.yml','.toml']:continue
  try:txt=f.read_text()
  except UnicodeError:continue
  before=sha(f);new=txt.replace(str(H),str(P))
  if new!=txt:f.write_text(new);rebase.append(dict(path=str(f.relative_to(P)),before=before,after=sha(f)))
put('audit/PATH_ONLY_REBASE.json',dict(changes=rebase,semantic_changes='none: canonical root string relocation only'))
for f in (LOCAL/'control').glob('*.py'):shutil.copy2(f,P/'control'/f.name)
packages=['ihear_overnight_research_retrospective_v1','m2_free_trajectory_feasibility_v1','adaptive_continuous_coordination_overnight_v1','adaptive_continuous_coordination_interface_v1','m2_18d_waypoint_smoothing_overnight_v1']
line=[]
for pkg in packages:
 root=S/pkg;assert root.is_dir(),pkg
 for name in ['REPORT.md','REPRODUCTION.md','CODE_MANIFEST.json','EXECUTION_CODE_MANIFEST.json','FROZEN_SELECTION.json','VALIDATION_RESULTS.json','BASELINE_REPRODUCTION.json','MOTION_ACCEPTANCE_PROTOCOL.json','RUN_PLAN.json','TRAJECTORY_OPTIMIZATION_PROTOCOL.json','CURRENT_MODEL_AND_TASK.json','PACKAGE_VERIFICATION.json']:
  f=root/name
  if f.is_file():
   dest=P/'provenance'/(pkg+'__'+name);shutil.copy2(f,dest);line.append(dict(source=str(f),copy=str(dest.relative_to(P)),sha256=sha(f)))
shutil.copy2(MAIN/'CURRENT_RESEARCH_BASELINE.md',P/'provenance/CURRENT_RESEARCH_BASELINE.md')
line.append(dict(source=str(MAIN/'CURRENT_RESEARCH_BASELINE.md'),sha256=sha(MAIN/'CURRENT_RESEARCH_BASELINE.md')))
put('audit/SOURCE_LINEAGE.json',line)
selection=json.loads((H/'FROZEN_SELECTION.json').read_text());candidate=selection['best']['candidate']
put('FROZEN_18D.json',candidate)
shutil.copy2(H/'MOTION_ACCEPTANCE_PROTOCOL.json',P/'MOTION_ACCEPTANCE_PROTOCOL.json')
shutil.copy2(H/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
pr=json.loads((H/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json').read_text())
entries=[]
explain=['共同进度常数','髋膝差分进度常数','差分进度一次倾斜','终端速度共同比例','终端速度差分比例','共同进度常数','髋膝差分进度常数','差分进度一次倾斜','终端速度共同比例','终端速度差分比例','共同进度一次倾斜','共同进度二次曲率','差分进度二次曲率','终端速度差分一次倾斜','共同进度一次倾斜','共同进度二次曲率','差分进度二次曲率','终端速度差分一次倾斜']
for i,(name,scale,value,desc) in enumerate(zip(pr['parameter_names'],pr['parameter_scales'],candidate['free_parameters'],explain)):
 entries.append(dict(index_zero_based=i,index_one_based=i+1,name=name,value=value,normalized_value=candidate['normalized_parameters'][i],scale=scale,normalized_bounds=[-1,1],phase='OUTBOUND' if name.startswith('O_') else 'RETURN',meaning_zh=desc,units='dimensionless',source='code/rich_planner.py:RichFreePlanner'))
put('PARAMETER_MAP.json',dict(parameters=entries,additional_frozen_native_residuals=candidate['phases'],hold='unchanged native B',coordinate_order=['hip','knee'],identity_warning='18D vector alone is incomplete: retain two RETURN native residual plateaus and request-slot semantics'))
now=env['t0_unix']
conditions=[dict(name='N1',seed=2026101701,prefix={'OUTBOUND':[[.06,.06,.06]]}),dict(name='N2',seed=2026101702,prefix={'OUTBOUND':[[-.06,-.06,-.06]]}),dict(name='N3',seed=2026101703,prefix={'OUTBOUND':[[.15,-.05,.05]]}),dict(name='N4',seed=2026101704,prefix={'OUTBOUND':[[-.05,.15,-.025]]})]
plan=dict(t0_unix=now,hard_stop_unix=now+6*3600,dispatch_cutoff_unix=now+5*3600,physics_hard_stop_unix=now+5*3600,physical_timeout_s=600,physics_budget=40,seed=2026101303,validation_conditions=conditions,expected_starts=15,single_physics_owner=True,question='Does the frozen complete historical 18D intent reproduce, then retain full-task force gains and original motion/safety under lawful native prefix states?',reproduction_gate='full trace exact identity against original B/18D archives; original complete task/safety/motion/ownership; exact complete live-state fork restored; parent unchanged; full JF and phase closure',validation_gate='each matched pair complete task, lower full J_F (positive gain), original frozen motion/safety/causal receipt. No selection or parameter update.',fork_rule='development at first OUTBOUND request; validation at next OUTBOUND request after one actual causal native prefix slot. B/18D inherit identical complete live parent. Prefix integral included in full TASK J_F. Frozen E resumes unconsumed slots; this tests remaining policy, not its consumed O0 slot.',exclusions='partial tasks never rank; deterministic same state repeats never add independent state count; this is one exposed Human/model only',truth_firewall='fixed registered intents; only causal B observations online. qpos/qvel read for evaluation/fork auditing only; no direct assignment/replay by qualification code',stop='absolute safety, task invalidity, fork mutation, ownership/integral error or reproduction gate failure stop all new starts. Motion failure is retained and permits remaining preregistered validation pairs. No tuning.',protected='B/plant/Human/robot/contact/gravity/actuator/ROM/torques/goals/HOLD/duration/bridge40ms/lifecycle100ms/admission/age/receipts/native ownership/carry/fallback unchanged',no_training=True,no_waypoint_smoothing=True,no_optimization=True,history_motion_primary='0/4 PASS retained, separate from current study')
put('RUN_PLAN.json',plan)
(P/'METHOD_DEFINITION.md').write_text('''# 18D方法定义（源码审计，physics前冻结）

历史primary是离线有限约束搜索选出的固定参考意图参数，不是学习策略，不调用Q-learning、Neural Q或在线RL。在线仍由原B的因果状态/模型估计、有限waypoint MPC、quintic scheduler/governor、current admission、FAST/cuff allocator和六轴torque执行。18D不是一条预存真实Human运动，也不是直接施加关节状态。

实现：`code/rich_planner.py:RichFreePlanner.parameters/decide/_waypoint_terminal_velocity`；原反对称残差在`source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/coordination_residual_v2.py`。全部18项及数值见PARAMETER_MAP.json，冻结完整candidate见FROZEN_18D.json。

对B已选出的非终末target，以本phase起点和跨度将hip/knee归一化为p，m=mean(p)，u=2m-1，e=sin²(pi*clip(m,0,1))。OUTBOUND j=0,k=10；RETURN j=5,k=14（零基索引）。

`c=e*(x[j]+x[k]*u+x[k+1]*u²)`；`d=e*(x[j+1]+x[j+2]*u+x[k+2]*u²)`；新target进度`p+[c+d,c-d]`，再乘各关节跨度恢复rad。c改变共同进度；d改变相对姿态；tilt/curve改变其沿进度形状。RETURN跨度负向，不能把正负系数直接解释为绝对屈曲方向。范围越界或原可行性不通过时保留B原执行目标。

非终末waypoint的原B终端速度乘以`1+e*[x[j+3]+x[j+4]+x[k+3]*u, x[j+3]-x[j+4]-x[k+3]*u]`。这是通过速度偏置，完整实际速度仍由quintic、桥接、governor、反馈与contact响应决定。HOLD、接近phase终点及最终目标保留原B行为。18D本身不增加内部quintic控制点。

完整赢家还包含RETURN第1和第2槽（零基）的native差分plateau，分别-0.020和-0.022。相对remaining causal progress在[0,.001,.5,.999,1]形成[0,a,a,a,0]，前端按当前start_m映射并在全局0补零；该层先作用于native目标，再施加18D。不得仅凭文件名NATIVE_SCALAR_18推断维数，更不能丢掉这两个plateau。

历史优化入口为`code/overnight_runner.py`及`runner.py`，有限COBYLA及预注册probe/repair/quality候选，以完整J_F最小化并受冻结运动、剂量、时长、tracking、moment/peak、安全/task/ownership约束。选择primary为开发合格候选中最小完整J_F，不保证收敛或全局最优。冻结后不得按验证重选；secondary也不能替换primary。运动阈值逐字节继承MOTION_ACCEPTANCE_PROTOCOL.json：原始velocity/acceleration/jerk比较1.10、excursion/边界0.5°、剂量0.95–1.05、时间0.1s、moment1.25、tracking增加0.5°、peaks1.05；phase-shape和jerk max为诊断，不偷改为PASS规则。

开发状态/模型：high_rom_nominal_sync_120_v1，同一已暴露被动Human，75kg/1.72m，rest[5,10]°，任务[5,10]→[120,120]→[5,10]°，ROM[0,125]°；完整case/options/模型来源hash见provenance中的CURRENT_MODEL_AND_TASK。合同HOLD dwell为0.5s，实际HOLD阶段约1.02s，两者不可混淆。开发seed=2026101303。完整历史B=1438.6134984674875，18D=1400.697221153 N·s，约2.635613%；完整19.03s。

历史primary合法prefix motion 0/4必须保留：V1膝velocity p95；V2 acceleration p95及phase-boundary；V3 velocity/acceleration p95及excursion；V4 acceleration max/p95、jerk RMS及excursion失败。历史更低力1196.685445候选motion失败，不是合格赢家。正式Native LEVEL2、host-clock LEVEL3/strict55/R2/FAST负结果和硬件/临床未验证均保留。仅PHYSICAL_LEVEL1同模型研究。
''')
(P/'SOURCE_AND_RESULT_LINEAGE.md').write_text('''# 来源与结果谱系

所有指定名称均已在真实Side Studies找到，没有虚构包。`audit/SOURCE_LINEAGE.json`列原始绝对路径、逐字节SHA及provenance副本；`audit/PATH_ONLY_REBASE.json`列复制源码仅绝对根路径替换的前后hash。历史原件只读。原始18D来自ihear_overnight_research_retrospective_v1/FROZEN_SELECTION.json的best.candidate，完整字段原样冻结为FROZEN_18D.json。

m2_free_trajectory_feasibility_v1：前序10D，历史1403.259730，不与18D混同。retrospective：18D开发1400.697221及历史合法prefix motion 0/4。adaptive_continuous_coordination_overnight_v1：旧路径基线精确复现、非零多段接口未过门。adaptive_continuous_coordination_interface_v1：后续非零多段执行达到隔离PHYSICAL_LEVEL1。m2_18d_waypoint_smoothing_overnight_v1：B/18D复现与小幅平滑干预，无新晋级primary。本轮使用retrospective原18D闭包，不叠加任何平滑。

历史关键raw：`ihear_overnight_research_retrospective_v1/source/results/development_repair2_B0_original`与`development_repair2_quality_NATIVE_SCALAR_18_063`的trace.npz、summary.json、runtime_artifacts.json.gz，以及原motion_series和MEASURED/receipts报告。历史V1–V4失败不覆盖。关键raw的启动SHA记录于audit/PROTECTED_SHA_BEFORE.json。

历史报告值、当前从raw独立重算、当前新physical结果必须各自标识。本轮是否精确复现以BASELINE_REPRODUCTION.json为准。本地Windows目录为审阅镜像，完整raw和源码闭包在canonical WSL目录；不能声称镜像含全部raw。
''')
put('STATE.json',dict(phase='SOURCE_AUDIT_COMPLETE_NO_PHYSICS',next_action='preflight imports and path closure, freeze execution manifest then reproduction',physics_starts=0))
print(json.dumps(dict(package=str(P),files=len(protected),rebase=len(rebase),plan=plan),ensure_ascii=False))
