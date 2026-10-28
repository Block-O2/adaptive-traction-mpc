"""Closeout-only schema enrichment; preserves original log and timing identity.

Missing budget usage is reconstructed from timestamped admission/settlement.
Enrichment is explicitly later annotation, never a backdated preregistration.
"""
from datetime import datetime
import hashlib,json,time
from research_common import ROOT,HARD_STOP,NO_TRAIN,atomic,read,now,sha

def epoch(s):return datetime.fromisoformat(s).timestamp()
def enrich():
    p=ROOT/'RESEARCH_DECISION_LOG.jsonl';original=p.read_text();lines=original.splitlines()
    source_hash=hashlib.sha256(original.encode()).hexdigest()
    archive=ROOT/'audit'/f'DECISION_LOG_PRE_ENRICHMENT_{source_hash}.jsonl'
    if not archive.exists():archive.write_text(original)
    ledger=read(ROOT/'LEDGER.json',{});attempts=ledger.get('attempts',[]);out=[]
    for i,line in enumerate(lines,1):
        a=json.loads(line);at=epoch(a['time_utc']);started=[x for x in attempts if epoch(x['start_utc'])<=at]
        ended=[x for x in started if x.get('end_utc') and epoch(x['end_utc'])<=at]
        settled_native=sum(x.get('native_steps',0) for x in ended)
        outstanding=sum(x['reserved_native_steps'] for x in started if x not in ended)
        if 'budget' not in a:
            a['budget']=dict(training_attempts=sum(x['kind']=='training' for x in started),
                evaluation_attempts=sum(x['kind']=='evaluation' for x in started),
                settled_native_steps=settled_native,outstanding_native_reservations=outstanding,
                training_hard_cap=450,evaluation_hard_cap=60,native_hard_cap=50000000,
                remaining_wall_s=max(0.,HARD_STOP-at),no_new_training_unix=NO_TRAIN,hard_stop_unix=HARD_STOP,
                origin='LATER_RECONSTRUCTION_FROM_TIMESTAMPED_ATTEMPT_LEDGER')
        a.setdefault('risks',[a.get('risk','Known nominal; G4/live matched/independent legal initial-state gaps remain')])
        a.setdefault('stop_conditions',['Original fixed task/safety and causal contract','10-hour/attempt/native/resource hard limits','New safety/causal/evidence risk'])
        a.setdefault('hypotheses_accepted',[]);a.setdefault('hypotheses_rejected',[])
        if a['event']=='CONTROL_IDENTITY' and a['evidence'].get('strict_paired_reuse'):
            a['hypotheses_accepted']=['Exact state/rollout equivalence supports reuse of original paired Control051–080']
        a['schema_annotation']=dict(annotated_utc=now(),original_log_sha256=source_hash,
             original_line=i,original_line_sha256=hashlib.sha256(line.encode()).hexdigest(),
             original_fields_preserved=True,scientific_gate_or_decision_changed=False)
        out.append(a)
    content=''.join(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n' for x in out)
    tmp=p.with_suffix('.enriching');tmp.write_text(content);tmp.replace(p)
    atomic(ROOT/'audit/DECISION_SCHEMA_VERIFICATION.json',dict(time_utc=now(),entries=len(out),
         original_log=str(archive),original_sha256=source_hash,enriched_sha256=sha(p),
         all_required_fields=all(all(k in x for k in ['evidence','next','budget','risks','stop_conditions','hypotheses_accepted','hypotheses_rejected']) for x in out),
         note='Schema and timestamped budget context annotation only; no decision rewritten or backdated.'))
    return len(out)
if __name__=='__main__':print('decision entries enriched',enrich())
