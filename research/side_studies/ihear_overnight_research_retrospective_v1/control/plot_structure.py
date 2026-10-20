from pathlib import Path
import os,json
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
os.environ['MPLCONFIGDIR']=str(S/'control/matplotlib');os.environ['OPENBLAS_NUM_THREADS']='1'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager
from matplotlib.patches import FancyBboxPatch
font='/mnt/c/Windows/Fonts/msyh.ttc';fontManager.addfont(font)
family=FontProperties(fname=font).get_name()
plt.rcParams.update({'font.family':family,'axes.unicode_minus':False,'font.size':12,'savefig.facecolor':'white'})
F=S/'FIGURES';F.mkdir(exist_ok=True)
colors=['#356DA4','#337F69','#9A6946'];dark='#263344'
def box(ax,x,y,w,h,text,color=colors[0],size=12):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.015,rounding_size=0.02',facecolor=color,edgecolor='white',lw=1.2))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',color='white',fontsize=size,linespacing=1.65)
def arrow(ax,x1,y1,x2,y2):ax.annotate('',(x2,y2),(x1,y1),arrowprops=dict(arrowstyle='-|>',color='#667080',lw=1.6))
def save(fig,name):fig.savefig(F/name,dpi=160,bbox_inches='tight');plt.close(fig)

fig,ax=plt.subplots(figsize=(14,9));ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
ax.text(.5,.975,'谁决定运动？架构转变经历了两个阶段',ha='center',fontsize=21,color=dark,weight='bold')
headers=['给定整条轨迹','Goal-directed torque MPC','在线下一对关节目标']
rows=[['外部规定 endpoint、速度和时长\n生成 q_ref / dq_ref / ddq_ref','任务给 start / goal / phase\n不再规定整条时间路径','任务目标 + 因果 state / belief\n高层提出 hip / knee waypoint'],
      ['Inverse dynamics + feedback\n或后期 tracking MPC','预测 generalized torque 序列\n执行首个 action','原 quintic 生成下一段\n运动/ROM/clearance/mechanics 筛选'],
      ['机器人 wrench / torque 执行\n真实接触推动被动 Human','仍需原机器人执行层\n历史 interface / HOLD / motion 失败','当前状态准入 + source age\nFAST / governor / bridge / fallback']]
for col in range(3):
    x=.025+col*.33
    ax.text(x+.145,.90,headers[col],ha='center',fontsize=16,weight='bold',color=colors[col])
    for row in range(3):
        y=.66-row*.235;box(ax,x,y,.285,.175,rows[row][col],colors[col],11.5)
        if row<2:arrow(ax,x+.145,y-.015,x+.145,y-.055)
    if col<2:arrow(ax,x+.303,.748,x+.326,.748)
ax.text(.5,.095,'角目标 ≠ 直接设置人体 qpos；在线规划 ≠ 取消轨迹规划',ha='center',fontsize=16,color=dark,weight='bold')
ax.text(.5,.040,'Phase3 初版是接口 smoke；完整 robot + lifecycle 在后续接齐。源码、版本与分母见 ARCHITECTURE_EVOLUTION.md。',ha='center',fontsize=10.5,color='#5B6573')
save(fig,'01_ARCHITECTURE_BEFORE_AFTER.png')

fig,ax=plt.subplots(figsize=(15,10));ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
ax.text(.5,.975,'研究演变：实际困难推动了结构变化',ha='center',fontsize=21,color=dark,weight='bold')
items=[('简化对象与示意脚本','Spring2D / 直接 Human torque','物理权限与接触定义不同'),
       ('固定参考的真实执行','Human V2 + robot + cuff','扩大 ROM，command-safe ≠ physical-safe'),
       ('由目标驱动运动','Goal torque → online waypoint','预测/执行一致性，HOLD/RETURN，motion 合同'),
       ('B 执行底座','commissioning / admission / ownership','计划可行、任务完成、host 资格须分开'),
       ('学习与协调证据','E → native linear Q → Neural Q','有降力但缺 state 排序与平顺优势'),
       ('同状态公平比较','live-state fork / native residual search','旧 snapshot 不可恢复；RETURN 状态收敛'),
       ('更自由的参考研究','common / differential progress / velocity','LEVEL1 teacher；治疗等效与接口迁移待定')]
for i,(title,method,problem) in enumerate(items):
    y=.805-i*.112
    ax.text(.025,y+.023,str(i+1),fontsize=22,color=colors[i%3],weight='bold')
    box(ax,.08,y-.010,.31,.085,title,colors[i%3],13)
    ax.text(.43,y+.046,method,fontsize=12.5,color=dark,va='center')
    ax.text(.43,y+.005,problem,fontsize=11.5,color='#5B6573',va='center')
    if i<6:arrow(ax,.233,y-.017,.233,y-.027)
ax.text(.5,.035,'按问题组织；日期与 source 见 RESEARCH_TIMELINE.md。教授上次实际汇报边界未确认。',ha='center',fontsize=10.5,color='#5B6573')
save(fig,'02_PROBLEM_DRIVEN_EVOLUTION.png')

fig,ax=plt.subplots(figsize=(14,7));ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
ax.text(.5,.96,'已有能力与尚未证明的能力',ha='center',fontsize=21,color=dark,weight='bold')
items=[('完整动力学与真实 robot / cuff 执行','有限条件成立','不是患者或硬件验证'),
       ('同完整状态 scientific fork','精确复现成立','没有 durable checkpoint / OS 时钟复制'),
       ('旧 M2 force 收益','同 Human 有限研究成立','motion 负担增大；不是 state-conditioned 学习'),
       ('自由参考优质 teacher','上轮开发 2.457489% / LEVEL1','合法状态 motion 1/2；非原 B LEVEL2'),
       ('正式 host / deployment 资格','未统一成立','strict55 / R2 / FAST 各合同保留原结果'),
       ('few-repetition 个体化 / 临床效果','尚未证明','不能由仿真 PASS 推导')]
for i,(cap,level,lim) in enumerate(items):
    y=.805-i*.125
    ax.text(.025,y,cap,fontsize=12,color=dark,va='center')
    box(ax,.425,y-.034,.225,.072,level,colors[1] if i<4 else colors[2],11.5)
    ax.text(.68,y,lim,fontsize=11.3,color='#5B6573',va='center')
ax.text(.5,.03,'科学、原生接口、host、部署、临床分别评价。上轮数值是历史证据；今晚结果另列。',ha='center',fontsize=10.5,color='#5B6573')
save(fig,'03_CAPABILITY_BOUNDARIES.png')
print('STRUCTURAL_FIGURES_WRITTEN',len(list(F.glob('*.png'))))
