"""Descriptive differences on the explicitly eligible complete equal-duration pairs."""
from pathlib import Path
import json
from research_common import ROOT,read,atomic,now

def main():
 r=read(ROOT/'STD_ABLATION_RESULTS.json');assert r['status']=='COMPLETE';rows=[]
 keys=['tracking_RMS_deg','velocity_RMS_deg_s','velocity_peak_deg_s','acceleration_RMS_deg_s2','acceleration_peak_deg_s2','jerk_RMS_deg_s3','jerk_peak_deg_s3','terminal_return_absolute_error_deg','RETURN_overshoot_below_goal_deg']
 for p in r['pairs']:
  if not p['complete_equal_duration']:continue
  a=next(x for x in r['cases'] if x['seed']==p['seed'] and x['rng']==p['rng'] and x['arm']=='A');b=next(x for x in r['cases'] if x['seed']==p['seed'] and x['rng']==p['rng'] and x['arm']=='B')
  rows.append(dict(seed=p['seed'],rng=p['rng'],JF_difference_B_minus_A=p['JF_difference_B_minus_A'],JM_difference_B_minus_A=p['JM_difference_B_minus_A'],motion_difference_B_minus_A={k:[y-x for x,y in zip(a['motion'][k],b['motion'][k])] for k in keys}))
 atomic(ROOT/'audit/PAIRED_COMPLETE_MOTION_TRADEOFFS.json',dict(time_utc=now(),pairs=rows,scope='Only complete equal-duration realized pair subset; descriptive post-run tradeoffs, no success-conditioned population superiority'))
 print('eligible complete equal-duration motion pairs',len(rows))
if __name__=='__main__':main()
