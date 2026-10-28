from common import ROOT
import os
def install():
 os.environ.update(IHEAR_THREAD_PLANNER='1',IHEAR_EXTERNAL_NATIVE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
 from native_journal import install as journal
 from source_lookup_optimization import install as lookup
 from model_binary_cache import install as binary
 from model_path_cache import install as path
 journal();lookup();binary();path()
