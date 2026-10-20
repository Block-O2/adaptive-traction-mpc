"""Create new isolated execution closure; never alter an old package."""
from pathlib import Path
import os,json,time,shutil,hashlib
LOCAL=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');A=S/'m2_18d_autonomous_review_v1';P=S/LOCAL.name
assert not P.exists(),'NEVER_OVERWRITE'
P.mkdir()
for d in ['audit','provenance','control','reports','output','motion_series','logs','derived','tmp','figures']:(P/d).mkdir()
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
for d in ['source','code','deps','weights']:
 shutil.copytree(A/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
(P/'source/results').mkdir()
rebased=[]
for d in ['source','code','deps']:
 for f in (P/d).rglob('*'):
  if not f.is_file() or f.suffix not in ['.py','.json','.xml','.yaml','.yml','.toml']:continue
  try:t=f.read_text()
  except UnicodeError:continue
  new=t.replace(str(A),str(P))
  if new!=t:before=sha(f);f.write_text(new);rebased.append(dict(path=str(f.relative_to(P)),before=before,after=sha(f)))
put('audit/PATH_ONLY_REBASE.json',rebased)
for n in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','METHOD_DEFINITION.md','PARAMETER_MAP.json']:shutil.copy2(A/n,P/n)
shutil.copy2(A/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for n in ['INTERVENTION_PROTOCOL.md','RUN_PLAN.json']:shutil.copy2(LOCAL/n,P/n)
for f in (LOCAL/'control').glob('*.py'):shutil.copy2(f,P/'control'/f.name)
shutil.copy2(LOCAL/'control/terminal_repair.py',P/'code/terminal_repair.py')
shutil.copy2(A/'control/independent_recompute.py',P/'control/independent_recompute.py')
shutil.copy2(A/'control/own_campaign.py',P/'control/own_campaign.py')
plan=json.loads((P/'RUN_PLAN.json').read_text());plan.update(seed=2026101303,physics_budget=20,dispatch_cutoff_unix=plan['no_new_physics_after_unix'],physics_hard_stop_unix=plan['hard_stop_unix']-1200,physical_timeout_s=900,validation_conditions=[dict(name='N2',seed=2026101702,prefix={'OUTBOUND':[[-.06,-.06,-.06]]},role='exposed development'),dict(name='U1',seed=2026101801,prefix={'OUTBOUND':[[-.075,-.045,-.05]]},role='new unexecuted prefix validation')]);put('RUN_PLAN.json',plan)
text=(A/'control/campaign.py').read_text()
text=text.replace("from rich_planner import RichFreePlanner","from rich_planner import RichFreePlanner\nfrom terminal_repair import TerminalRepairPlanner")
text=text.replace("NEW=json.loads((P/'CANDIDATE.json').read_text());REPAIR=json.loads((P/'BOUNDED_REPAIR.json').read_text())","NEW=OLD;REPAIR=OLD")
start=text.index("    if GROUP=='N2' and arm=='C_repeat':")
end=text.index("    if GROUP=='reproduction':",start)
text=text[:start]+"    if arm=='T' and comp['acceptance_pass'] and comp['gain_percent']>=1.: arms.append('T_repeat')\n    if GROUP=='N2' and arm in ['B','E']:\n     gate=compare_raw(P/'source/results'/ident,P.parent/'m2_18d_autonomous_review_v1'/'source/results'/ident);put('audit/'+ident+'_ARCHIVE_GATE.json',gate);assert gate['status']=='PASS','N2_ARCHIVE_MISMATCH'\n"+text[end:]
text=text.replace("['B','E','C','C_repeat'] if GROUP=='N2' else ['B','E',read('DEVELOPMENT_SELECTION.json')['selected']]","['B','E','T']")
text=text.replace("['E','C','C_repeat','R','R_repeat']","['E','T','T_repeat']")
text=text.replace("['C','C_repeat']","['T','T_repeat']")
text=text.replace("for candidate in ['C','R']:","for candidate in ['T']:")
text=text.replace("   if not isinstance(planner,RichFreePlanner):planner.__class__=RichFreePlanner","   planner.__class__=TerminalRepairPlanner if self.arm in ['T','T_repeat'] else RichFreePlanner")
text=text.replace(" if GROUP!='reproduction':assert read('BASELINE_REPRODUCTION.json')['status']=='PASS','REPRODUCTION_REQUIRED'", " if GROUP=='U1':assert read('N2_T_GATE.json')['status']=='PASS','N2_GATE_REQUIRED'")
# Root identifiers contain no state and only redirect the isolated execution closure.
text=text.replace(str(A),str(P))
(P/'control/campaign.py').write_text(text)
put('audit/CAMPAIGN_ADAPTATION.json',dict(source=str(A/'control/campaign.py'),source_sha256=sha(A/'control/campaign.py'),new_sha256=sha(P/'control/campaign.py'),changes=['B/E/T serial same full-state fork','T repeats only after original qualification and >=1% gain','N2 B/E archival exact physical comparison','No C/R or parameter fallback','U1 requires N2 gate','20 starts and original clocks preserved']))
put('ENVIRONMENT.json',dict(python='/home/hank/envs/adaptive-online-rl-v1/bin/python',canonical=str(P),review=str(LOCAL),created_unix=time.time(),historical_source=str(A)))
print('CREATED',P,flush=True)
