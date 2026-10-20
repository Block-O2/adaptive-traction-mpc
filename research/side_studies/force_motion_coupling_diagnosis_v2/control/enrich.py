from analyze import *

def main():
    if Path(__file__).resolve()!=P/'control/enrich.py':shutil.copy2(__file__,P/'control/enrich.py')
    manifest=json.loads((P/'SOURCE_MANIFEST.json').read_text());SOURCE_FILES.update(manifest['files'])
    records=json.loads((P/'RAW_DERIVED_METRICS.json').read_text())['cases'];ww=json.loads((P/'derived/WINDOWS.json').read_text());params=[];event_audit=[];rise={}
    for rec in records:
        root=Path(rec['source_root']);ident=rec['archive_case'];label=rec['label'];run=root/'source/results'/ident
        config=read(run/'config_snapshot.json');su=read(run/'summary.json');measured=read(root/'reports'/(ident+'_MEASURED.json'))
        put('provenance/'+label+'_CONFIG.json',config);put('provenance/'+label+'_ARCHIVED_MEASURED.json',measured)
        params.append({'label':label,'archive_id':ident,'parameters':rec['qualification'].get('parameters'),'qualification':rec['qualification'],'new_physics':False})
        # Correct planned waypoint clock uses actual suffix splice where
        # recorded, otherwise actual activation. Arrival markers remain distinct.
        ev=json.loads((P/'events'/(label+'.json')).read_text())['events'];ev=[e for e in ev if e['kind']!='planned_waypoint_end'];splices={e['request_id']:e for e in ev if e['kind']=='splice'}
        for lr in su['learning_records']:
            ix=lr['decision_index'];d=su['decisions'][ix];assert abs(lr['request_time_s']-d['decision_request_time_s'])<1e-9
            if not lr['selected_plan_activated']:continue
            sc=lr['selected_plan']['schedule'];rid=d['timing_request_id'];origin=splices[rid]['absolute_s'] if rid in splices else d['actual_schedule_start_physics_s'];end=origin+sc['duration_s']
            ev.append({'kind':'planned_waypoint_end','task_s':end-rec['absolute_task_start_s'],'absolute_s':end,'request_id':rid,'target_q_rad':sc.get('target_q_rad'),'origin':'recorded suffix splice' if rid in splices else 'activation','qualification':'planned reference endpoint; not proof of Human arrival, may be superseded'})
            if 'knots_s' in sc:
                for knot in sc['knots_s'][1:-1]:ev.append({'kind':'internal_knot','task_s':origin+knot-rec['absolute_task_start_s'],'absolute_s':origin+knot,'request_id':rid,'qualification':'planned C2 reference knot, not actual Human crossing'})
        tr=np.load(run/'trace.npz');mask=tr['stage']=='TASK';tt=tr['time_s'][mask];flags=tr['terminal_boundary_node'][mask];onsets=np.flatnonzero(flags & ~np.r_[False,flags[:-1]])
        for ix in onsets:ev.append({'kind':'reference_terminal_marker','task_s':tt[ix]-rec['absolute_task_start_s'],'absolute_s':tt[ix],'qualification':'stored controller terminal_boundary_node rising edge; not an independent Human waypoint arrival test'})
        put('events/'+label+'.json',{'events':ev,'phase_bounds_task_s':rec['task_bounds_s'],'planned_vs_actual_distinguished':True})
        event_audit.append({'case':label,'counts':{kind:sum(x['kind']==kind for x in ev) for kind in sorted({x['kind'] for x in ev})},'learning_request_alignment':'PASS'})
        if label in CORE:
            rise[label]={}
            for width in [.05,.1,.25,.5]:
                for ph in ['OUTBOUND','RETURN']:
                    rs=[r for r in ww[label][str(width)] if r['phase']==ph];f=np.array([r['mean_force_N'] for r in rs]);slope=np.diff(f)/width
                    for feature in FEATURES[:3]:
                        x=np.array([r[feature] for r in rs])[1:]
                        rise[label][f'{width}|{ph}|{feature}']=lag_record(x,slope,width)
    frozen=read(HIST/'FROZEN_SELECTION.json');params[1]['parameters']=frozen['best']['candidate'];put('provenance/18D_FROZEN_SELECTION.json',frozen)
    for root,name in [(HIST,'MOTION_ACCEPTANCE_PROTOCOL.json'),(HIST,'VALIDATION_RESULTS.json'),(OLD,'PARENT_FORK_GATE.json'),(OLD,'SELECTED_REPEAT_GATE.json')]:
        f=source(root/name);shutil.copy2(f,P/'provenance'/(root.name+'__'+name))
    put('CANDIDATE_PARAMETERS_AND_QUALIFICATION.json',params);put('audit/EVENT_ALIGNMENT.json',event_audit);put('FORCE_RISE_LAGS.json',{'definition':'lagged corr(motion feature[t], backward first difference of mean force[t+lag]); positive lag motion leads; phase-local bins; slope units N/s; no cumulative J used','cases':rise})
    # Native-derived arrays/force and repeated trace fields independently equal.
    a=np.load(P/'series/legacy005.npz');b=np.load(P/'series/legacy005_repeat.npz')
    repeat={key:bool(np.array_equal(a[key],b[key],equal_nan=True)) for key in a.files};assert all(repeat.values())
    put('audit/DERIVED_ANOMALY_REPEAT_IDENTITY.json',{'status':'PASS','fields':repeat,'scope':'all saved task native q/dq/a/j and 5ms force/cumulative/reference/command arrays; archived full-native repeat audit retained separately','new_physical_repeat':False})
    put('SOURCE_MANIFEST.json',{'files':SOURCE_FILES,'raw_policy':manifest['raw_policy']})
    print('ENRICHED',len(params),'cases',flush=True)

if __name__=='__main__':main()
