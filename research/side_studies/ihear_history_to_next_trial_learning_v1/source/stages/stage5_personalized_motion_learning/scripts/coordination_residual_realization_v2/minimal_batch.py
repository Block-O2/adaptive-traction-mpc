from gates import *
if __name__=='__main__':
 assert read(os.environ.get('ZERO_GATE','zero_logging_v2_GATE.json'))['pass_']
 rows=[]
 for kind in read('CONTRACT.json')['minimal']:
  for amp in read('CONTRACT.json')['amplitudes']:
   name=kind+'_'+str(amp)+'_'+os.environ.get('GATE_REV','logged')
   if (L/(name+'_AUDIT.json')).exists():row=read(name+'_AUDIT.json')
   elif (L/(name+'.json')).exists():row=audit(name,read(name+'.json'))
   else:
    action=pattern(kind,amp);save(name+'_ACTION.json',action);row=audit(name,run(name,Interface(action)))
   print(json.dumps(dict(name=name,pass_=row['pass_'],valid=row['metric']['valid'],accepted=row['accepted'],activated=row['activated'])),flush=True)
   rows.append(dict(name=name,**row));save('MINIMAL_PROGRESS.json',rows)
   if row['pass_']:break
  else:
   save('MINIMAL_GATE.json',dict(pass_=False,blocked=kind,rows=rows));raise RuntimeError('MINIMAL_GATE_BLOCKED:'+kind)
 save('MINIMAL_GATE.json',dict(pass_=True,rows=rows))
