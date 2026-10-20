"""Offline scientific figures from preregistered patients and completed evidence.

No controller/plant imports and no physics. Missing results are never zero.
Usage: python -B make_cross_figures.py --package CANONICAL [--mirror REVIEW]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import textwrap
from datetime import datetime, timezone

sys.dont_write_bytecode = True
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "tmp" / "mpl_figures"))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D

COLORS = {"B": "#2466a6", "H150": "#dc7326"}
STATUS = {"PASS": "#27815a", "FAIL": "#c14949", "UNKNOWN": "#abb2b9"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.labelcolor": "#263440",
    "axes.edgecolor": "#aab2bb", "grid.color": "#dce1e6", "grid.alpha": .65,
    "figure.facecolor": "white", "savefig.facecolor": "white", "axes.axisbelow": True})


class Figures:
    def __init__(self, package, output, mirror=None):
        self.p = Path(package).resolve(); self.out = Path(output).resolve()
        self.mirror = None if mirror is None else Path(mirror).resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.sources = {}; self.warnings = []; self.figures = []
        self.cohort = self.read(self.p / "VIRTUAL_PATIENT_COHORT.json", {})
        self.patients = self.cohort.get("patients", [])
        self.ids = [row["patient_id"] for row in self.patients]
        self.pairs = {pid: self.read(self.p / (pid + "_COMPARISON.json"), {}) for pid in self.ids}
        self.done = {pid: self.read(self.p / (pid + "_DONE.json"), {}) for pid in self.ids}
        self.measured = {}
        for pid in self.ids:
            for arm in COLORS:
                row = self.pairs[pid].get(arm, {})
                path = row.get("measured_path")
                self.measured[pid, arm] = self.read(self.p/path, {}) if path else {}
        self.valid_ids = [pid for pid in self.ids if self.pairs[pid].get("full_integral_comparison_valid")]
        self.complete_pairs = len(self.valid_ids)
        self.qualified_pairs = sum(bool(self.pairs[pid].get("complete_qualified_H150")) for pid in self.ids)
        self.generated = datetime.now(timezone.utc).isoformat()

    def record_source(self, path):
        path = Path(path)
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(2**20), b""): h.update(chunk)
        try: key = str(path.relative_to(self.p))
        except ValueError: key = str(path)
        self.sources[key] = {"sha256": h.hexdigest(), "bytes": path.stat().st_size}

    def read(self, path, default=None):
        if not path.exists(): return default
        try:
            raw = path.read_bytes(); value = json.loads(raw)
            self.sources[str(path.relative_to(self.p))] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            return value
        except (ValueError, OSError) as exc:
            self.warnings.append(f"Unavailable input {path.name}: {exc}")
            return default

    def value(self, pid, arm, key, joint=None, measured=False):
        row = self.measured[pid, arm] if measured else self.pairs[pid].get(arm, {})
        for name in key.split("."):
            row = row.get(name) if isinstance(row, dict) else None
        if joint is not None:
            row = row[joint] if isinstance(row, (list, tuple)) and len(row) > joint else None
        return float(row) if isinstance(row, (int, float)) and np.isfinite(row) else np.nan

    def footer(self):
        return (f"Snapshot: {self.complete_pairs}/{len(self.ids)} valid full-task pairs; "
            f"{self.qualified_pairs} fully qualified H150 pairs. Missing values are not zero. "
            "PHYSICAL_LEVEL1 simulation; no clinical or statistical-generalization claim.")

    def save(self, fig, name, title, caption, **metadata):
        fig.suptitle(title, x=.06, ha="left", fontsize=17, fontweight="bold")
        fig.text(.06, .018, "\n".join(textwrap.wrap(caption + " " + self.footer(), 160)),
            fontsize=8.5, color="#53606d", va="bottom")
        fig.subplots_adjust(top=.88, bottom=.16, left=.20 if name=="01_patient_parameters.png" else .08,
            right=.97, hspace=.5, wspace=.32)
        file = self.out / name
        fig.savefig(file, dpi=180)
        plt.close(fig)
        self.figures.append({"file": name, "title": title, "caption": caption,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), **metadata})

    def pairs_panel(self, ax, key, joint=None, measured=False, ylabel=None):
        n = len(self.ids); x = np.arange(n)
        values = {arm: np.array([self.value(pid, arm, key, joint, measured) for pid in self.ids]) for arm in COLORS}
        for j in range(n):
            if all(np.isfinite(values[a][j]) for a in COLORS):
                ax.plot([j-.12,j+.12], [values[a][j] for a in COLORS], color="#adb6bf", lw=1.5)
        for arm, offset in [("B",-.12),("H150",.12)]:
            ax.scatter(x+offset, values[arm], s=35, color=COLORS[arm], label=arm, zorder=3)
        for j in range(n):
            if not any(np.isfinite(values[a][j]) for a in COLORS):
                ax.text(j,.03,"N/A",transform=ax.get_xaxis_transform(),ha="center",va="bottom",fontsize=7,color="#858d95")
        ax.set_xticks(x, self.ids, rotation=45, ha="right")
        ax.set_xlim(-.6,n-.4); ax.grid(axis="y")
        if ylabel: ax.set_ylabel(ylabel)
        return values

    @staticmethod
    def resolved(physical):
        p=physical; height=p["height_m"]; mass=p["body_mass_kg"]
        l1=.254*height*p["thigh_length_scale"]; l2=.233*height*p["shank_length_scale"]
        m1=.099*mass*p["thigh_mass_scale"]; m2=.060*mass*p["shank_mass_scale"]
        return np.array([l1,l2,m1,m2,p["thigh_com_fraction"],p["shank_com_fraction"],
            m1*(p["thigh_inertia_radius_fraction"]*l1)**2,
            m2*(p["shank_inertia_radius_fraction"]*l2)**2,
            *p["passive_stiffness_nm_rad"],*p["passive_damping_nms_rad"]])

    def parameters(self):
        matrix=np.array([self.resolved(r["physical"]) for r in self.patients]); ratio=matrix/matrix[0]
        fig,ax=plt.subplots(figsize=(15,8.5))
        span=max(.3,float(np.max(abs(ratio-1)))); im=ax.imshow(ratio,cmap="RdBu_r",norm=TwoSlopeNorm(1,1-span,1+span),aspect="auto")
        labels=["Thigh\nlength","Shank\nlength","Thigh\nmass","Shank\nmass","Thigh\nCOM frac.","Shank\nCOM frac.","Thigh Iy","Shank Iy","Hip K","Knee K","Hip D","Knee D"]
        ax.set_xticks(range(len(labels)),labels); ax.set_yticks(range(len(self.ids)),[r["patient_id"]+"  "+r["label"].replace("_"," ") for r in self.patients])
        for (i,j),v in np.ndenumerate(ratio):ax.text(j,i,f"{v:.2f}",ha="center",va="center",fontsize=9,color="white" if abs(v-1)>span*.65 else "#172d42")
        ax.tick_params(length=0);fig.colorbar(im,ax=ax,pad=.02,label="Ratio to reference P00")
        self.save(fig,"01_patient_parameters.png","Preregistered virtual-patient parameters",
            "All registered identities shown in fixed order. Ratios derive from actual segment properties; length and mass changes also alter COM/inertia consistently. Engineering sensitivity ranges, not a sampled clinical population.",evidence="MODEL_PARAMETER_REGISTRATION",ratios=ratio.tolist(),columns=labels)

    def force(self):
        fig,axes=plt.subplots(2,1,figsize=(14,9),gridspec_kw={"height_ratios":[2,1]})
        self.pairs_panel(axes[0],"J_F_N_s",ylabel="Full-task force integral (N s)")
        axes[0].legend(frameon=False,ncols=2);axes[0].set_title("Compare B and H150 only within the same patient",loc="left",fontsize=11)
        for j,pid in enumerate(self.ids):
            pair=self.pairs[pid]; gain=pair.get("gain_percent")
            if gain is None or not pair.get("full_integral_comparison_valid"):
                axes[1].text(j,.08,"N/A",transform=axes[1].get_xaxis_transform(),ha="center",color="#858d95",fontsize=8);continue
            color=STATUS["PASS"] if pair.get("complete_qualified_H150") else STATUS["FAIL"]
            axes[1].scatter(j,gain,color=color,marker="o" if pair.get("qualified_B_reference") else "x",s=65,zorder=3)
            axes[1].annotate(f"{gain:+.2f}%",(j,gain),xytext=(0,8),textcoords="offset points",ha="center",fontsize=8)
        axes[1].axhline(0,color="#65717e",lw=1);axes[1].set_ylabel("Paired force reduction (%)")
        axes[1].set_xticks(range(len(self.ids)),self.ids);axes[1].set_xlim(-.6,len(self.ids)-.4);axes[1].grid(axis="y")
        self.save(fig,"02_paired_force_integral.png","Full-task interaction force: paired B / H150",
            "J_F uses the original 5 ms left integral. Gain=(B-H150)/B; positive is lower H150 force. Green gains are fully qualified; red gains are descriptive/incomplete qualification; x marks invalid B reference. Absolute force values across patients are not a ranking.",evidence="PHYSICAL_LEVEL1",valid_pair_ids=self.valid_ids)

    def motion(self):
        fig,axes=plt.subplots(3,2,figsize=(15,12))
        specs=[("motion_extra.outbound_overshoot_deg",False,"OUTBOUND overshoot from final issued reference"),
            ("motion_extra.return_undershoot_deg",False,"RETURN undershoot from final issued reference"),
            ("dose.excursion_deg",True,"Full-task actual excursion")]
        for r,(key,measured,title) in enumerate(specs):
            for j,joint in enumerate(["Hip","Knee"]):
                self.pairs_panel(axes[r,j],key,j,measured,ylabel="degrees");axes[r,j].set_title(joint+": "+title,loc="left",fontsize=10)
                if r==0 and j==0:axes[r,j].legend(frameon=False,ncols=2)
        self.save(fig,"03_true_motion_extrema.png","Actual Human motion: overshoot, undershoot and excursion",
            "Extrema use evaluation-only Human truth on the native 0.25 ms grid. Overshoot/undershoot use actual final issued phase references, not nominal task targets. Incomplete H150 P06/P10 full-task extrema are omitted; their completed B arms remain shown. Dots do not imply qualification.",evidence="PHYSICAL_LEVEL1",reference_definition="actual final issued phase reference")

    def tradeoff(self):
        fig,axes=plt.subplots(1,2,figsize=(15,7.5));points=[]
        for pid in self.valid_ids:
            pair=self.pairs[pid];mb=self.value(pid,"B","moment_integral_Nm_s");mh=self.value(pid,"H150","moment_integral_Nm_s")
            b=np.array([self.value(pid,"B","tracking_RMS_deg",j,True) for j in range(2)])
            h=np.array([self.value(pid,"H150","tracking_RMS_deg",j,True) for j in range(2)])
            if mb>0 and np.isfinite(mh) and np.all(np.isfinite(np.r_[b,h])):
                points.append((pid,pair["gain_percent"],100*(mh-mb)/mb,float(np.sqrt(np.mean(h*h))-np.sqrt(np.mean(b*b)))))
        if points:
            values=np.array([r[1:] for r in points]);maxc=max(.01,np.max(abs(values[:,2])))
            scatter=axes[0].scatter(values[:,0],values[:,1],c=values[:,2],cmap="RdBu_r",vmin=-maxc,vmax=maxc,s=90,edgecolor="#34495e",lw=.7)
            previous=-np.inf;label_x=float(values[:,0].max())+.12
            for pid,x,y,c in sorted(points,key=lambda row:row[2]):
                label_y=max(y+.08,previous+.32);previous=label_y
                axes[0].annotate(pid,(x,y),xytext=(label_x,label_y),fontsize=9,
                    arrowprops={"arrowstyle":"-","color":"#88949c","lw":.6})
            axes[0].set_ylim(min(-.3,float(values[:,1].min())-.3),max(previous+.2,float(values[:,1].max())+.3))
            axes[0].set_xlim(min(-.15,float(values[:,0].min())-.15),float(values[:,0].max())+.58)
            fig.colorbar(scatter,ax=axes[0],label="Change in combined tracking RMS (deg)",shrink=.78)
        else:axes[0].text(.5,.5,"No valid complete pair with\nforce, moment and tracking evidence",transform=axes[0].transAxes,ha="center",color="#697783")
        axes[0].axhline(0,color="#9ca5ae",lw=1);axes[0].axvline(0,color="#9ca5ae",lw=1);axes[0].grid()
        axes[0].set_xlabel("Paired force reduction (%) — positive is lower force")
        axes[0].set_ylabel("Moment integral change (%) — positive is higher moment")
        for j,(joint,marker) in enumerate([("Hip","o"),("Knee","s")]):
            delta=[self.value(pid,"H150","tracking_RMS_deg",j,True)-self.value(pid,"B","tracking_RMS_deg",j,True) if pid in self.valid_ids else np.nan for pid in self.ids]
            axes[1].scatter(delta,np.arange(len(self.ids))+(j-.5)*.16,marker=marker,label=joint,s=40)
        axes[1].axvline(0,color="#9ca5ae",lw=1);axes[1].set_yticks(range(len(self.ids)),self.ids);axes[1].set_ylim(len(self.ids)-.5,-.5);axes[1].grid(axis="x")
        for j,pid in enumerate(self.ids):
            if pid not in self.valid_ids:axes[1].text(.98,j,"N/A",transform=axes[1].get_yaxis_transform(),ha="right",va="center",color="#8a939b",fontsize=8)
        axes[1].set_xlabel("Tracking RMS: H150 minus matched B (degrees)");axes[1].legend(frameon=False,ncols=2,loc="lower left",bbox_to_anchor=(0,1.01))
        self.save(fig,"04_force_moment_tracking.png","Paired force–moment–tracking tradeoffs",
            "Only complete, integral-valid matched pairs enter numerical comparisons. Moment and tracking increases are costs; positive force reduction is a benefit. Combined tracking RMS is sqrt(mean(joint RMS squared)); no clinical acceptability is inferred.",evidence="PHYSICAL_LEVEL1",plotted_points=[dict(patient_id=p,force_reduction_percent=x,moment_change_percent=y,tracking_rms_change_deg=c) for p,x,y,c in points])

    def qualification(self):
        fig=plt.figure(figsize=(15,10));grid=fig.add_gridspec(2,3,height_ratios=[1,1.55]);axes=[fig.add_subplot(grid[0,j]) for j in range(3)]
        base=self.resolved(self.patients[0]["physical"])
        factors=[]
        for patient in self.patients:
            v=self.resolved(patient["physical"]);factors.append([sum(v[2:4])/sum(base[2:4]),np.mean(v[8:10]/base[8:10]),np.mean(v[10:12]/base[10:12])])
        for j,ax in enumerate(axes):
            label_groups={}
            for i,pid in enumerate(self.ids):
                pair=self.pairs[pid];gain=pair.get("gain_percent")
                if gain is None or pid not in self.valid_ids:continue
                color=STATUS["PASS"] if pair.get("complete_qualified_H150") else STATUS["FAIL"]
                ax.scatter(factors[i][j],gain,color=color,s=48,marker="o" if pair.get("qualified_B_reference") else "x")
                label_groups.setdefault(round(factors[i][j],8),[]).append((pid,gain))
            highest_label=0
            for factor_value,points in label_groups.items():
                previous=-np.inf
                for pid,gain in sorted(points,key=lambda row:(row[1],row[0])):
                    label_y=max(gain+.04,previous+.14);previous=label_y;highest_label=max(highest_label,label_y)
                    ax.annotate(pid,(factor_value,gain),xytext=(factor_value+.012,label_y),fontsize=8,
                        arrowprops={"arrowstyle":"-","color":"#88949c","lw":.6})
            ax.axhline(0,lw=1,color="#87939d");ax.grid();ax.set_xlabel(["Total leg mass / P00","Mean joint stiffness / P00","Mean joint damping / P00"][j])
            ax.set_ylabel("Paired force reduction (%)")
            factor=np.asarray(factors)[:,j];ax.set_xlim(float(factor.min())-.05,float(factor.max())+.05)
            if label_groups:ax.set_ylim(min(-.12,ax.get_ylim()[0]),max(highest_label+.12,ax.get_ylim()[1]))
        ax=fig.add_subplot(grid[1,:]);cols=["Parent\nformed","B\ntask","B\nsafety","B\nexecution","H150\ntask","H150\nsafety","H150\nexecution","H150 relative\nmotion"]
        matrix=np.zeros((len(self.ids),len(cols)));text=np.full(matrix.shape,"N/A",dtype="<U8")
        for i,pid in enumerate(self.ids):
            done=self.done[pid];formed=done.get("cold_commissioning_reached")
            vals=["PASS" if formed is True else "FAIL" if formed is False else "UNKNOWN"]
            vals += [self.pairs[pid].get(a,{}).get("axes",{}).get(k,"UNKNOWN") for a in COLORS for k in ["task","absolute_safety","causal_execution"]]
            vals += [self.pairs[pid].get("motion_relative","UNKNOWN")]
            for j,val in enumerate(vals):
                if val=="PASS":
                    matrix[i,j]=1;text[i,j]="PASS*" if j==5 and not self.pairs[pid].get("H150",{}).get("complete_task",False) else "PASS"
                elif val=="FAIL":matrix[i,j]=-1;text[i,j]="FAIL"
        cmap=ListedColormap(["#e7a5a5","#e5e9ec","#9fceb7"]);ax.imshow(matrix,cmap=cmap,norm=BoundaryNorm([-1.5,-.5,.5,1.5],3),aspect="auto")
        for (i,j),v in np.ndenumerate(matrix):ax.text(j,i,text[i,j],ha="center",va="center",fontsize=8,color="#253e4b")
        ax.set_yticks(range(len(self.ids)),self.ids);ax.set_xticks(range(len(cols)),cols);ax.tick_params(length=0)
        self.save(fig,"05_parameters_and_qualification.png","Parameter sensitivity and qualification status",
            "Top: descriptive paired gains, green fully qualified / red not fully qualified; compounds are not isolated-factor effects. Bottom: frozen gates; PASS* safety covers only the observed prefix of an incomplete task. Missing or invalid relative comparisons are N/A. A parent failure does not assert either controller would fail.",evidence="PHYSICAL_LEVEL1",factor_values=factors,status_matrix=matrix.tolist())

    def timeline(self):
        candidates=[pid for pid in self.ids if self.pairs[pid].get("motion_relative")=="FAIL"]
        candidates += [pid for pid in self.ids if pid not in candidates]
        selected=next((pid for pid in candidates if self.pairs[pid] and all(
            (self.p/"motion_series"/(pid+"_"+a+".npz")).exists()
            and (self.p/"source/results"/(pid+"_"+a)/"trace.npz").exists() for a in COLORS)),None)
        fig,axes=plt.subplots(3,2,figsize=(15,11));details={}
        if selected is None:
            for ax in axes.flat:
                ax.text(.5,.5,"No paired native motion series available",transform=ax.transAxes,ha="center",color="#697783");ax.set_axis_off()
            self.save(fig,"06_terminal_timeline.png","Terminal motion evidence — awaiting a complete pair",
                "No synthetic trajectory or mathematical reference has been substituted for missing physical data.",evidence="NO_PAIRED_NATIVE_EVIDENCE",selected_patient=None);return
        durations=[];series={};plot_data={(r,j):[] for r in range(3) for j in range(2)}
        minimum_times=[];terminal_onsets=[];reference_labels={0:[],1:[]}
        for arm,color in COLORS.items():
            path=self.p/"motion_series"/(selected+"_"+arm+".npz");self.record_source(path)
            with np.load(path) as z:
                ret=z["phase"]=="RETURN";t=z["time_s"][ret];origin=float(t[0]);elapsed=t-origin
                q=np.rad2deg(z["true_q_rad"][ret]);v=np.rad2deg(z["true_dq_rad_s"][ret]);series[arm]=(elapsed,q,v);durations.append(float(elapsed[-1]))
            tr=self.p/"source/results"/(selected+"_"+arm)/"trace.npz";self.record_source(tr)
            with np.load(tr) as z:
                mask=(z["stage"]=="TASK")&(z["task_phase"]=="RETURN");tt=z["time_s"][mask]-origin
                ref=np.rad2deg(z["reference_q_rad"][mask]);f=np.linalg.norm(z["physical_cuff_force_world_n"][mask],axis=1);m=np.linalg.norm(z["physical_cuff_moment_world_nm"][mask],axis=1)
            for j in range(2):
                axes[0,j].plot(elapsed,q[:,j],color=color,label=arm+" true q",lw=1.5)
                axes[0,j].step(tt,ref[:,j],where="post",color=color,ls="--",alpha=.7,label=arm+" issued reference",lw=1)
                minimum=int(np.argmin(q[:,j]));minimum_times.append(float(elapsed[minimum]))
                axes[0,j].plot(elapsed[minimum],q[minimum,j],"o",color=color,ms=5,zorder=5)
                axes[0,j].annotate(f"{arm} min {q[minimum,j]:.3f}° at {elapsed[minimum]:.3f}s",
                    xy=(elapsed[minimum],q[minimum,j]),xytext=(.03,.24 if arm=="B" else .10),
                    textcoords="axes fraction",fontsize=8,color=color,
                    arrowprops={"arrowstyle":"-","color":color,"lw":.8},
                    bbox={"facecolor":"white","edgecolor":"none","alpha":.85,"pad":2})
                reference_labels[j].append(f"{arm} {ref[-1,j]:.3f}°")
                axes[1,j].plot(elapsed,v[:,j],color=color,label=arm,lw=1.4)
                plot_data[0,j].extend([(elapsed,q[:,j]),(tt,ref[:,j])]);plot_data[1,j].append((elapsed,v[:,j]))
            axes[2,0].plot(tt,f,color=color,label=arm,lw=1.4);axes[2,1].plot(tt,m,color=color,label=arm,lw=1.4)
            plot_data[2,0].append((tt,f));plot_data[2,1].append((tt,m))
            intervention=self.pairs[selected].get(arm,{}).get("interventions",{}).get("rows",{}).get("H150",[])
            onset=next((r.get("start_time_s") for r in intervention if r.get("activated") and r.get("start_time_s") is not None),None)
            if onset is not None:
                terminal_onsets.append(float(onset-origin))
                for ax in axes.flat:ax.axvline(onset-origin,color=color,ls=":",lw=1,alpha=.6)
            details[arm]={"return_native_start_physics_s":origin,"native_return_duration_s":float(elapsed[-1]),"return_undershoot_deg":self.pairs[selected].get(arm,{}).get("motion_extra",{}).get("return_undershoot_deg"),"H150_receipt_onset_return_elapsed_s":None if onset is None else onset-origin}
        # Include both arms' minima and at least 0.35s antecedent to activated H150.
        # The registered patient selection remains unchanged; only the evidence window expands.
        lo=max(0,min([min(durations)-3.0,*[t-.35 for t in minimum_times],*[t-.35 for t in terminal_onsets]]));hi=max(durations)+.1
        for ax in axes.flat:ax.set_xlim(lo,hi);ax.grid();ax.set_xlabel("Seconds from each arm's actual RETURN entry")
        for (r,j),values in plot_data.items():
            local=np.concatenate([y[(t>=lo)&(t<=hi)] for t,y in values])
            if len(local):
                pad=max(.02,float(np.ptp(local))*.1);axes[r,j].set_ylim(float(local.min())-pad,float(local.max())+pad)
        for j,joint in enumerate(["Hip","Knee"]):axes[0,j].set_ylabel(joint+" angle (deg)");axes[1,j].set_ylabel(joint+" velocity (deg/s)")
        for j in range(2):axes[0,j].text(.98,.94,"Final issued reference: "+" / ".join(reference_labels[j]),transform=axes[0,j].transAxes,ha="right",va="top",fontsize=8,color="#3b4c56")
        axes[2,0].set_ylabel("Physical cuff force norm (N)");axes[2,1].set_ylabel("Physical cuff moment norm (Nm)");axes[0,0].legend(frameon=False,fontsize=8,ncols=2)
        motion=self.pairs[selected].get("motion_relative","NOT_EVALUABLE")
        self.save(fig,"06_terminal_timeline.png",f"{selected}: native terminal motion and interaction wrench",
            f"Selected in registered patient order: first evaluable motion failure, otherwise first available pair (P00 preferred). Relative motion status: {motion}. Window {lo:.3f}–{hi:.3f}s includes both minima and ≥0.35s before activated H150 receipt onset (dotted line). Native q/dq at 0.25 ms; wrench/reference at 5 ms. Time is RETURN-entry aligned, not phase-normalized; each line stops at actual completion. This terminal window does not localize every full-task failure. Motion PASS does not mean every local undershoot improved.",evidence="PHYSICAL_LEVEL1",selected_patient=selected,selection_reason="first motion failure" if motion=="FAIL" else "first available pair",arm_details=details,window_return_elapsed_s=[lo,hi])

    def run(self):
        if not self.patients:raise ValueError("Missing registered patient cohort; cannot fabricate a matrix")
        for method in (self.parameters,self.force,self.motion,self.tradeoff,self.qualification,self.timeline):method()
        manifest={"schema":"IHEAR_CROSS_PATIENT_FIGURES_V1","generated_utc":self.generated,
            "patient_count":len(self.ids),"complete_valid_pair_count":self.complete_pairs,"fully_qualified_h150_count":self.qualified_pairs,
            "physics_starts":0,"source_inputs":self.sources,"figures":self.figures,"warnings":self.warnings,
            "code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"missing_results_policy":"N/A or absent mark, never zero",
            "qualification_authority":"Original cross-analysis output; visualization does not recompute or relax gates"}
        (self.out/"FIGURE_MANIFEST.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
        lines=["# Cross-patient study figures", "", self.footer(), "", "Derived offline from immutable patient registration and the available physical evidence. Re-run after additional completed pairs; the manifest records this snapshot's exact inputs.", ""]
        for f in self.figures:lines += ["## "+f["title"],"",f["caption"],"",f"![{f['title']}]({f['file']})",""]
        (self.out/"FIGURES.md").write_text("\n".join(lines),encoding="utf-8")
        if self.mirror is not None and self.mirror!=self.out:
            self.mirror.mkdir(parents=True,exist_ok=True)
            for f in [*(self.out/x["file"] for x in self.figures),self.out/"FIGURE_MANIFEST.json",self.out/"FIGURES.md"]:shutil.copy2(f,self.mirror/f.name)
        return {k:manifest[k] for k in ["patient_count","complete_valid_pair_count","fully_qualified_h150_count","physics_starts","warnings"]}


def main():
    p=argparse.ArgumentParser();p.add_argument("--package",type=Path,required=True);p.add_argument("--output",type=Path);p.add_argument("--mirror",type=Path)
    args=p.parse_args();print(json.dumps(Figures(args.package,args.output or args.package/"figures",args.mirror).run(),ensure_ascii=False))


if __name__=="__main__":main()
