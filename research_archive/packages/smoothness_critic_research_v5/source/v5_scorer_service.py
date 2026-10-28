from pathlib import Path
import os,sys
P=Path(__file__).resolve().parents[1]
os.environ.update(ACL2_PACKAGE=str(P),PYTHONDONTWRITEBYTECODE="1",OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1")
sys.dont_write_bytecode=True
sys.path[:0]=[str(P/"source"),str(P/"legacy_source")]
import acl2_scorer_replay
acl2_scorer_replay.main()
