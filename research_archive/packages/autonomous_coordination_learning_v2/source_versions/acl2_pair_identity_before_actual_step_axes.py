"""Zero-native semantic raw identity and actual coordinate-domain audit."""
import sys,json,time
import numpy as np
from acl2_shared import P,R,read,put,sha,utc
sys.path[:0]=[str(R/'control'),str(R/'code')]
import base_campaign

def pair(a,b,output):
    pa=R/'source/results'/a;pb=R/'source/results'/b
    inputs={str(f.relative_to(P)):sha(f) for p in [pa,pb] for f in [p/'trace.npz',p/'runtime_artifacts.json.gz']}
    target=P/output
    if target.exists():
        previous=read(output)
        if previous.get('input_sha256')==inputs:return previous
    result=base_campaign.compare_raw(pa,pb)
    result.update(utc=utc(),input_sha256=inputs,audit_source_sha256=sha(__file__),comparison_source_sha256=sha(base_campaign.__file__),physical_attempts_added=0,native_steps_added=0)
    put(output,result);return result

def coordinate():
    rows=[json.loads(x) for x in (P/'ALL_RESULTS.jsonl').read_text().splitlines()];D={r['id']:r for r in rows};pairs=[]
    for i in range(1,5):
        a='COORDINATE_NATIVE_%03d'%i;b='COORDINATE_ROTATED_%03d'%i
        if all(D.get(ident,{}).get('complete') for ident in [a,b]):pairs.append(pair(a,b,'audit/coordinate_pairs/common_%03d.json'%i))
    adaptive={};domain=[]
    for arm in ['NATIVE','ROTATED']:
        own=sorted([r for r in rows if r['id'].startswith('COORDINATE_'+arm+'_')],key=lambda r:r['id']);history=[];steps=[]
        for i,row in enumerate(own):
            x=np.asarray(row['action']['legacy']);domain.append(bool(np.all(abs(x)<=1+1e-12)))
            if arm=='ROTATED':
                u=np.asarray(row['action']['latent']);domain.append(bool(np.allclose([u[0]+u[1],u[0]-u[1]],x,atol=1e-12) and abs(u[0]+u[1])<=1+1e-12 and abs(u[0]-u[1])<=1+1e-12))
            if i>=4:
                center=min([D['COORDINATE_H150']]+[r for r in history if r['qualified']],key=lambda r:r['JF']);step=float(np.linalg.norm(x-np.asarray(center['action']['legacy'])))
                steps.append(dict(id=row['id'],center_id=center['id'],center_legacy=center['action']['legacy'],actual_legacy=x.tolist(),Euclidean_step=step))
            history.append(row)
        adaptive[arm]=steps
    full=all(len(adaptive[a])==4 for a in adaptive);matched=full and all(abs(a['Euclidean_step']-b['Euclidean_step'])<1e-12 for a,b in zip(adaptive['NATIVE'],adaptive['ROTATED']))
    out=dict(utc=utc(),status='FAIL' if any(x['status']!='PASS' for x in pairs) or not all(domain) or (full and not matched) else 'PASS' if len(pairs)==4 else 'PARTIAL_PAIRS',common_pairs_audited=len(pairs),common_pairs=pairs,actual_legacy_domain_and_rotated_diamond_preserved=all(domain),adaptive_step_check='PASS' if matched else 'FAIL' if full else 'NOT_RUN_ALL_FOUR',adaptive_steps=adaptive,physical_attempts_added=0,native_steps_added=0,scope='Physical scientific traces and native receipt fields; wall profiling and case-label metadata excluded. Legacy action actually consumed by the worker is checked, independently of unused informational family defaults in its config.',source_sha256=sha(__file__))
    put('audit/COORDINATE_COMMON_DESIGN_RAW_IDENTITY.json',out);print('COORDINATE_IDENTITY',out['status'],out['adaptive_step_check'],flush=True)

def response():
    a='RESPONSE_MODEL_01';b='RESPONSE_NATIVE_SCALAR_COUNTERFACTUAL';af=P/'attempts'/(a+'_RESULT.json');bf=P/'attempts'/(b+'_RESULT.json')
    if not af.exists() or not bf.exists():print('RESPONSE_IDENTITY NOT_RUN',flush=True);return
    da=json.loads(af.read_text());db=json.loads(bf.read_text())
    same=json.dumps(da['action'],sort_keys=True)==json.dumps(db['action'],sort_keys=True)
    if not same or not da['complete'] or not db['complete']:
        put('audit/RESPONSE_SAME_ACTION_RAW_IDENTITY.json',dict(status='ACTIONS_DIFFER' if not same else 'INCOMPLETE_NOT_COMPARED',same_action=same,native_steps_added=0));return
    out=pair(a,b,'audit/RESPONSE_SAME_ACTION_RAW_IDENTITY.json');print('RESPONSE_IDENTITY',out['status'],flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='response':response()
    else:coordinate()
