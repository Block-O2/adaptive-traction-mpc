"""Manual-only cloud smoke coordinator: qualification -> 1 update -> resume -> eval."""
from common import ROOT,put
import argparse,subprocess,sys,json
def main():
 p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');a=p.parse_args()
 if not a.enable:raise RuntimeError('DISABLED_REQUIRE_EXPLICIT_ENABLE')
 commands=[['qualify.py','--enable'],['train.py','--enable','--profile','smoke','--decisions','16','--seed','20261021','--out','runs/smoke_train_01'],['audit_checkpoint.py','--checkpoint','runs/smoke_train_01/checkpoints/final','--out','runs/smoke_train_01/CHECKPOINT_AUDIT.json'],['train.py','--enable','--profile','smoke','--decisions','16','--seed','20261021','--resume','runs/smoke_train_01/checkpoints/final','--out','runs/smoke_resume_01'],['evaluate.py','--enable','--checkpoint','runs/smoke_train_01/checkpoints/initial','--out','runs/eval_initial_01'],['evaluate.py','--enable','--checkpoint','runs/smoke_resume_01/checkpoints/final','--out','runs/eval_final_01']]
 results=[]
 for command in commands:
  proc=subprocess.run([sys.executable,*command],cwd=ROOT);results.append({'argv':command,'returncode':proc.returncode});put(ROOT/'runs/SMOKE_SEQUENCE.json',{'commands':results,'learning_success_claim':False})
  if proc.returncode:raise RuntimeError('SMOKE_STOP:'+str(command))
 before=json.loads((ROOT/'runs/smoke_train_01/checkpoints/final.json').read_text());after=json.loads((ROOT/'runs/smoke_resume_01/checkpoints/final.json').read_text());audit=json.loads((ROOT/'runs/smoke_train_01/CHECKPOINT_AUDIT.json').read_text())
 initial=json.loads((ROOT/'runs/smoke_train_01/checkpoints/initial.json').read_text())
 checks={'first_update_exists':before['updates']>0,'first_policy_changed':before['policy_sha256']!=initial['policy_sha256'],'resume_more_updates':after['updates']>before['updates'],'resume_more_decisions':after['decisions']>before['decisions'],'resumed_policy_changed':after['policy_sha256']!=before['policy_sha256'],'trained_restore_exact':audit['pass']}
 put(ROOT/'runs/PPO_SMOKE_RESULTS.json',{'category':'MECHANICAL_PPO_UPDATE_AND_RESUME_SMOKE','pass':all(checks.values()),'checks':checks,'commands':results,'learning_success_claim':False})
 if not all(checks.values()):raise RuntimeError('SMOKE_ASSERTIONS_FAILED')
if __name__=='__main__':main()
