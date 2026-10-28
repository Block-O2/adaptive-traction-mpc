"""Read-only replay of GP decision layers on their original candidate pools."""
import json, hashlib, collections
import numpy as np
from acl2_shared import P,put,read,utc,sha

def predict(model,pool):
    X=np.asarray(model['x']);K=np.exp(-np.sum((pool[:,None,:]-X[None,:,:])**2,axis=2)/(2*model['length']**2))
    mean=K@np.asarray(model['alpha'])*np.asarray(model['scale']);V=np.linalg.solve(np.asarray(model['L']),K.T)
    sd=np.sqrt(np.maximum(1e-10,1-np.sum(V*V,axis=0)))[:,None]*np.asarray(model['scale'])
    return mean,sd

def main():
    rows=[json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()]
    proposals=sorted((P/'predictions').glob('CORE_C_*.json'));data=[];errors=[]
    D={r['id']:r for r in rows}
    for pf in proposals:
        if pf.name.endswith('_POOL.json'):continue
        p=json.loads(pf.read_text())
        if not p.get('model_id'):continue
        ident=pf.stem;n=int(ident.rsplit('_',1)[1]);mf=P/'models'/('CORE_C_%03d.json'%n)
        if not mf.exists():errors.append('MISSING_MODEL:'+ident);continue
        m=json.loads(mf.read_text());poolpath=P/p['candidate_pool_path'];saved=json.loads(poolpath.read_text());pool=np.asarray(saved['pool']);nom=np.asarray(saved['anchored_nominal']);physics=np.asarray(saved['nominal_mask'],bool);allowed=np.asarray(saved['allowed_mask'],bool);mu,sd=predict(m,pool);mean=nom+mu
        modelid=hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()
        if modelid!=p['model_id']:errors.append('MODEL_ID:'+ident)
        def choose(values,mask):return int(np.argmin(np.where(mask,values,np.inf)))
        nominal_i=choose(nom[:,0],physics);mean_i=choose(mean[:,0],physics);lcb_i=choose(mean[:,0]-.5*sd[:,0],physics);final_i=choose(mean[:,0]-.5*sd[:,0],allowed)
        if final_i!=saved['chosen_index'] or not np.array_equal(pool[final_i],p['x']):errors.append('SAVED_DECISION_REPLAY:'+ident)
        if nominal_i!=saved['nominal_counterfactual_index']:errors.append('NOMINAL_COUNTERFACTUAL_REPLAY:'+ident)
        selected={}
        for name,index in [('nominal',nominal_i),('GP_mean_only',mean_i),('GP_LCB_same_physical_mask',lcb_i),('actual_GP_with_screen',final_i)]:
            selected[name]=dict(index=index,x=pool[index],nominal=nom[index],learned_mean=mean[index],learned_sd=sd[index],allowed_by_actual_final_mask=bool(allowed[index]))
        y=np.asarray(m['y']);target_motion=y[:,2]+nom[0,2]
        actual=D.get(ident)
        data.append(dict(id=ident,model_path=str(mf.relative_to(P)),model_sha256=sha(mf),candidate_pool_sha256=sha(poolpath),all_feedback_attempt_ids=m['all_feedback_attempt_ids'],cost_training_attempt_ids=m['training_attempt_ids'],undefined_full_cost_ids=m['undefined_full_JF_attempt_ids'],decisions=selected,GP_mean_changes_nominal=mean_i!=nominal_i,uncertainty_bonus_changes_mean=lcb_i!=mean_i,screen_changes_LCB=final_i!=lcb_i,final_changes_nominal=final_i!=nominal_i,completion_screen_had_candidates=p.get('completion_screen_had_candidates'),training_motion_target_min=float(target_motion.min()),training_motion_target_max=float(target_motion.max()),minimum_GP_motion_scale=float(np.asarray(m['scale'])[2]),complete=actual.get('complete') if actual else None,qualified=actual.get('qualified') if actual else None,actual_JF=actual.get('JF') if actual else None,actual_JM=actual.get('JM') if actual else None,nominal_error_on_executed_point=float(nom[final_i,0]-actual['JF']) if actual and actual['complete'] else None,GP_error_on_executed_point=float(mean[final_i,0]-actual['JF']) if actual and actual['complete'] else None))
    result=dict(utc=utc(),status='PASS' if not errors else 'FAIL',errors=errors,adaptive_proposals=len(data),decisions_changed=sum(r['final_changes_nominal'] for r in data),GP_mean_changes=sum(r['GP_mean_changes_nominal'] for r in data),uncertainty_layer_changes=sum(r['uncertainty_bonus_changes_mean'] for r in data),screen_layer_changes=sum(r['screen_changes_LCB'] for r in data),screen_had_candidates=sum(bool(r['completion_screen_had_candidates']) for r in data),rows=data,scope='Exact algorithmic replay of saved pre-execution pools/models; layer differences are not separate physical interventions or native benefit claims. Counterfactual physical value is assessed separately in frozen paired tests.',source_sha256=sha(__file__))
    put('GP_DECISION_LAYER_REPLAY.json',result);return result

if __name__=='__main__':main()
