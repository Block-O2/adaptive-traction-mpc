"""Document already registered choices without changing scientific rules or source."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True);args=parser.parse_args();root=args.package
    def read(name):return json.loads((root/name).read_text())
    contract=root/'PATIENT_VARIATION_CONTRACT.md';original=contract.read_bytes();original_hash=sha(contract)
    backup=root/'audit/PATIENT_VARIATION_CONTRACT_BEFORE_ADOPTION_NOTE.md';backup.parent.mkdir(parents=True,exist_ok=True)
    if backup.exists():assert backup.read_bytes()==original,'EXISTING_ADOPTION_BACKUP_DIFFERS'
    else:backup.write_bytes(original)
    cohort=read('VIRTUAL_PATIENT_COHORT.json');reg=read('PREREGISTRATION.json');manifest=read('EXECUTION_CODE_MANIFEST.json');env=read('ENVIRONMENT.json')
    order=cohort['order'];assert order==[f'P{i:02d}' for i in range(12)]
    assert sha(root/'VIRTUAL_PATIENT_COHORT.json')==reg['cohort_sha256']
    source_binding=manifest['files'].get('PATIENT_VARIATION_CONTRACT.md')
    if source_binding is not None:assert source_binding==original_hash
    events=[json.loads(line) for line in (root/'ATTEMPTS.jsonl').read_text().splitlines() if line.strip()]
    first_start=min(e['unix'] for e in events if e['event']=='START')
    assert reg['registered_unix']<first_start
    mass=[]
    for patient in cohort['patients']:
        pid=patient['patient_id'];p=patient['physical'];static=read(f'patients/{pid}/static/MODEL_STATIC_AUDIT.json');props=static['resolved_properties']
        assert p['body_mass_kg']==75.0
        assert abs(props['thigh_mass_kg']-75*.099*p['thigh_mass_scale'])<1e-10
        assert abs(props['shank_mass_kg']-75*.060*p['shank_mass_scale'])<1e-10
        mass.append(dict(patient_id=pid,body_mass_kg=p['body_mass_kg'],thigh_mass_scale=p['thigh_mass_scale'],shank_mass_scale=p['shank_mass_scale'],
            actual_thigh_mass_kg=props['thigh_mass_kg'],actual_shank_mass_kg=props['shank_mass_kg'],static_audit_sha256=sha(root/f'patients/{pid}/static/MODEL_STATIC_AUDIT.json')))
    versions={}
    for name in ['mujoco','numpy']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    selected={}
    for name in ['patient_models.py','cross_runner.py','serial_campaign.py','control/campaign_v2.py']:
        if (root/name).exists():selected[name]=dict(sha256=sha(root/name),frozen_manifest_sha256=manifest['files'].get(name))
    now=datetime.now(timezone.utc);local=now.astimezone(timezone(timedelta(hours=8)))
    registered=datetime.fromtimestamp(reg['registered_unix'],timezone.utc).astimezone(timezone(timedelta(hours=8))).isoformat()
    result=dict(status='ADOPTION_DOCUMENTATION_ONLY_NO_PROTOCOL_CHANGE',documented_utc=now.isoformat(),documented_Asia_Shanghai=local.isoformat(),
        original_contract_sha256=original_hash,backup_path=str(backup),backup_sha256=sha(backup),original_contract_unchanged=sha(contract)==original_hash,
        original_contract_bound_in_execution_manifest=source_binding is not None,original_contract_hash_present_in_preregistration=original_hash in json.dumps(reg),
        preregistration_sha256=sha(root/'PREREGISTRATION.json'),preregistration_time_Asia_Shanghai=registered,cohort_sha256=reg['cohort_sha256'],
        registered_before_first_START=reg['registered_unix']<first_start,adopted_order=order,mass_implementation='SEGMENT_MASS_MULTIPLIERS_WITH_BASE_BODY_MASS_75_KG_RETAINED',
        mass_rows=mass,source_manifest_sha256=sha(root/'EXECUTION_CODE_MANIFEST.json'),selected_source_bindings=selected,environment=env,
        python_executable=sys.executable,python_version=platform.python_version(),installed_distribution_versions=versions,
        source_of_distribution_versions='importlib.metadata only; no simulator imported',native_dt_s=.00025,control_trace_dt_s=.005,
        outcomes_added=False,scientific_rules_changed=False,frozen_files_changed=False,new_physics_starts=0)
    text=f'''# 参数合同最终采用说明（记录说明，不修改预注册）

记录时间：{local.isoformat()}（Asia/Shanghai）；原预注册时间：{registered}。

本说明解释 `PATIENT_VARIATION_CONTRACT.md` 草案中已经由执行前预注册确定的选择。草案原始字节保持不变，备份为 `audit/PATIENT_VARIATION_CONTRACT_BEFORE_ADOPTION_NOTE.md`，SHA-256 为 `{original_hash}`。原草案是否绑定于执行源码 manifest：{str(source_binding is not None).lower()}；是否在 `PREREGISTRATION.json` 中记录其独立哈希：{str(result['original_contract_hash_present_in_preregistration']).lower()}。因此不把本次补充说明回写成历史预注册文件，也不宣称新增了一项执行前注册。

实际采用的患者顺序为 **P00 → P01 → P02 → P03 → P04 → P05 → P06 → P07 → P08 → P09 → P10 → P11**。依据是执行前的 `VIRTUAL_PATIENT_COHORT.json::order`、`PREREGISTRATION.json` 和 `serial_campaign.py`。队列文件 SHA-256 为 `{reg['cohort_sha256']}`，核对结果与预注册一致，注册时间早于首个 START。草案曾给出的另一“建议顺序”没有被采用；本说明不依据后来结果调整次序、患者或阈值。

质量扰动统一采用现有 `HiddenHumanV2` 的 `thigh_mass_scale` / `shank_mass_scale`，构造基准 `body_mass_kg=75.0` 在全部 12 个配置中保留。段质量为 `75 × 0.099 × thigh_mass_scale` 和 `75 × 0.060 × shank_mass_scale` kg，未再对基准体重重复缩放。P01 使用 0.8/0.8，P02 使用 1.2/1.2，P11 使用 1.1/0.9；所有实际段质量已逐项与 `patients/{{id}}/static/MODEL_STATIC_AUDIT.json::resolved_properties` 一致核对。COM、长度和惯量仍按原生成模型一致更新。这里的 75 kg 是构造基准参数；这些是下肢段的工程敏感性扰动，不构成临床体重或人体参数分布声明。

实际执行环境为 `{env['distribution']}`，Python `{sys.executable}`（{platform.python_version()}），MuJoCo 安装发行版 `{versions['mujoco']}`，NumPy `{versions['numpy']}`。原生物理步长为 0.25 ms，控制/主积分轨迹为 5 ms，证据模式为 `SCIENTIFIC_SIMULATION`。版本号通过安装包元数据读取，本说明未导入或启动模拟器。

规范源码位置为 `{env['canonical']}`，历史冻结来源为 `{env['historical_source']}`，执行源码总 manifest SHA-256 为 `{result['source_manifest_sha256']}`。生成侧是 `patient_models.py` 和冻结 `source/.../fresh_qualification_v1/scenario.py::hidden_plant / HiddenHumanV2`；执行侧是 `cross_runner.py` 继承冻结 `control/campaign_v2.py`，由 `serial_campaign.py` 串行拥有各患者进程。每患者实际模型/控制先验身份见 `audit/{{id}}_RUNTIME_MODEL_IDENTITY.json`；P0 控制先验仍是冻结 `high_rom_deployable_prior`，真实患者参数只进入 plant 生成及离线审计。该身份核对不等价于任务通过。

本说明不重写患者参数、B/H150 动作、任务目标、安全界限、运动接受协议、失败规则、积分口径或未来患者保留规则。P1 仍仅为协议，Learning 未训练。全部执行结局及分母另见 `CROSS_PATIENT_EXPERIMENT_RESULTS.json`、`CROSS_PATIENT_QUALIFICATION.json`、`derived/REPORT_STATISTICS.json` 和最终报告；本文件不添加任何成功或失败结论。

机器可核验记录：`audit/CONTRACT_ADOPTION_RECORD.json`。P09–P11 在当前描述性研究中已暴露，未来若据此设计模型或控制策略，需要另外未接触的患者身份作为确认集。
'''
    (root/'CONTRACT_ADOPTION.md').write_text(text,encoding='utf-8')
    result['adoption_note_sha256']=sha(root/'CONTRACT_ADOPTION.md')
    (root/'audit/CONTRACT_ADOPTION_RECORD.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    assert contract.read_bytes()==original and backup.read_bytes()==original
    print(json.dumps({'status':result['status'],'original_contract_unchanged':True,'frozen_bound':source_binding is not None,'source_manifest_sha256':result['source_manifest_sha256'],'versions':versions,'physics_starts':0}))
if __name__=='__main__':main()
