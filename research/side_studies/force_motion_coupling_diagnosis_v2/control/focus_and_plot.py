"""Read-only postprocessing of derived arrays; all outputs belong to new study."""
from analyze import *

def loadj(n): return json.loads((P/n).read_text())
def savefig(fig,name):
    fig.savefig(P/'figures'/(name+'.png'),dpi=160)
    fig.savefig(P/'figures'/(name+'.svg'))
    plt.close(fig)

def main():
    shutil.copy2(__file__,P/'control/focus_and_plot.py') if Path(__file__).resolve()!=P/'control/focus_and_plot.py' else None
    metrics=loadj('RAW_DERIVED_METRICS.json')['cases']; by={x['label']:x for x in metrics}
    ss={x['label']:dict(np.load(P/'series'/(x['label']+'.npz'))) for x in metrics}
    for label,s in ss.items():
        s['bounds']=by[label]['task_bounds_s'];s['events']=loadj('events/'+label+'.json')['events'];s['t0']=by[label]['absolute_task_start_s']
    B=ss['B0'];windows=loadj('derived/WINDOWS.json');lag=loadj('LAG_ANALYSIS.json')['cases']
    details={}
    edges=np.r_[np.arange(0,19.00001,.5),B['tf'][-1]]
    for label,s in ss.items():
        chunks=[]
        for lo,hi in zip(edges,edges[1:]):
            m=(s['t']>=lo-1e-8)&(s['t']<=hi+1e-8);bm=(B['t']>=lo-1e-8)&(B['t']<=hi+1e-8)
            jf=float(integral(s['tf'],s['f'],lo,hi));gain=float(integral(B['tf'],B['f'],lo,hi)-jf)
            chunks.append({'start_s':lo,'end_s':hi,'J_F_N_s':jf,'gain_vs_B_N_s':gain,'velocity_TV_delta_vs_B_rad_s':float(np.linalg.norm(np.diff(s['v'][m],axis=0),axis=1).sum()-np.linalg.norm(np.diff(B['v'][bm],axis=0),axis=1).sum()),'acceleration_variation_delta_vs_B_rad_s2':float(np.linalg.norm(np.diff(s['a'][m],axis=0),axis=1).sum()-np.linalg.norm(np.diff(B['a'][bm],axis=0),axis=1).sum())})
        assert abs(sum(x['J_F_N_s'] for x in chunks)-by[label]['J_F_N_s'])<1e-8
        df=s['f']-B['f'];dt=np.diff(s['tf'])
        overlap=[]
        for ph in ['OUTBOUND','RETURN']:
            rs=[x for x in windows[label]['0.05'] if x['phase']==ph];force=np.array([x['mean_force_N'] for x in rs])
            for feature in FEATURES[:3]:
                x=np.array([z[feature] for z in rs]);high=x>=np.quantile(x,.75);hf=force>=np.quantile(force,.75)
                overlap.append({'phase':ph,'feature':feature,'motion_top_quartile_time_fraction':float(high.mean()),'force_integral_share_in_motion_top_quartile':float(force[high].sum()/force.sum()),'high_force_window_fraction_overlapping_high_motion':float((high&hf).sum()/hf.sum()),'n_bins':len(rs)})
        details[label]={'half_second_windows':chunks,'highest_force_windows':sorted(chunks,key=lambda x:x['J_F_N_s'],reverse=True)[:8],'largest_gain_windows':sorted(chunks,key=lambda x:x['gain_vs_B_N_s'],reverse=True)[:8],'delta_force_positive_area_N_s':float(np.maximum(df[:-1],0)@dt),'delta_force_negative_area_N_s':float(np.minimum(df[:-1],0)@dt),'delta_force_abs_area_N_s':float(abs(df[:-1])@dt),'time_to_cumulative_fractions_s':{str(frac):float(np.interp(frac*s['cf'][-1],s['cf'],s['tf'])) for frac in [.25,.5,.75,.9]},'motion_force_overlap':overlap,'gain_4to6_N_s':float(integral(B['tf'],B['f'],4,6)-integral(s['tf'],s['f'],4,6)),'gain_15to16_N_s':float(integral(B['tf'],B['f'],15,16)-integral(s['tf'],s['f'],15,16))}
    A=ss['legacy005'];ix=int(np.argmax(abs(A['a'][:,0])));peak=float(A['t'][ix]);anomaly={'hip_acceleration_peak_task_s':peak,'hip_acceleration_peak_absolute_s':peak+A['t0'],'hip_acceleration_peak_deg_s2':float(np.degrees(A['a'][ix,0])),'B_hip_acceleration_same_time_deg_s2':float(np.degrees(B['a'][ix,0])),'windows':[]}
    for lo,hi in [(peak-.05,peak+.05),(5.8,6.0),(5.5,6.0),(5.,6.5),(0.,19.03)]:
        fi=(A['tf']>=lo-1e-8)&(A['tf']<=hi+1e-8);ni=(A['t']>=lo-1e-8)&(A['t']<=hi+1e-8);d=A['f']-B['f'];di=np.flatnonzero(fi)
        anomaly['windows'].append({'task_range_s':[lo,hi],'candidate_J_F_N_s':float(integral(A['tf'],A['f'],lo,hi)),'delta_J_F_vs_B_N_s':float(integral(A['tf'],d,lo,hi)),'positive_delta_area_N_s':float(integral(A['tf'],np.maximum(d,0),lo,hi)),'negative_delta_area_N_s':float(integral(A['tf'],np.minimum(d,0),lo,hi)),'candidate_force_range_N':[float(A['f'][fi].min()),float(A['f'][fi].max())],'B_force_range_N':[float(B['f'][fi].min()),float(B['f'][fi].max())],'max_abs_delta_force_N':float(abs(d[fi]).max()),'max_abs_delta_force_time_s':float(A['tf'][di[np.argmax(abs(d[fi]))]]),'candidate_jerk_combined_max_rad_s3':float(np.linalg.norm(A['j'][ni],axis=1).max())})
    ni=np.flatnonzero(abs(A['t']-peak)<.1);jf=np.linalg.norm(A['j'][ni],axis=1);anomaly['jerk_peak_nearby_task_s']=float(A['t'][ni[np.argmax(jf)]])
    fi=np.flatnonzero(abs(A['tf']-peak)<.1);anomaly['delta_force_peak_nearby_task_s']=float(A['tf'][fi[np.argmax(abs(A['f'][fi]-B['f'][fi]))]])
    anomaly['nearest_events']=sorted(A['events'],key=lambda e:abs(e['task_s']-peak))[:8]
    put('ANOMALY_TIME_ALIGNMENT.json',anomaly);put('FORCE_WINDOWS_AND_CONTRASTS.json',details)
    # Paired differences are task-matched contrasts, not independent sampling.
    contrasts={}
    for label in ['18D','legacy002','legacy005','D1_coupled_inverse','adaptive_D2','S_fixed_knots_late','PS_early']:
        contrasts[label]={}
        for width in [.05,.25,.5,1.]:
            for ph in ['OUTBOUND','RETURN']:
                rs=[x for x in windows[label][str(width)] if x['phase']==ph];bs=[x for x in windows['B0'][str(width)] if x['phase']==ph]
                df=np.array([x['mean_force_N']-b['mean_force_N'] for x,b in zip(rs,bs)])
                for feature in FEATURES[:3]:
                    dx=np.array([x[feature]-b[feature] for x,b in zip(rs,bs)])
                    contrasts[label][f'{width}|{ph}|{feature}']=lag_record(dx,df,width)
    put('PAIRED_DIFFERENCE_LAGS.json',contrasts)
    compact=[]
    for label in ['B0','18D','legacy005']:
        for ph in ['OUTBOUND','RETURN']:
            for feat in FEATURES[:3]:
                for trans in ['level','linear_detrend','first_difference']:
                    z=lag[label][f'0.05|SG0|{ph}|{feat}|{trans}'];compact.append({'case':label,'phase':ph,'feature':feat,'transform':trans,'zero_r':z.get('zero_lag_r'),'peak_r':z.get('peak_abs_r'),'peak_lag_s':z.get('peak_lag_s'),'null':z.get('circular_shift_maxlag_null')})
    put('LAG_SUMMARY.json',compact)
    with (P/'derived/CANDIDATE_SUMMARY.csv').open('w',newline='') as f:
        keys=['label','J_F_N_s','gain_vs_B_N_s','force_peak_N','force_RMS_N','velocity_TV_ratio_vs_B','acceleration_variation_ratio_vs_B','jerk_combined_RMS_ratio_vs_B','motion','task','receipt','safety']
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for x in metrics:w.writerow({**{k:x.get(k) for k in keys if k not in ['motion','task','receipt','safety']},**{k:x['qualification'].get(k) for k in ['motion','task','receipt','safety']}})
    plt.rcParams.update({'font.size':9,'axes.titlesize':11,'lines.linewidth':1.0,'svg.fonttype':'none'})
    colors={'B0':'#28354a','18D':'#007c91','legacy005':'#cb482d','legacy002':'#7651a8'}
    def phases(ax,s,lines=True):
        ax.axvspan(s['bounds'][1],s['bounds'][2],color='#d6dbdf',alpha=.35)
        for b in s['bounds'][1:3]:ax.axvline(b,color='0.4',lw=.6,ls='--')
        if lines:
            for e in s['events']:
                if e['kind']=='splice': ax.axvline(e['task_s'],color='#c69b28',alpha=.25,lw=.5)
        ax.grid(alpha=.18);ax.set_xlim(0,19.03)
    def absolute(ax,t0):
        sec=ax.secondary_xaxis('top',functions=(lambda x:x+t0,lambda x:x-t0));sec.set_xlabel('Absolute physics time [s]')
    for labels,name in [(['B0','18D','legacy005'],'01_core_common_timeline'),(['B0','legacy002','D1_coupled_inverse'],'02_legal_common_timeline')]:
        fig,axes=plt.subplots(9,3,figsize=(18,20),sharex=True,sharey='row',layout='constrained')
        fig.suptitle('Archived actual motion, issued reference, cuff force and events | no new physics',fontsize=15)
        for c,label in enumerate(labels):
            s=ss[label];color=colors.get(label,'#277b49')
            for k in [0,1]:
                axes[k,c].plot(s['t'][::4],np.degrees(s['q'][::4,k]),color=color,label='Actual native')
                axes[k,c].plot(s['tf'],np.degrees(s['refq'][:,k]),'--',color='0.2',alpha=.7,label='Issued reference 5 ms')
            axes[0,c].set_title(label+(' — motion FAIL' if label=='legacy005' else ''));absolute(axes[0,c],s['t0'])
            axes[2,c].plot(s['tf'],s['f'],color=color);axes[3,c].plot(s['tf'],s['cf'],color=color)
            for k in [0,1]:
                axes[4,c].plot(s['t'][::4],np.degrees(s['v'][::4,k]),color=['#007c91','#b34e79'][k],label=['hip','knee'][k])
                axes[4,c].plot(s['tf'],np.degrees(s['refv'][:,k]),'--',color=['#007c91','#b34e79'][k],alpha=.5)
            rs=windows[label]['0.05'];xx=np.array([(r['start_s']+r['end_s'])/2 for r in rs])
            axes[5,c].plot(xx,[r['velocity_TV_rate'] for r in rs],color=color)
            axes[6,c].plot(xx,[r['acceleration_variation_rate'] for r in rs],color=color)
            axes[7,c].plot(xx,[r['jerk_RMS'] for r in rs],color=color)
            for kind,yy,cc in [('request',3,'#4c70a3'),('activation',2,'#5e9b7b'),('splice',1,'#c58c26'),('planned_waypoint_end',0,'#8f6aa9'),('internal_knot',-1,'#b34e79'),('reference_terminal_marker',-2,'#6d7979')]:
                ee=[x['task_s'] for x in s['events'] if x['kind']==kind]
                axes[8,c].scatter(ee,np.full(len(ee),yy),s=18,marker='|',color=cc)
            axes[8,c].set_yticks([-2,-1,0,1,2,3],['terminal marker','internal knot','planned waypoint','splice','activation','request']);axes[8,c].set_ylim(-2.5,3.5);axes[8,c].set_xlabel('Task elapsed time [s]')
            for row,yl in enumerate(['Hip q [deg]','Knee q [deg]','Force [N]','Cumulative J_F [N s]','Actual/ref dq [deg/s]','Velocity TV / time [rad/s²]','Acceleration variation / time\n[rad/s³]','Native-derived jerk RMS\n50 ms bins [rad/s³]','Events']):
                phases(axes[row,c],s);axes[row,c].set_ylabel(yl if c==0 else '')
            axes[0,c].legend(loc='upper left',fontsize=7);axes[4,c].legend(fontsize=7,ncol=2)
        savefig(fig,name)
    fig,axes=plt.subplots(4,1,figsize=(12,11),sharex=True,layout='constrained')
    for label in ['B0','18D','legacy002','legacy005']:
        s=ss[label];axes[0].plot(s['tf'],s['f'],color=colors[label],label=label);axes[1].plot(s['tf'],s['cf'],color=colors[label]);axes[2].plot(s['tf'],B['cf']-s['cf'],color=colors[label])
    rr=details['18D']['half_second_windows'];axes[3].bar([x['start_s'] for x in rr],[x['gain_vs_B_N_s'] for x in rr],width=.48,align='edge',color='#007c91')
    for ax,yl in zip(axes,['Force [N]','Cumulative J_F [N s]','B − candidate cumulative [N s]','18D benefit per 0.5 s [N s]']):phases(ax,B);ax.set_ylabel(yl)
    axes[0].legend(ncol=4);absolute(axes[0],B['t0']);axes[-1].set_xlabel('Task elapsed time [s]');savefig(fig,'03_force_and_18D_local_benefit')
    # Close view: no interpolation of force or implied native-rate cuff force.
    fig,axes=plt.subplots(6,1,figsize=(12,13),sharex=True,layout='constrained')
    for label in ['B0','legacy005','legacy005_repeat','legacy002']:
        s=ss[label];color=colors.get(label,'#dd9f1b');style='--' if label.endswith('repeat') else '-'
        axes[0].plot(s['tf'],s['f'],style,color=color,label=label)
        axes[1].plot(s['tf'],s['f']-B['f'],style,color=color)
        axes[2].plot(s['tf'],s['cf']-B['cf'],style,color=color)
        axes[3].plot(s['t'],np.degrees(s['a'][:,0]),style,color=color)
        axes[4].plot(s['t'],np.linalg.norm(s['j'],axis=1),style,color=color)
        axes[5].plot(s['tf'],np.linalg.norm(s['torque']-B['torque'],axis=1),style,color=color)
    for ax,yl in zip(axes,['Force [N]','Force − B [N]','Cumulative J_F − B [N s]','Hip raw acceleration [deg/s²]','Combined raw jerk [rad/s³]','Torque difference norm [Nm]']):
        ax.set_xlim(5.65,6.05);ax.axvline(peak,ls=':',color='0.3');ax.grid(alpha=.2);ax.set_ylabel(yl)
    axes[0].legend(ncol=4);axes[0].set_title('Repeated +0.05° motion FAIL: local force redistribution, not a large force peak');absolute(axes[0],A['t0']);axes[-1].set_xlabel('Task elapsed time [s]');savefig(fig,'04_anomaly_force_motion_torque')
    fig,axes=plt.subplots(3,2,figsize=(13,10),sharex=True,sharey=True,layout='constrained')
    for row,feature in enumerate(FEATURES[:3]):
        for col,ph in enumerate(['OUTBOUND','RETURN']):
            ax=axes[row,col]
            for label in ['B0','18D','legacy005']:
                z=lag[label][f'0.05|SG0|{ph}|{feature}|first_difference'];ax.plot(z['lag_s'],z['pearson'],color=colors[label],label=label)
            ax.axhline(0,color='0.6',lw=.7);ax.axvline(0,color='0.5',ls=':');ax.grid(alpha=.2);ax.set_ylim(-1,1);ax.set_title(ph+' | Δ'+feature+' vs Δforce');ax.set_ylabel('Within-phase Pearson r');ax.set_xlabel('Lag [s], positive = motion leads force')
    axes[0,0].legend(ncol=3);fig.suptitle('Lagged correlations after first differences | 50 ms bins, raw native derivatives');savefig(fig,'05_phase_lag_first_difference')
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for col,ph in enumerate(['OUTBOUND','RETURN']):
        for label in ['B0','18D']:
            for row,trans in enumerate(['level','linear_detrend']):
                z=lag[label][f'0.05|SG0|{ph}|acceleration_variation_rate|{trans}'];axes[row,col].plot(z['lag_s'],z['pearson'],color=colors[label],label=label)
        for row,trans in enumerate(['level','linear_detrend']):
            ax=axes[row,col];ax.axhline(0,color='.6');ax.axvline(0,color='.6',ls=':');ax.grid(alpha=.2);ax.set_ylim(-1,1);ax.set_title(ph+' | '+trans);ax.set_xlabel('Lag [s], positive = motion leads force');ax.set_ylabel('r(acceleration variation, force)')
    axes[0,0].legend();savefig(fig,'06_trend_sensitivity')
    fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    for ax,metric in zip(axes,['velocity_TV_ratio_vs_B','acceleration_variation_ratio_vs_B','jerk_combined_RMS_ratio_vs_B']):
        for x in metrics:
            if x['label']=='18D':continue
            good=x['qualification']['motion'] is True;ax.scatter(x[metric],x['gain_vs_B_N_s'],marker='o' if good else 'x',color='#007c91' if good else '#cb482d',s=35)
            if x['label'] in ['legacy005','adaptive_D2'] or (x['label']=='D1_coupled_inverse' and metric=='velocity_TV_ratio_vs_B'):
                ax.annotate(x['label'],(x[metric],x['gain_vs_B_N_s']),fontsize=7,xytext=(4,6),textcoords='offset points')
        ax.axhline(0,color='.5');ax.axvline(1,color='.5');ax.set_xlabel(metric);ax.set_ylabel('B − candidate J_F [N s]');ax.grid(alpha=.2)
    fig.suptitle('Historical small perturbations: tiny force differences and mixed motion response | all negatives retained');savefig(fig,'07_historical_force_motion_tradeoff')
    print('B_TOP_WINDOWS',clean(details['B0']['highest_force_windows'][:4]),flush=True)
    print('18D_TOP_GAIN',clean(details['18D']['largest_gain_windows'][:6]),flush=True)
    print('ANOMALY',clean(anomaly),flush=True)
    print('LAG_SUMMARY_SAVED',len(compact),'rows',flush=True)
    print('FIGURES_COMPLETE',flush=True)

if __name__=='__main__':main()
