from pathlib import Path
import json,hashlib,shutil,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1');R=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_review');C=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_control')
verification=json.loads((S/'PACKAGE_VERIFICATION.json').read_text());protocol=json.loads((S/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json').read_text());elapsed=(time.time()-protocol['t0_unix'])/60
assert elapsed<240
verification.setdefault('numeric_verification_elapsed_minutes',verification['elapsed_minutes']);verification['final_closeout_elapsed_minutes']=elapsed;verification['final_closeout_unix']=time.time();verification['artifact_only_closeout_after_numeric_verification']=True
(S/'PACKAGE_VERIFICATION.json').write_text(json.dumps(verification,indent=2,ensure_ascii=False)+'\n');shutil.copy2(S/'PACKAGE_VERIFICATION.json',R/'PACKAGE_VERIFICATION.json')
qa=json.loads((S/'VISUAL_QA.json').read_text());qa.update(final_labels_visually_inspected=True,method='All three plots visually inspected; final third-plot labels and external legend checked; raw verified data, no acceptance smoothing');(S/'VISUAL_QA.json').write_text(json.dumps(qa,indent=2)+'\n');shutil.copy2(S/'VISUAL_QA.json',R/'VISUAL_QA.json')
report=(S/'REPORT.md').read_text();report+='\n图表标签和收尾完成后，总墙钟约%.2f分钟，仍在4小时硬限内；该阶段仅更新报告/图表/清单，没有新增物理任务。STOP。\n'%elapsed;(S/'REPORT.md').write_text(report);shutil.copy2(S/'REPORT.md',R/'REPORT.md')
shutil.copytree(S/'figures',R/'figures',dirs_exist_ok=True)
for p in C.glob('*.py'):shutil.copy2(p,S/'control'/p.name)
manifest={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in S.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='PACKAGE_MANIFEST.json'}
(S/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copy2(S/'PACKAGE_MANIFEST.json',R/'PACKAGE_MANIFEST.json')
print('ONLY_ARTIFACT_LABELS_AND_MANIFEST_REFRESHED_NO_PHYSICS')
