from pathlib import Path
import json, shutil, hashlib, time
P=Path(__file__).resolve().parents[1]
Q=P.parent/'m2_18d_baseline_qualification_v1'
def put(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
f=P/'control/campaign.py';s=f.read_text()
s=s.replace("OLD=json.loads((P/'FROZEN_18D.json').read_text())", "OLD=json.loads((P/'FROZEN_18D.json').read_text());NEW=json.loads((P/'CANDIDATE.json').read_text());REPAIR=json.loads((P/'BOUNDED_REPAIR.json').read_text())")
s=s.replace("n<40", "n<PLAN['physics_budget']")
s=s.replace("self.arm!='E'", "self.arm not in ['E','C','C_repeat','R','R_repeat']")
s=s.replace("if self.arm=='E':", "if self.arm in ['E','C','C_repeat','R','R_repeat']:")
s=s.replace("planner.free_parameters=np.asarray(OLD['free_parameters'],float)", "planner.free_parameters=np.asarray((NEW if self.arm in ['C','C_repeat'] else REPAIR if self.arm in ['R','R_repeat'] else OLD)['free_parameters'],float)")
s=s.replace("needed=0 if GROUP=='reproduction' else 1", "needed=0 if GROUP in ['reproduction','development'] else 1")
s=s.replace("for arm in ['B','E']:", "arms=['B','E'] if GROUP=='reproduction' else ['B','E','C','C_repeat'] if GROUP=='N2' else ['B','E',read('DEVELOPMENT_SELECTION.json')['selected']]\n   if GROUP=='development':arms.append(arms[-1]+'_repeat')\n   for arm in arms:")
s=s.replace("if GROUP=='reproduction':\n     oldid", "if GROUP=='N2' and arm=='C_repeat':\n     cr=next(x for x in self.results if x['arm']=='C')\n     if not (cr['motion']['acceptance_pass'] and cr['motion']['gain_percent']>=1.):\n      put('audit/C_FIRST_FAILURE.json',dict(classification='SCIENTIFIC_HYPOTHESIS_FAILURE',implementation_contract='PASS',failed=cr['motion']['failed_requirements'],bounded_repair='Predeclared full OUTBOUND half scale; same live parent, new attempts, no threshold changes'));arms.extend(['R','R_repeat'])\n    if GROUP=='reproduction':\n     oldid")
s=s.replace("if GROUP=='reproduction':\n     oldid", "if GROUP=='reproduction':\n     oldid")
s=s.replace("bdata=read('output/'+GROUP+'_B_DATA.json');edata=read('output/'+GROUP+'_E_DATA.json')", "bdata=read('output/'+GROUP+'_B_DATA.json');edata=read('output/'+GROUP+'_E_DATA.json')\n   for row in self.results:\n    assert read('output/'+row['id']+'_DATA.json')['branch_start']['full_hash']==bdata['branch_start']['full_hash'],'UNMATCHED_CANDIDATE'\n   for candidate in ['C','R']:\n    if any(x['arm']==candidate+'_repeat' for x in self.results):\n     repeat=compare_raw(P/'source/results'/(GROUP+'_'+candidate),P/'source/results'/(GROUP+'_'+candidate+'_repeat'));put('audit/'+GROUP+'_'+candidate+'_REPEAT.json',repeat);assert repeat['status']=='PASS','CANDIDATE_REPEAT_FAIL'")
s=s.replace("cond=dict(name=GROUP,seed=PLAN['seed'],prefix={}) if GROUP=='reproduction' else next", "cond=dict(name=GROUP,seed=PLAN['seed'],prefix={}) if GROUP in ['reproduction','development'] else next")
f.write_text(s)
f=P/'control/own_campaign.py';s=f.read_text().replace("['reproduction']+", "['reproduction','development']+");f.write_text(s)
# Keep independent arithmetic isolated from the controller. Generalize only arm enumeration.
f=P/'control/independent_recompute.py';s=f.read_text().replace("checks=[measure(g+'_'+arm) for arm in ['parent','B','E']]", "checks=[measure(g+'_parent')]+[measure(r['id']) for r in read(g+'_RESULTS.json')['rows']]")
f.write_text(s)
# Original byte-preserved numerical motion/safety evaluator, no algorithm changes.
put('audit/PREPHYSICS_CHANGE_DESCRIPTION.json',dict(unix=time.time(),controller_source_changes='none',harness_changes='Versioned campaign adds globally fixed candidate arms, all-arm full-hash match, exact deterministic repeat and bounded budgets. Original matched fork and analyzers unchanged.',candidate_changed_indices=[3,4,13],repair_changed_indices=[0,1,2,3,4,10,11,12,13],source= str(Q)))
print('PREPARED')
