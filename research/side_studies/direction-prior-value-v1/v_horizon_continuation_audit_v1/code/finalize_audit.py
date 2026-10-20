from audit_common import *
import importlib
def main():
 for name in ('sync_audit','analyze_attribution','audit_compute','closeout_verify','write_report','plot_audit','finish_state','deliver'):
  importlib.import_module(name).main()
 print('FINALIZATION_COMPLETE_STOPPED')
if __name__=='__main__':main()
