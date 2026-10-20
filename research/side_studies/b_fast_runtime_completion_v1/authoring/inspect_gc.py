from pathlib import Path
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
for root in (S/'code',S/'source/stages/stage5_personalized_motion_learning/src'):
 for p in root.rglob('*.py'):
  text=p.read_text()
  if 'gc.disable' in text or 'gc.collect' in text or 'gc.enable' in text:
   lines=text.splitlines()
   for i,l in enumerate(lines):
    if 'gc.disable' in l or 'gc.collect' in l or 'gc.enable' in l:print(p,i+1,'\n'.join(lines[max(0,i-4):i+5]))
