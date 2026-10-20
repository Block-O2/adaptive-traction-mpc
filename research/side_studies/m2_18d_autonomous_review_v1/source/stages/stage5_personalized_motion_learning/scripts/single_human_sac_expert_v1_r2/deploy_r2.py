from pathlib import Path
import shutil,ast,json
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1/source');S=R/'stages/stage5_personalized_motion_learning';P1=S/'scripts/single_human_sac_expert_v1';P=S/'scripts/single_human_sac_expert_v1_r2';W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_r2')
for name in ('campaign_r2.py','preflight_r2.py','diagnose_r2.py','hold_details_r2.py','hold_compact_r2.py','probe_hold_r2.py','deploy_r2.py'):shutil.copy2(W/name,P/name)
src=(P1/'train_campaign.py').read_text()
start=src.index('def lock_and_budget():');end=src.index('def evaluate(',start)
src=src[:start]+'from campaign_r2 import lock_and_budget_r2 as lock_and_budget, resource_check\n\n'+src[end:]
src=src.replace("datetime.datetime.fromisoformat('2026-10-03T03:50:00+00:00').timestamp()","json.loads((D/'SAC_TRAINING_CONFIG.json').read_text())['hard_wall_cutoff_unix']-5*60")
src=src.replace('self.episodes=0','self.episodes=0;self.last_resource_probe=time.monotonic()')
needle="        info=self.locals['infos'][0];step=self.model.num_timesteps\n"
assert needle in src
src=src.replace(needle,needle+"        if time.monotonic()-self.last_resource_probe>=60.:\n            self.last_resource_probe=time.monotonic()\n            if not resource_check('formal_periodic_resource_guard'):\n                self.stop_reason='RESOURCE_RISK';return False\n")
ast.parse(src);(P/'train_campaign_r2.py').write_text(src)
print(json.dumps(dict(path=str(P),formal_source_lines=len(src.splitlines()),R1_training_source_unchanged=True)))
