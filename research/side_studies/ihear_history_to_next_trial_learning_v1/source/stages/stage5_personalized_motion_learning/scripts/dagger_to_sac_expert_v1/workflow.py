from common import *
def run():
    try:
        assert read('EXPERT_GATE.json')['status']=='PASS'
        from mechanical_checks import run as tests
        tests()
        from dagger import run as dagger
        if dagger():
            from sac import run as sac
            sac()
    except BaseException as e:
        save('EXCEPTION.json',dict(error=str(e),traceback=traceback.format_exc()))
        label='HARD_WALL_CAP_SAVED' if 'HARD_WALL_CAP' in str(e) else 'NAN_RESOURCE_EVIDENCE_CORRUPTION' if 'RESOURCE' in str(e) or 'NAN' in str(e) else 'IMPLEMENTATION_EXCEPTION_SAVED'
        state(label,next_action='Inspect saved exception; repair only implementation defects before any continuation.',error=str(e))
        raise
    finally:
        from finish import run as finish
        finish()
if __name__=='__main__':run()
