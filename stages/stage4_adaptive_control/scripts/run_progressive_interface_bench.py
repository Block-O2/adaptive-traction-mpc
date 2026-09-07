#!/usr/bin/env python3
"""Load-deflection registration and 36 bounded standalone MuJoCo ringdowns."""
import argparse
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback

REPO=Path(__file__).resolve().parents[3]
STAGE=REPO/'stages/stage4_adaptive_control'
sys.path.insert(0,str(REPO/'stages/stage3_full3d/src'))
import numpy as np
import mujoco
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation
from traction_mpc_stage3.progressive_interface import ProgressiveParameters,evaluate_progressive,radial_load,tangent_stiffness
from traction_mpc_stage3.spring_damper_interface import AttachmentState

SPEC=STAGE/'docs/PROGRESSIVE_INTERFACE_BENCH_SPEC.json'
DOC=SPEC.with_suffix('.md')
ROOT=STAGE/'results/engineering_validation/progressive_interface_bench_20260904_v1'
EXPECTED_JSON_SHA='aedebae72fa4c2137a5e73e46f3d03616d3dd821cb9057e80ac242f27fe9643e'
NEW_FILES=[Path(__file__),STAGE/'tests/test_progressive_interface.py',
 REPO/'stages/stage3_full3d/src/traction_mpc_stage3/progressive_interface.py']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def write(p,x):p.write_text(json.dumps(clean(x),indent=2,sort_keys=True,allow_nan=False)+'\n')
def root_deflection(load,k1,k3):
    if load==0:return 0.
    return float(brentq(lambda a:k1*a+k3*a**3-load,0.,max(load/k1,1e-9),xtol=1e-15))
def norm(y):return np.abs(y) if np.asarray(y).ndim==1 else np.linalg.norm(y,axis=1)
def cumtrap(y,t):return np.r_[0.,np.cumsum(.5*(y[1:]+y[:-1])*np.diff(t))]
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}

def spec():
    assert sha(SPEC)==EXPECTED_JSON_SHA,'registration_changed'
    s=json.loads(SPEC.read_text())
    for field in ('original_frozen_sha256','old_evidence_sha256'):
        for p,h in s[field].items():assert sha(REPO/p)==h,p
    old=json.loads((REPO/'stages/stage4_adaptive_control/results/engineering_validation/phase3a_soft_1ms_qualification_20260904_v1/implementation_registration.json').read_text())
    for p,h in old['hashes'].items():assert sha(REPO/p)==h,p
    return s


def static_bench(s):
    rows=[]; curves=[]; qualified={}
    for c in s['candidates']:
        p=ProgressiveParameters(**c['parameters']); checks=[]
        for kind,loads,k1,k3 in [('force',s['static_loads_n']+[s['extra_static_extreme_load_n']],p.k1_n_m,p.k3_n_m3),
                                 ('moment',s['static_moments_nm'],p.kr1_nm_rad,p.kr3_nm_rad3)]:
            for value in loads:
                r=root_deflection(value,k1,k3); residual=abs(k1*r+k3*r**3-value)
                rows.append(dict(candidate=c['id'],kind=kind,load=value,deflection_si=r,
                    deflection_display=r*1000 if kind=='force' else np.degrees(r),
                    display_unit='mm' if kind=='force' else 'deg',radial_tangent=k1+3*k3*r*r,
                    tangential_tangent=k1+k3*r*r,load_residual=residual))
                for direction in [np.array([1.,0,0]),np.array([0.,1,0]),np.array([0.,0,1]),np.array([1.,2,3])/np.sqrt(14)]:
                    v=r*direction;f=radial_load(v,k1,k3)
                    err=np.linalg.norm(f-value*direction)/max(value,1.)
                    checks.append(residual<=s['numerical_tolerances']['static_root_residual_abs'] and err<=s['numerical_tolerances']['cross_axis_alignment_relative'] and np.min(np.linalg.eigvalsh(tangent_stiffness(v,k1,k3)))>0)
            grid=s['static_curve_grid']['force_n' if kind=='force' else 'moment_nm']
            for value in np.linspace(*grid):
                r=root_deflection(value,k1,k3)
                curves.append(dict(candidate=c['id'],kind=kind,load=value,deflection_si=r,radial_tangent=k1+3*k3*r*r))
        targets=s['static_targets']
        d100=root_deflection(100,p.k1_n_m,p.k3_n_m3);d200=root_deflection(200,p.k1_n_m,p.k3_n_m3);d300=root_deflection(300,p.k1_n_m,p.k3_n_m3);r50=root_deflection(50,p.kr1_nm_rad,p.kr3_nm_rad3)
        passed=all(checks) and d100<=targets['nominal_100n_max_translation_m'] and d200<=targets['high_200n_max_translation_m'] and d300<=targets['extreme_300n_max_translation_m'] and r50<=targets['moment_50nm_max_rotation_rad']
        qualified[c['id']]=dict(passed=passed,translation_100n_m=d100,translation_200n_m=d200,translation_300n_m=d300,rotation_50nm_rad=r50,monotone_positive_tangent_and_axis_checks=all(checks))
    return rows,curves,qualified


def fixture(s,dt):
    mass=s['bench_inertia']['bench_mass_kg']; inertia=s['bench_inertia']['bench_inertia_kg_m2']
    xml=f'''<mujoco model="progressive_interface_fixture"><option timestep="{dt:.17g}" gravity="0 0 0" integrator="implicitfast" solver="Newton" iterations="100" tolerance="1e-8"/>
    <worldbody><site name="fixed_H" pos="0 0 0"/><body name="plate"><freejoint name="free"/><inertial pos="0 0 0" mass="{mass:.17g}" diaginertia="{inertia:.17g} {inertia:.17g} {inertia:.17g}"/><geom type="sphere" size="0.01" contype="0" conaffinity="0"/><site name="moving_R" pos="0 0 0"/></body></worldbody></mujoco>'''
    m=mujoco.MjModel.from_xml_string(xml);return m,mujoco.MjData(m),xml


def fixture_state(m,d):
    mujoco.mj_fwdPosition(m,d);mujoco.mj_fwdVelocity(m,d)
    site=m.site('moving_R').id
    vel=np.empty(6);mujoco.mj_objectVelocity(m,d,mujoco.mjtObj.mjOBJ_SITE,site,vel,0)
    return AttachmentState(d.site_xpos[site].copy(),d.site_xmat[site].reshape(3,3).copy(),vel[3:].copy(),vel[:3].copy())


def ringdown(s,c,case,dt):
    params=ProgressiveParameters(**c['parameters']);m,d,xml=fixture(s,dt)
    axis=np.asarray(s['bench']['translation_direction'],float);axis/=np.linalg.norm(axis)
    rotaxis=np.asarray(s['bench']['rotation_direction'],float);rotaxis/=np.linalg.norm(rotaxis)
    x=root_deflection(case['preload_n'],params.k1_n_m,params.k3_n_m3)*axis
    theta=root_deflection(case['preload_nm'],params.kr1_nm_rad,params.kr3_nm_rad3)*rotaxis
    quat=Rotation.from_rotvec(theta).as_quat();d.qpos[:3]=x;d.qpos[3:]=quat[[3,0,1,2]];d.qvel[:]=0.
    fixed=AttachmentState(np.zeros(3),np.eye(3),np.zeros(3),np.zeros(3))
    records=[];reason='completed_ringdown';error=None;steps=int(round(s['bench']['ringdown_duration_s']/dt));tol=s['numerical_tolerances']
    try:
        for step in range(steps+1):
            r=fixture_state(m,d);v=evaluate_progressive(params,r,fixed)
            f_res=np.linalg.norm(v.robot_wrench_world[:3]+v.human_wrench_world[:3])
            moment_res=np.linalg.norm(v.robot_wrench_world[3:]+v.human_wrench_world[3:]-np.cross(r.position_world_m,v.human_wrench_world[:3]))
            kinetic=.5*s['bench_inertia']['bench_mass_kg']*float(r.velocity_world_m_s@r.velocity_world_m_s)+.5*s['bench_inertia']['bench_inertia_kg_m2']*float(r.angular_velocity_world_rad_s@r.angular_velocity_world_rad_s)
            row=dict(time_s=float(d.time),x=v.displacement_human_m.copy(),theta=v.rotation_error_human_rad.copy(),
                velocity=v.velocity_human_m_s.copy(),omega=v.angular_velocity_human_rad_s.copy(),
                force=-v.robot_wrench_world[:3].copy(),moment=-v.robot_wrench_world[3:].copy(),
                wrench_R=v.robot_wrench_world.copy(),wrench_H=v.human_wrench_world.copy(),
                U=v.spring_energy_j,D=v.damping_dissipation_w,P=v.mechanical_power_w,Udot=v.spring_energy_rate_w,
                kinetic=kinetic,total_energy=kinetic+v.spring_energy_j,force_balance=f_res,moment_balance=moment_res,
                power_identity=v.mechanical_power_w+v.spring_energy_rate_w+v.damping_dissipation_w,
                warning_count=sum(int(w.number) for w in d.warning))
            records.append(row)
            if not all(np.all(np.isfinite(value)) for value in row.values()):reason='nonfinite';break
            if row['warning_count']:reason='mujoco_warning';break
            if np.linalg.norm(row['x'])>tol['emergency_bench_translation_m'] or np.linalg.norm(row['theta'])>tol['emergency_bench_rotation_rad']:reason='emergency_motion_guard';break
            if step==steps:break
            mujoco.mj_step1(m,d)
            r=fixture_state(m,d);v=evaluate_progressive(params,r,fixed)
            d.qfrc_applied[:]=0.
            mujoco.mj_applyFT(m,d,v.robot_wrench_world[:3],v.robot_wrench_world[3:],r.position_world_m,m.body('plate').id,d.qfrc_applied)
            mujoco.mj_step2(m,d)
    except Exception:
        reason='implementation_exception';error=traceback.format_exc()
    trace={k:np.asarray([r[k] for r in records]) for k in records[0]} if records else {}
    if trace:
        t=trace['time_s'];trace['Ed']=cumtrap(trace['D'],t);trace['W']=cumtrap(trace['P'],t)
        trace['interface_R']=trace['U']-trace['U'][0]+trace['W']+trace['Ed']
        trace['total_R']=trace['total_energy']-trace['total_energy'][0]+trace['Ed']
    return trace,dict(termination=reason,error=error,fixture_xml=xml)


def local_gates(s,p,meta):
    tol=s['numerical_tolerances'];finite=bool(p and all(np.isfinite(v).all() for v in p.values()))
    if not finite:return dict(passed=False,mechanics=False,energy=False,motion=False,reason='nonfinite_or_missing_trace')
    S=float(max(np.max(p['U']),p['Ed'][-1],np.max(np.abs(p['W']))))
    absR=float(np.max(np.abs(p['interface_R'])));posR=float(max(0,np.max(p['interface_R'])))
    Rlimit=tol['energy_max_abs_residual_ratio']*S if S else 1e-10
    Plimit=tol['energy_max_positive_residual_ratio']*S if S else 1e-10
    initial=float(p['total_energy'][0]);increase=float(max(0.,np.max(np.diff(p['total_energy']),initial=0.)))
    rise_limit=max(tol['passivity_energy_roundoff_j'],tol['passivity_energy_increase_fraction_per_step']*initial)
    mechanics=bool(meta['termination']=='completed_ringdown' and not np.any(p['warning_count']) and np.max(p['force_balance'])<=tol['action_reaction_abs'] and np.max(p['moment_balance'])<=tol['action_reaction_abs'] and np.max(np.abs(p['power_identity']))<=tol['instantaneous_power_abs_w'] and np.min(p['D'])>=-tol['negative_damping_roundoff_w'])
    energy=bool(absR<=Rlimit and posR<=Plimit and increase<=rise_limit)
    decayed=bool(p['total_energy'][-1]<=tol['ringdown_final_energy_fraction']*initial)
    motion=bool(np.max(norm(p['x']))<=tol['max_ringdown_translation_m'] and np.max(norm(p['theta']))<=tol['max_ringdown_rotation_rad'])
    return dict(passed=mechanics and energy and decayed and motion,mechanics=mechanics,energy=energy,motion=motion,ringdown_decayed=decayed,
        finite=True,warning_count=int(np.max(p['warning_count'])),energy_scale_j=S,abs_R_ratio=absR/S if S else None,positive_R_ratio=posR/S if S else None,
        total_energy_balance_ratio=float(np.max(np.abs(p['total_R']))/initial) if initial else None,
        max_energy_increase_j=increase,energy_increase_limit_j=rise_limit,final_energy_fraction=float(p['total_energy'][-1]/initial) if initial else None,
        max_x_m=float(np.max(norm(p['x']))),max_theta_rad=float(np.max(norm(p['theta']))),peak_force_n=float(np.max(norm(p['force']))),peak_moment_nm=float(np.max(norm(p['moment']))),
        min_damping_w=float(np.min(p['D'])),max_force_balance_n=float(np.max(p['force_balance'])),max_moment_balance_nm=float(np.max(p['moment_balance'])),max_power_identity_w=float(np.max(np.abs(p['power_identity']))))


def compare(s,a,b):
    tol=s['numerical_tolerances'];out={}
    ta=a['time_s'];tb=b['time_s']
    coverage=abs(ta[-1]-s['bench']['ringdown_duration_s'])<1e-9 and abs(tb[-1]-s['bench']['ringdown_duration_s'])<1e-9
    if not coverage:return dict(passed=False,reason='incomplete_ringdown_coverage')
    for key,abs_key in [('force','force_n'),('moment','moment_nm'),('x','translation_m'),('theta','rotation_rad'),('U','energy_j'),('Ed','energy_j')]:
        ca=a[key];fb=b[key];scalar=ca.ndim==1
        if scalar:ca=ca[:,None];fb=fb[:,None]
        interp=np.column_stack([np.interp(tb,ta,ca[:,j]) for j in range(ca.shape[1])])
        error=norm(interp-fb);ref=norm(fb);einf=float(np.max(error));den=float(np.max(ref))
        e2=float(np.sqrt(np.trapezoid(error**2,tb)/(tb[-1]-tb[0])));den2=float(np.sqrt(np.trapezoid(ref**2,tb)/(tb[-1]-tb[0])))
        absolute=tol['absolute'][abs_key];peakdiff=abs(float(np.max(norm(a[key])))-float(np.max(norm(b[key]))))
        passed=einf<=max(absolute,tol['waveform_linf_relative']*den) and e2<=max(absolute,tol['waveform_l2_relative']*den2) and peakdiff<=max(absolute,tol['scalar_peak_relative']*den)
        if key=='force':passed=passed and peakdiff<=tol['independent_force_peak_difference_n']
        out[key]=dict(passed=passed,linf_absolute=einf,linf_relative=einf/den if den else None,l2_relative=e2/den2 if den2 else None,peak_absolute_difference=peakdiff,absolute_budget=absolute)
    return dict(passed=all(r['passed'] for r in out.values()),metrics=out)


def csv_write(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def freeze(s):
    ROOT.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(SPEC,ROOT/SPEC.name);shutil.copyfile(DOC,ROOT/DOC.name)
    write(ROOT/'registration.json',dict(spec_hash=sha(SPEC),doc_hash=sha(DOC),
        implementation_hashes={str(p.relative_to(REPO)):sha(p) for p in NEW_FILES},
        command=[sys.executable,*sys.argv],numpy=np.__version__,mujoco=mujoco.__version__,
        no_high_rom_trajectory_used_for_candidate_selection=True))
    (ROOT/'SPEC_SHA256SUMS').write_text(f'{sha(SPEC)}  {SPEC.name}\n{sha(DOC)}  {DOC.name}\n')
    print('REGISTERED',sha(SPEC),flush=True)


def run(s):
    reg=json.loads((ROOT/'registration.json').read_text())
    assert sha(SPEC)==reg['spec_hash'] and sha(DOC)==reg['doc_hash']
    for p,h in reg['implementation_hashes'].items():assert sha(REPO/p)==h,p
    (ROOT/'started.json').open('x').write(json.dumps(dict(command=[sys.executable,*sys.argv],registered_case_budget=s['bench']['run_budget']))+'\n')
    rows,curves,static=static_bench(s);csv_write(ROOT/'static_load_deflection.csv',rows);csv_write(ROOT/'static_curves.csv',curves);write(ROOT/'static_gates.json',static)
    verdicts={};flat=[];count=0
    for c in s['candidates']:
        cid=c['id'];local=[];pairs=[];contractions=[]
        if not static[cid]['passed']:
            verdicts[cid]=dict(passed=False,reason='static_targets_failed');continue
        for case in s['bench']['cases']:
            traces={}
            for dt in s['bench']['timesteps_s']:
                pair=[]
                for repeat in (1,2):
                    name=f'{cid}_{case["id"]}_dt{int(round(dt*1e6)):04d}us_repeat{repeat}'
                    directory=ROOT/name;directory.mkdir();write(directory/'case.json',dict(candidate=c,release=case,dt_s=dt,repeat=repeat))
                    p,meta=ringdown(s,c,case,dt);np.savez_compressed(directory/'trace.npz',**p)
                    (directory/'fixture.xml').write_text(meta.pop('fixture_xml'))
                    g=local_gates(s,p,meta);write(directory/'result.json',dict(**g,**meta));pair.append(p);local.append(g['passed']);count+=1
                    flat.append(dict(case=name,candidate=cid,release=case['id'],dt_s=dt,repeat=repeat,**g))
                    if meta['termination']=='implementation_exception':raise RuntimeError(meta['error'])
                same=set(pair[0])==set(pair[1]) and all(pair[0][k].shape==pair[1][k].shape and np.allclose(pair[0][k],pair[1][k],rtol=0,atol=1e-12,equal_nan=False) for k in pair[0])
                pairs.append(bool(same));traces[dt]=pair[0]
                write(ROOT/f'{cid}_{case["id"]}_dt{int(dt*1e6):04d}us_determinism.json',dict(passed=bool(same),atol=1e-12,rtol=0))
            cmp1=compare(s,traces[.001],traces[.00025]);cmp5=compare(s,traces[.0005],traces[.00025]);contraction=True
            if 'metrics' in cmp1 and 'metrics' in cmp5:
                contraction=all(a['linf_absolute']<=a['absolute_budget'] or cmp5['metrics'][k]['linf_absolute']<=a['linf_absolute']+1e-12 for k,a in cmp1['metrics'].items())
            else:contraction=False
            write(ROOT/f'{cid}_{case["id"]}_convergence.json',dict(dt1ms=cmp1,dt05ms=cmp5,refinement_contracts=contraction))
            contractions.append(cmp1['passed'] and cmp5['passed'] and contraction)
        verdicts[cid]=dict(passed=all(local+pairs+contractions),static_passed=static[cid]['passed'],all_local_gates=all(local),deterministic=all(pairs),convergence=all(contractions))
        print('CANDIDATE',cid,json.dumps(verdicts[cid]),flush=True)
    write(ROOT/'all_ringdown_results.json',flat)
    eligible=[c for c in s['candidates'] if verdicts[c['id']]['passed']]
    selected=min(eligible,key=lambda c:c['parameters']['k1_n_m'])['id'] if eligible else None
    write(ROOT/'bench_verdict.json',dict(candidates=verdicts,selected_candidate=selected,ringdowns_executed=count,
        overall='PASS' if selected else 'FAIL',gate_40_40_authorized=selected is not None,
        stop_reason=None if selected else 'NO_CANDIDATE_PASSED_STATIC_AND_1MS_NUMERICAL_GATES',
        closed_loop_trajectories_executed=0,old_candidate_retired=True))
    spec()
    for p,h in reg['implementation_hashes'].items():assert sha(REPO/p)==h,p
    print('BENCH_COMPLETE',selected,count,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--run',action='store_true')
    args=parser.parse_args();s=spec()
    if args.freeze:freeze(s)
    elif args.run:run(s)
    else:parser.error('choose --freeze or --run')
