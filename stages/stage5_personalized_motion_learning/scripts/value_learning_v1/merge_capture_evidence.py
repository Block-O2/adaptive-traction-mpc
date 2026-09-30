"""Merge separately executed conditional development-session evidence."""
import json
from research_campaign import D,save

def main():
 canonical=json.loads((D/'KNOWN_BENEFIT_CAPTURE.json').read_text())
 prior=json.loads((D/'KNOWN_BENEFIT_CAPTURE_PRIOR.json').read_text())
 if canonical['status']!='COMPLETE' or prior['status']!='COMPLETE':raise RuntimeError('both independent units must close before merge')
 indexed={(r['session'],r['repetition']):r for r in canonical['rows']}
 indexed.update({(r['session'],r['repetition']):r for r in prior['rows']})
 save(D/'KNOWN_BENEFIT_CAPTURE.json',{**canonical,'rows':[indexed[key] for key in sorted(indexed)],'separate_session_execution_merged_after_both_complete':True})

if __name__=='__main__':main()
