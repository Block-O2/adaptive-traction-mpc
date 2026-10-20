from pathlib import Path
import json
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name
f=P/'ATTEMPT_ACCOUNTING.json';a=json.loads(f.read_text())
for r in a['attempts']:
 d=json.loads((P/'output'/(r['id']+'_DATA.json')).read_text());c=d.get('child');condition=d['condition']
 r['parent_state_source']=dict(kind='LEGAL_COLD_COMMISSIONING_THEN_NATIVE_PREFIX' if c is None else 'COMPLETE_LIVE_ADDRESS_SPACE_FORK_NO_HUMAN_REPLAY',condition=condition,parent_id=None if c is None else condition['name']+'_parent',full_parent_hash=None if c is None else d['branch_start']['full_hash'],native_parent_hash=None if c is None else d['branch_start']['native_hash'],fork_physical_s=None if c is None else c['physical_time_at_fork'],inherited_native_steps=0 if c is None else c['physics_step_at_fork'],shared_task_prefix_J_F_N_s=None if c is None else c['start_J_F'])
 r['native_steps']=dict(actual_new=r['actual_new_native_steps'],full_including_inherited=r['total_including_inherited_native_steps'],inherited=r['parent_state_source']['inherited_native_steps'])
 a['serial_execution']='One flock owner. Parent pauses for each child; child joined before next START. Parent START/END encloses paused forks; no simultaneous physics integration.'
f.write_text(json.dumps(a,indent=2,ensure_ascii=False)+'\n');print('ACCOUNT_PARENT_LINEAGE_ENRICHED')
