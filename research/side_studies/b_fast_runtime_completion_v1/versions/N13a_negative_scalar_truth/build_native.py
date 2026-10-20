from pathlib import Path
import os,sys,json,time,subprocess,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy,mujoco
from setuptools import setup,Extension
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
for n in ('fast_native.cpp','build_native.py'):shutil.copy2(W/n,S/'native'/n)
root=Path(mujoco.__file__).parent
os.chdir(S/'native')
sys.argv=[str(S/'native/build_native.py'),'build_ext','--build-lib',str(S/'build'),'--build-temp',str(S/'build/temp')]
setup(name='fast-native-research-v1',version='1.0',ext_modules=[Extension('fast_native',[str(S/'native/fast_native.cpp')],include_dirs=[numpy.get_include(),str(root/'include')],extra_objects=[str(root/'libmujoco.so.3.10.0')],runtime_library_dirs=[str(root)],language='c++',extra_compile_args=['-O3','-fno-fast-math','-ffp-contract=off'])])
