from audit_common import *
def main():
 final=read(STUDY/'FINAL_STATUS.json');assert final['status']=='COMPLETE' and (STUDY/'STOP_DISPATCH').exists()
 final.update(unix=time.time(),phase='COMPLETE_STOPPED',next_action='STOP; no new dispatch or training',start_unix=START,deadline_unix=START+6*3600);save(STUDY/'STATE.json',final)
 (STUDY/'PROGRESS.md').write_text(f'COMPLETE / STOPPED\n\nOriginal start {START}; elapsed {(time.time()-START)/3600:.3f} h / 6 h hard cap.\nNew physics attempts {final["attempts"]}/50 including failures and replay parents.\nTraining 0; all required diagnostics completed, owner joined.\nV status {final["V_STATUS"]}.\nFinal report REPORT.md.\n',encoding='utf-8')
 print('STATE_COMPLETE_STOPPED')
if __name__=='__main__':main()
