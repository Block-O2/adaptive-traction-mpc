from pathlib import Path
import shutil,sys,subprocess,json
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_work');S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime/source/stages/stage5_personalized_motion_learning');P=S/'scripts/single_human_sac_expert_v1';D=S/'docs/single_human_sac_expert_v1'
for name in ('sac_env.py','qualify.py','qualification_batch.py','final_qualification.py','throughput.py','test_adapter.py','prepare_final_qualification.py','run_final_qualification.py'):shutil.copy2(W/name,P/name)
subprocess.run([sys.executable,str(P/'prepare_final_qualification.py')],check=True)
test=subprocess.run([sys.executable,str(P/'test_adapter.py')],capture_output=True,text=True)
(D/'ADAPTER_TESTS.txt').write_text(test.stdout+'\n'+test.stderr)
assert test.returncode==0
subprocess.run([sys.executable,'-u',str(P/'final_qualification.py')],check=True)
if json.loads((D/'STATE.json').read_text())['phase']=='FINAL_ENVIRONMENT_GATES_PASS':subprocess.run([sys.executable,'-u',str(P/'throughput.py')],check=True)
