from pathlib import Path
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
O=S/'adaptive_continuous_coordination_optimization_v1'
H=S/'ihear_overnight_research_retrospective_v1'
for root,patterns in [(O,['runtime_coordination_residual_v2.py','multisegment_reference.py']),(H,['native_scalar*py','native*18*py','quality*py'])]:
 for pattern in patterns:
  for f in root.rglob(pattern):
   if 'results' in f.parts:continue
   lines=f.read_text().splitlines();needles=['torque_components','allocated_wrench_world','position_wrench','velocity_wrench','def apply','def build_reference','def context','def native','free_parameters']
   idx=[i for i,l in enumerate(lines) if any(n in l for n in needles)]
   print('FILE',f)
   shown=set()
   for i in idx:
    for j in range(max(0,i-5),min(len(lines),i+24)):
     if j not in shown:print(f'{j+1}: {lines[j]}');shown.add(j)
for file in ['code/interfaces.py','code/native18.py','code/analyze_matched.py']:
 f=O/file
 if f.exists():
  print('FILE',f);s=f.read_text();print(s[:17000])
