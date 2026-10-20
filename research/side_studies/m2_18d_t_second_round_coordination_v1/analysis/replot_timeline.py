from pathlib import Path
import os,json,ast
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg',MPLCONFIGDIR=str(P/'tmp/mpl'))
import numpy as np
import matplotlib.pyplot as plt
A=P.parent/'m2_18d_terminal_expanded_prefix_validation_v1'
source=(P/'control/diagnose_prepare.py').read_text();tree=ast.parse(source);ns=dict(P=P,A=A,np=np,json=json,plt=plt)
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['put','load','metrics']];exec(compile(ast.Module(body=nodes,type_ignores=[]),'historical_raw_plot_functions','exec'),ns)
block=source[source.index('Z={'):source.index('identities={')]
block=block.replace('[::12,j]','[:,j]').replace('[::12]','').replace('[::8]','')
exec(compile(block,'full_native_timeline','exec'),ns)
print('FULL_NATIVE_TIMELINE_SAVED',flush=True)
