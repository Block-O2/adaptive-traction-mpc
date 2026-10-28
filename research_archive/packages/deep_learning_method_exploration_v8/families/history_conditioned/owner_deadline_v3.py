"""Absolute inherited owner budget; no wall-clock reset at child/hook return."""
import signal,time


def make_owner_deadline(budget_s,*,inherited_deadline=None,now_monotonic=None):
    now=time.monotonic() if now_monotonic is None else float(now_monotonic)
    deadline=now+float(budget_s)
    return deadline if inherited_deadline is None else min(deadline,float(inherited_deadline))


def arm_owner_deadline(deadline,maximum_s,*,campaign_stop_unix,now_monotonic=None,now_unix=None,timer_writer=None):
    now=time.monotonic() if now_monotonic is None else float(now_monotonic)
    wall=time.time() if now_unix is None else float(now_unix)
    remaining=min(float(deadline)-now,float(maximum_s),float(campaign_stop_unix)-wall)
    if remaining<=0.:raise TimeoutError('ORIGINAL_OWNER_OR_CAMPAIGN_DEADLINE_EXPIRED')
    if timer_writer is None:signal.setitimer(signal.ITIMER_REAL,remaining)
    else:timer_writer(remaining)
    return remaining
