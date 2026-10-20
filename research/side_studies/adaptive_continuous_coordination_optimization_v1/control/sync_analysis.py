from pathlib import Path
import shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
for name in ['postprocess.py','build_report.py','finalize.py','protection_audit.py','anomaly_mechanism.py','plot_anomaly.py','force_redistribution.py','enrich_diagnostics.py','visual_qa.py','sync_analysis.py','check_analysis_sources.py','progress_audit.py','preview_export.py']:
 shutil.copy2(L/'control'/name,P/'control'/name)
print('POSTPROCESSING_ONLY_SOURCES_SYNCED')
