from pathlib import Path
import shutil
L=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');P=S/L.name;A=S/'m2_18d_terminal_response_repair_v1'
text=(L.parent/'m2_18d_terminal_response_repair_v1/control/build_results.py').read_text();text=text[:text.index('# Controlled local view')]
text=text.replace("import matplotlib.pyplot as plt",'').replace("(L/n).write_text","(P/n).write_text").replace("limit=20","limit=30").replace("['N2','U1']","['V1','V2']")
text += "\nprint('ASSEMBLED',len(groups),'groups',len(starts),'START',flush=True)\n"
(P/'analysis/build_results.py').write_text(text)
shutil.copy2(L.parent/'m2_18d_terminal_response_repair_v1/control/intervention_audit.py',P/'analysis/intervention_audit.py')
text=(L/'control/audit_contract.py').read_text().replace("A=S/'m2_18d_terminal_response_repair_v1'","A=P").replace("['N2','U1']","['V1','V2']").replace("_HISTORICAL_TIME_EVIDENCE.json","_NEW_TIME_EVIDENCE.json").replace("audit/T_EXECUTION_CONTRACT_AUDIT.json","audit/EXPANDED_EXECUTION_TIME_AUDIT.json").replace("historical_rows=rows","new_rows=rows").replace("physical_started=False","physical_started=True").replace("PHYSICAL_LEVEL1 historical raw reconstruction only","PHYSICAL_LEVEL1 new frozen validation raw reconstruction only")
(P/'analysis/new_time_audit.py').write_text(text)
print('ANALYSIS_PREPARED',flush=True)
