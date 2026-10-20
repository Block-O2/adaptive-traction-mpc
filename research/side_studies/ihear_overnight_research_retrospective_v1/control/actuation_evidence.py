"""Independent streaming evidence, no runner/model import and no simulation."""
from pathlib import Path
import os,json,gzip,time,hashlib,collections,sys,xml.etree.ElementTree as ET
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
PRECHECK='--precheck' in sys.argv
def load(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()
def array_items(path,key):
    with gzip.open(path,'rt') as f:
        buffer='';needle='"'+key+'":';decoder=json.JSONDecoder()
        while True:
            part=f.read(65536)
            if not part:raise ValueError('REQUIRED_RUNTIME_ARRAY_MISSING:'+key)
            buffer+=part;index=buffer.find(needle)
            if index>=0:
                buffer=buffer[index+len(needle):].lstrip()
                while not buffer:
                    part=f.read(65536)
                    if not part:raise ValueError('REQUIRED_RUNTIME_ARRAY_EOF:'+key)
                    buffer+=part;buffer=buffer.lstrip()
                assert buffer.startswith('[');buffer=buffer[1:];break
            buffer=buffer[-len(needle):]
        while True:
            buffer=buffer.lstrip(', \n\r\t')
            if buffer.startswith(']'):return
            try:value,end=decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                part=f.read(65536)
                if not part:raise ValueError('UNEXPECTED_ARRAY_EOF')
                buffer+=part
                if len(buffer)>4*2**20:raise ValueError('RUNTIME_ARRAY_ITEM_TOO_LARGE:'+key)
                continue
            yield value;buffer=buffer[end:]
def main():
    selection_path=S/'FROZEN_SELECTION.json'
    if selection_path.exists():
        selection=load(selection_path);ids=[selection['best']['base_id'],selection['best']['id'],selection['diagnostic']['id']];selection_kind='FROZEN'
    else:
        assert PRECHECK,'FROZEN_SELECTION_REQUIRED_FOR_FINAL_ACTUATION_EVIDENCE'
        evaluations=[json.loads(x) for x in (S/'EVALUATIONS.jsonl').read_text().splitlines() if x.strip()]
        complete=[r for r in evaluations if (S/'source/results'/r['id']/'runtime_artifacts.json.gz').is_file()]
        accepted=[r for r in complete if r['comparison']['acceptance_pass']]
        assert accepted,'NO_COMPLETE_ACCEPTED_REFERENCE_FOR_PRECHECK'
        best=min(accepted,key=lambda r:r['J_F_N_s']);strong=min(complete,key=lambda r:r['J_F_N_s'])
        ids=[best['base_id'],best['id'],strong['id']];selection_kind='INTERIM_COMPLETED_ROWS_NOT_FROZEN'
    xml=S/'source/stages/stage5_personalized_motion_learning/models/cr12_v0.xml'
    old_xml=Path(load(S/'RUN_PLAN.json')['original_sources'])/'source/stages/stage5_personalized_motion_learning/models/cr12_v0.xml'
    assert sha(xml)==sha(old_xml),'ROBOT_XML_CHANGED_FROM_ORIGINAL'
    elements=ET.parse(xml).getroot().find('actuator');motors={r.attrib['name']:r.attrib for r in elements}
    names=[f'joint{i}_torque' for i in range(1,7)];assert len(motors)==6 and set(motors)==set(names),'ACTUATOR_AUTHORITY_CHANGED'
    ranges=np.array([[float(x) for x in motors[name]['ctrlrange'].split()] for name in names]);assert ranges.shape==(6,2) and np.all(np.isfinite(ranges)) and np.all(ranges[:,0]<ranges[:,1])
    limits=ranges[:,1];assert all(float(motors[name]['gear'])==1 for name in names)
    rows=[]
    for ident in dict.fromkeys(ids):
        raw=S/'source/results'/ident/'runtime_artifacts.json.gz';data=load(S/'output'/(ident+'_DATA.json'));fork=(data.get('child') or {}).get('physical_time_at_fork',0.)
        measured=load(S/'reports'/(ident+'_MEASURED.json'));assert data['metric']['task_valid'],'ACTUATION_REPRESENTATIVE_NOT_COMPLETE_VALID_TASK'
        expected_total=int(measured['native_steps']);expected_new=int(data['metric']['actual_new_native_physics_steps'])
        maximum=np.zeros(6);task_maximum=np.zeros(6);n=0;new=0;nonzero=0;with_contact=0;contact_samples=[];previous=None;dt_error=0.
        for r in array_items(raw,'native_states_evaluation_only'):
            assert all(key in r for key in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only']),'NATIVE_REQUIRED_FIELD_MISSING'
            assert np.isfinite(r['time_s']) and np.all(np.isfinite(np.asarray(r['qpos_evaluation_only']))) and np.all(np.isfinite(np.asarray(r['qvel_evaluation_only']))),'NATIVE_STATE_NONFINITE'
            torque=np.asarray(r['command_torque_nm']);assert torque.shape==(6,) and np.all(np.isfinite(torque))
            assert np.all(torque>=ranges[:,0]-1e-8) and np.all(torque<=ranges[:,1]+1e-8),'ROBOT_TORQUE_RANGE_FAILURE'
            maximum=np.maximum(maximum,abs(torque));n+=1;nonzero+=bool(np.any(abs(torque)>1e-12))
            if r['time_s']>fork+1e-9:new+=1;task_maximum=np.maximum(task_maximum,abs(torque))
            if previous is not None:dt_error=max(dt_error,abs(r['time_s']-previous-.00025))
            previous=r['time_s']
            if r.get('contact_pairs_evaluation_only'):
                with_contact+=1
                if len(contact_samples)<3:contact_samples.append(r['contact_pairs_evaluation_only'])
        receipts=[];all_receipts=0
        for r in array_items(raw,'command_receipts'):
            all_receipts+=1
            assert all(key in r for key in ['receipt_index','applied','native_steps','start_physics_s','end_physics_s']),'RECEIPT_REQUIRED_FIELD_MISSING'
            if r['applied'] and r['native_steps']>0:receipts.append(r)
        assert n>0 and n==expected_total,'NATIVE_COUNT_VS_MEASURED_MISMATCH'
        assert new==expected_new,'NEW_SUFFIX_COUNT_VS_PHYSICAL_WORK_MISMATCH'
        assert all_receipts>0 and receipts,'EMPTY_REQUIRED_COMMAND_RECEIPTS'
        assert sum(r['native_steps'] for r in receipts)==n,'APPLIED_RECEIPT_NATIVE_STEP_TOTAL'
        assert dt_error<1e-10,'NATIVE_DT'
        lineage=load(S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'));assert lineage['status']=='PASS'
        rows.append(dict(id=ident,native_rows=n,expected_native_rows=expected_total,actual_new_rows=new,expected_actual_new_rows=expected_new,nonzero_torque_rows=nonzero,motor_names=names,torque_limits_Nm=limits.tolist(),torque_lower_limits_Nm=ranges[:,0].tolist(),
                         max_abs_torque_Nm=maximum.tolist(),new_suffix_max_abs_torque_Nm=task_maximum.tolist(),applied_positive_step_receipts=len(receipts),
                         exact_native_receipt_ownership=lineage['status'],contact_row_count=with_contact,contact_pair_samples=contact_samples,
                         native_dt_max_error_s=dt_error,complete_raw_preserved=True,raw_sha256=sha(raw)))
    output=dict(status='PASS',final=not PRECHECK,selection_scope=selection_kind,generated_unix=time.time(),physics_attempts_added=0,source='streamed original native/receipt arrays; XML torque ranges, gear=1, six robot actuators; no runner import',rows=rows,robot_XML_sha256=sha(xml),
                human_actuator_added=False,no_human_qpos_qvel_actuation_claim='unchanged plant source and isolated planner source audit; reset only original lawful cold initialization',
                no_hardware_actuation=True,formal_level3_or_clinical_claim=False)
    target=W/'audit/ACTUATOR_HARDENING_PRECHECK.json' if PRECHECK else S/'ACTUATOR_CONTACT_EVIDENCE.json'
    target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    print('ACTUATION_CONTACT_EVIDENCE_PASS',len(rows))
if __name__=='__main__':main()
