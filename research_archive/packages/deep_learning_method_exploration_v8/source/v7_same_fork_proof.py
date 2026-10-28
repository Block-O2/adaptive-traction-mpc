"""Require exact complete controller/address-space manifests for one local data set."""
from pathlib import Path
import json,sys,hashlib,time
P=Path(__file__).resolve().parents[1];g=sys.argv[1]
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
bound={};rows=[]
for tag in ['V6PHASE','REL_M','REL_P','SPD_M','SPD_P','MM','MP','PM','PP']:
 f=P/'runtime/reports'/(g+'_'+tag+'_SNAPSHOT.json');s=json.loads(f.read_text())
 r=P/'attempts'/(g+'_'+tag+'_RESULT.json');d=json.loads(r.read_text());assert d['complete'],'DATASET_INCOMPLETE'
 for q in [f,r]:bound[str(q.relative_to(P))]=sha(q)
 assert s['interface_scientific_state'] is not None
 rows.append({'id':d['id'],'snapshot_file_sha256':sha(f),'full_controller_hash':s['hash'],'native_integration_sha256':s['manifest']['native_integration']['sha256'],'interface_scientific_state':s['interface_scientific_state'],'opaque_fork_preserved':s['opaque_fork_preserved']})
assert len({r['snapshot_file_sha256'] for r in rows})==1,'FULL_SNAPSHOT_FILE_DIFFERS'
assert len({r['full_controller_hash'] for r in rows})==1,'FULL_CONTROLLER_MANIFEST_MISMATCH'
assert len({r['native_integration_sha256'] for r in rows})==1,'NATIVE_PARENT_MISMATCH'
assert len({json.dumps(r['interface_scientific_state'],sort_keys=True) for r in rows})==1,'INTERFACE_PARENT_MISMATCH'
assert json.loads((P/'owned'/(g+'_SUPERVISOR_END.json')).read_text())['worker_exit_code']==0
f=P/'jobs'/g/'SOURCE_MANIFEST.json';bound[str(f.relative_to(P))]=sha(f)
q=P/'audit'/(g+'_LOCAL_FULL_PARENT_EQUIVALENCE.json');assert not q.exists(),'PROOF_IS_IMMUTABLE'
out={'status':'PASS','groups':[g],'rows':rows,'bound_files_sha256':bound,'created_unix':time.time(),'source_sha256':sha(Path(__file__)),'equivalence':'Exact original full state manifest and interface state, no canonical deletion or tolerance. One Linux parent, fork copy; all opaque handles recorded fork_preserved by original manifest. No cross-job pooling.','independent_state_evidence':False}
tmp=q.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(q);print('EXACT_SAME_FORK_PARENT_PASS',g,len(rows),rows[0]['full_controller_hash'])
