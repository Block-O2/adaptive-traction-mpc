from pathlib import Path
import os,sys,json
P=Path(__file__).resolve().parents[1];R=P/'runtime';sys.dont_write_bytecode=True;os.environ['STUDY_GROUP']='P1';sys.path[:0]=[str(R/'control'),str(R/'code')]
import base_campaign as bc
old=Path('/home/hank/ihear-lab/autonomous_learning_smoothness_v7/runtime/source/results/MOTION_CAUSE_STRONG');gate=bc.compare_raw(R/'source/results/P1_OLD_STRONG',old);gate['scope']='Full18D action adapter at inherited strong vector exactly reproduces previous legacy2 strong through every archived trace field, native Human/robot/contact/applied torque and receipt ownership/reference/source fields.';(P/'audit/FULL18D_ADAPTER_RAW_GATE.json').write_text(json.dumps(gate,indent=2)+'\n');print(gate['status'],gate['errors'],gate['counts'])
