from pathlib import Path
import json,datetime
P=Path(__file__).resolve().parents[1];m=json.loads((P/'analysis/FROZEN_BRANCH_MODEL.json').read_text());p=json.loads((P/'predictions/DEV_PREREGISTERED_PREDICTIONS.json').read_text());rows=[]
for a in p['actions']:
 if a['tag']!='C19' and 'local_delta' not in a:continue
 pr=a['prediction'];phi=pr['predicted_phi'];rate=abs(pr['predicted_rate']);h=m['h_s'];band=h*rate-50*h*h/(2*m['L_m']);levels=[]
 for eps in [0,1e-8,1e-7,1e-6,1e-5]:
  min_abs=max(0,abs(phi)-eps);max_abs=abs(phi)+eps;label='ROBUST_SEVERE_SPIKE' if max_abs<band else 'ROBUST_NO_SEVERE_SPIKE' if min_abs>band else 'AMBIGUOUS'
  levels.append(dict(assumed_phi_error_rad=eps,label=label,scope='hypothetical error sensitivity, not a certified state-error bound'))
 rows.append(dict(tag=a['tag'],predicted_phi_rad=phi,crossing_time_offset_microseconds=1e6*abs(phi)/rate,severe_spike_halfwidth_phi_rad=band,error_sensitivity=levels))
slope=m['coefficients'][1][0];intercept=m['coefficients'][0][0];rate=m['coefficients'][0][1];b=m['h_s']*abs(rate)-50*m['h_s']**2/(2*m['L_m']);limits=sorted([(-b-intercept)/slope,(b-intercept)/slope]);out=dict(status='EXECUTED_ZERO_PHYSICS_SENSITIVITY',nominal_local_severe_spike_delta_interval=limits,rows=rows,control_period_s=.005,difference_halfwidth_s=1e-5,extrapolation='LOO interpolation residual is not an observer/model-error bound. At an unseen prefix, strict model abstains.',new_physics_steps=0)
(P/'analysis/BRANCH_UNCERTAINTY_SENSITIVITY.json').write_text(json.dumps(out,indent=2)+'\n');print('PREDICTED_LOCAL_BAND',limits)
# Disable the confusing numeric offset on the force axis of the scientific plot.
f=P/'source/make_figures.py';s=f.read_text().replace("axs[2].set_ylabel('Full-task JF (N·s)')","axs[2].set_ylabel('Full-task JF (N·s)');axs[2].ticklabel_format(axis='y',style='plain',useOffset=False)");f.write_text(s)
f=P/'CLEARANCE_GEOMETRY_ANALYSIS.md';s=f.read_text();s+='\n## 局部模式与误差敏感性\n\n六个新微扰显示：跨支曲率幅度虽不同，超过可行范围后原guard在相同加速度box角点饱和，实际jerk RMS接近同一平台；因此不能用曲率下降比例预测运动改善。原native jerk保持未滤波。冻结局部响应模型的严重冲击参数带约为x[3]相对C19的[−0.000331,0.000403]，仅适用于已冻结同父同cell。10μs差分半宽远小于5ms采样周期；额外φ误差会移动窄失败带。analysis/BRANCH_UNCERTAINTY_SENSITIVITY.json列出假定误差1e−8至1e−5rad的敏感性，不把很小LOO拟合残差当成真实observer误差界。\n';f.write_text(s)
