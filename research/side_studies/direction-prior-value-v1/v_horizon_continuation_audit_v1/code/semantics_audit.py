from audit_common import *
def main():
 files=('planning.py','interfaces.py','data_collection.py','known_model.py','train.py','study_common.py')
 sources={name:dict(path=str(OLD/'code'/name),sha256=sha(OLD/'code'/name)) for name in files}
 horizons=[]
 for p in (OLD/'output').glob('*_DATA.json'):
  r=read(p)
  for row in r.get('value_rows',[]):
   pred=row.get('model_prediction')
   if pred:horizons.append(dict(source=str(p),start_task_s=row['context']['task_s'],terminal_task_s=pred['terminal']['task_s'],near_seconds=pred['terminal']['task_s']-row['context']['task_s'],interior=pred['terminal']['interior_opportunities'],phase_start=row['context']['phase'],phase_terminal=pred['terminal']['phase']))
 save(STUDY/'SOURCE_SEMANTICS.json',dict(status='SOURCE_AUDIT_COMPLETE_BEFORE_PHYSICS',unix=time.time(),sources=sources,model_horizon='NO_SINGLE_FIXED_HORIZON',model_full_rollout='analytic schedules to current single task RETURN endpoint plus phase-end wait; max16 schedule loop iterations; HOLD=1.02s; endpoint wait to9.005s per movement phase',near_value_split='first accumulated3 interior modifiable opportunities OR first current movement endpoint, whichever occurs first',value_horizon='from synthetic model terminal node through end of current OUTBOUND/HOLD/RETURN repetition',label_horizon='from actual causal native boundary to actual COMPLETE of same repetition',label_continuation='native-certified-committed-K3-suffix-v1',online_continuation='selected current row applied, next decision re-searches; previous full plan always a candidate after first search; no unconditional suffix guarantee',near_plus_base='exact arithmetic total_cost=near_cost+V_base; deltaV evaluated anew on each candidate terminal feature',safety_margin_semantics='50ms/segment and500ms settling only screening metadata; not an explicit model/value horizon and not integrated cost',repetition_semantics='PASS_CURRENT_REPETITION_ONLY',case='H3 event/pending-suffix driven with full-repetition cost-to-go (H1 finite near split, but full analytic P continuation already present)',observed_label_model_splits=horizons))
 text='''# Exact frozen V semantics audit

This document is saved before any new physics dispatch. Sources and SHA256 are in SOURCE_SEMANTICS.json. No algorithm or repetition semantics are changed.

| Timeline point | Exact code behavior | Cost interval / ownership |
|---|---|---|
| t0 native interior request | causal55D, previous actually applied K3, counts; native B target inspected on cloned estimated planner | actual measured force integral F0 recorded by logger |
| candidate generation | 2 generations x8: B zero, first qualified unlearned K3 seed / later previous plan, six CEM or <=3 G replacements; executed rows overwritten with previous plan past | table shape2x5x3; OUTBOUND5 rows and RETURN5 rows, one row per native interior opportunity; knots sampled once on each native target, not three decisions |
| model predict | clone native planner+arguments, estimated scheduler/certification; known beta/geometry used only research inverse dynamics; n12 left-endpoint wrench samples per analytic schedule | full remaining single OUTBOUND/HOLD/RETURN task, loop cap16; q/dq forecast with exp(-4t/duration) error decay |
| t* near/value split | first3 interior opportunities OR current phase endpoint; set terminal before switching phase or adding endpoint wait | near=[t0,t*]; terminal preserves current phase and counts; seconds vary with state, target and accepted schedules: NO_SINGLE_FIXED_HORIZON |
| after t* | predictor keeps rolling through remaining committed table, B-owned terminal, HOLD1.02s, endpoint static wait max(0,9.005-phase_elapsed) | V_base=total_model-near, interval[t*,model task end]; P already predicts this remainder analytically |
| screening | predicted smooth movement arrival +0.050s xsegment count +0.500s <=9.020s | feasibility estimate only; neither margin is a value horizon; rejected candidates receive no online V score |
| V score | DeltaV=network(terminal103D), pending executed rows masked, previous3K maintained; P_score=near+V_base; PV=P_score+DeltaV | trained residual target at actual causal boundary: actual same committed remainder - model same committed remainder |
| selected plan | minimum across both generations; assigns previous_plan and table, increments only current interior count | applies only current K3 row through native request; HOLD/terminal remains B-owned |
| next native modifiable request | fresh context; previous_plan included explicitly in BOTH generations; new CEM/G; fresh predict+V for every accepted candidate | selected suffix can replace previous suffix; old numeric V is never cached or reused; carry is candidate, not guaranteed selected |
| label branch | selected table fixed through all future interior requests; native certification/rejection/fallback active, no performance replanning | records actual native boundaries including logger-only terminal contexts; label=final J_F-prefix_J_F - fresh model total at identical recorded context+table+counts |
| repetition end | one task ends at COMPLETE; no repetition loop in label collector or predictor | current repetition only: PASS; timeout30s is a failure ceiling, not target horizon; n+1 cost never enters |

Near and V_base are algebraically non-overlapping. The physical future does not follow the identical analytic clock: bridge/receipt ticks, tracking and settling are approximate and cost margins are not added explicitly. Actual-minus-model labels can absorb these errors under committed continuation; this does not prove calibrated synthetic-terminal features or rolling continuation. These issues will be measured separately.

Intended future semantics are frozen in REPETITION_CONTRACT.json: each V_n ends at repetition n completion; memory may transfer only through retained plans/data/priors/parameters/belief. Current single-repetition implementation is not modified.
'''
 (STUDY/'SEMANTICS.md').write_text(text)
 print(json.dumps(dict(status='SOURCE_AUDIT_COMPLETE_BEFORE_PHYSICS',label_split_samples=len(horizons),near_seconds_range=[min(r['near_seconds'] for r in horizons),max(r['near_seconds'] for r in horizons)])))
if __name__=='__main__':main()
