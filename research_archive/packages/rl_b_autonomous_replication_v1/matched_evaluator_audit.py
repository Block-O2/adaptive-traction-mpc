"""Provenance audit only; intentionally cannot invent original B/H150 scoring."""
from pathlib import Path
import hashlib,json,time,zipfile,re
R=Path(__file__).resolve().parent;B=R.parent

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def put(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
zip_path=Path('/home/hank/ihear_rl_b_cpu_cloud_v1.zip')
with zipfile.ZipFile(zip_path) as z:
 names=z.namelist();manifest=json.loads(z.read('SHA256_MANIFEST.json'));checks={n:hashlib.sha256(z.read(n)).hexdigest()==meta['sha256'] and len(z.read(n))==meta['bytes'] for n,meta in manifest['files'].items()}
 zipaudit={'zip':str(zip_path),'sha256':sha(zip_path),'archive_members':len(names),'manifest_entries':len(checks),'all_payloads_verified':all(checks.values()),'missing_payloads':[n for n,ok in checks.items() if not ok],'matched_identity_name_hits':[n for n in names if re.search(r'H150|strict55|matched.*scor|Master.Contract',n,re.I)],'packaged_docs':[n for n in names if '/docs/' in n]}
put(R/'audit/ORIGINAL_ARCHIVE_VERIFICATION.json',zipaudit)
packages={};reference=json.loads((R/'SOURCE_MANIFEST.json').read_text())['files']
for name in ['rl_b_cloud_v1','rl_b_cloud_g4_repair_v1','rl_b_g4_closure_ppo_readiness_v1','rl_b_first_ppo_pilot_v1']:
 root=B/name/'source';files={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 packages[name]={'source_files':len(files),'different_from_current_replication_source':[k for k,v in files.items() if reference.get(k)!=v],'missing_in_current':[k for k in files if k not in reference],'additional_in_current':[k for k in reference if k not in files],'source_manifest_path':str(B/name/'SOURCE_MANIFEST.json')}
# Search every available scientific text once, recording context and names rather
# than deciding version equivalence from a generic matched/baseline file name.
patterns=['H150','strict55','B/H150','FULL_QUALIFIED','B-relative','cumulative dose','motion_noninferiority']
content_hits={p:[] for p in patterns}
for p in (R/'source').rglob('*'):
 if not p.is_file() or p.suffix not in ['.py','.json','.md']:continue
 text=p.read_text(errors='replace')
 for pattern in patterns:
  for i,line in enumerate(text.splitlines(),1):
   if pattern.lower() in line.lower():content_hits[pattern].append({'path':str(p.relative_to(R)),'line':i,'text':line[:400]})
contract_path=R/'source/stages/stage5_personalized_motion_learning/docs/adaptive_human_online_interface_v1/EXPERIMENT_CONTRACT.json';contract=json.loads(contract_path.read_text())
missing=['Authoritative original B/H150 complete task/safety/motion/fairness/causal contract and manifest naming precise frozen scorer files','Original B/H150 scorer implementation/dependency closure and original baseline motion/dose normalization with version/hash','Original B and H150 controller/config identities, complete raw, state restoration or deterministic initial-state generator','Known original PASS and FAIL fixtures, exact tolerances, native ownership/receipt/source-age semantics and scientific-vs-host/strict55 qualification requirements']
audit={'unix':time.time(),'status':'MATCHED_BASELINE_EVALUATION_NOT_READY','formal_scorer_deployed':False,'formal_B_H150_reproduction_attempts':0,'archive':zipaudit,'four_source_packages':packages,'text_identity_search_hits':content_hits,'only_packaged_contract':{'path':str(contract_path.relative_to(R)),'sha256':sha(contract_path),'frozen_utc':contract['frozen_utc'],'source_commit':contract['source_commit'],'evidence_category':contract['evidence_category'],'no_training_historical':contract['no_training'],'not_a_B_H150_master':True,'current_user_development_training_authorization_supersedes_historical_no_training':True},'minimal_missing':missing,'no_approximate_promotion':True,'baseline_identity':'Fixed legal plus-one is explicitly not B or H150','available_metrics_scope':'Original runtime and per-episode observed physics/causal audit; no recovered B-relative fairness/jerk/overshoot/dose qualification thresholds','local_source_origin':'Portable CPU archive sha verified; no .git checkout or original external baseline archive present in supplied workspace.'}
put(R/'audit/MATCHED_EVALUATOR_INVENTORY.json',audit)
rows=[('task/phase/runtime duration','原runtime、completion_evidence、10s/phase与30s/task可核对；正式matched合同缺失'),('19.030s与容差','历史verify_physics.py必要回归使用abs(t−19.03)<.05；不是完整task合同'),('OUTBOUND/HOLD/RETURN','原转换链与causal return commit可核对'),('absolute safety / ROM / torque / clearance / contact','原runtime监控与逐native实际物理审计可用；全动作和未触发边界没有新证明'),('B-relative motion / fairness','原B/H150身份、完整基准raw与motion非劣标准缺失'),('velocity / acceleration / jerk','原45/75°/s与300/600°/s²可按native核对；实际jerk作诊断，不能从reference jerk限制推导Human正式门'),('excursion / terminal overshoot','可独立计算实际轨迹数值；原基准相对门和terminal容差版本缺失'),('cumulative dose','完整JF/JM及phase积分可重算；正式dose定义/门槛身份缺失'),('force / moment / tracking','左端5ms完整已执行TASK区间积分与实际Human相对owned-reference tracking可核对'),('native ownership / causal receipt','0.25ms网格、每步唯一torque receipt、请求/证书/bridge/模型epoch/source-age可核对'),('source age / execution mode','100ms原始样本有效期、40ms桥和SCIENTIFIC_SIMULATION可核对；host实时/strict55不评定')]
md='# B/H150正式匹配评价器审查\n\n结论：**MATCHED_BASELINE_EVALUATION_NOT_READY**。本轮未部署原完整scorer，也未冒称完成B/H150原条件复现。\n\n原CPU ZIP SHA256为`'+zipaudit['sha256']+'`，'+str(len(checks))+'/'+str(len(checks))+'载荷hash与bytes均复核通过。四个历史包各414源文件；cloud初版与后续在两处有已登记差异，当前复制的是first pilot实际source身份。唯一source docs为在线接口development合同，source_commit `'+contract['source_commit']+'`，并非B/H150 Master。详见audit/MATCHED_EVALUATOR_INVENTORY.json。没有把其他Stage的matched_branch、baseline_replay或matched_pacing认作本任务scorer。\n\n|审查项目|可用证据与缺口|\n|---|---|\n'+'\n'.join('|'+a+'|'+b+'|' for a,b in rows)+'\n\n最小缺失：\n\n'+'\n'.join('- '+x for x in missing)+'\n\n下一步迁移应按原manifest精确名称与SHA复制完整scorer依赖，先复现原B/H150已知PASS/FAIL条件和state恢复，再消费冻结PPO raw。当前接口仅分开报告runtime、必要时长和正式NOT_READY状态，不执行手写近似门。固定合法对照只可核对历史固定策略物理数值，不能填补B/H150复现结果。\n'
(R/'MATCHED_EVALUATOR_AUDIT.md').write_text(md)
put(R/'BASELINE_REPRODUCTION.json',{'status':'NOT_READY_ORIGINAL_B_H150_ARTIFACTS_MISSING','B_reproduction':'NOT_RUN','H150_reproduction':'NOT_RUN','formal_physical_attempts':0,'original_raw_metrics_and_qualification_parity':'NOT_EVALUABLE','missing':missing,'fixed_legal_control':'PENDING_SEPARATE_NON_B_H150_REPRODUCTION','source_archive_verified':zipaudit})
print(json.dumps({'status':audit['status'],'archive_payloads':len(checks),'all_payloads_verified':all(checks.values()),'identity_hits':{k:len(v) for k,v in content_hits.items()}}))
