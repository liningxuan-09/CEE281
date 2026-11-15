"""Reproduce synchronized report illustrations from evaluation seed 110.

All traffic comparisons are trajectories on the same 0--45 min, 0--2 km axes.
Only the three selected recorded runs are recovered; their summaries must match
the saved evaluation results. Existing multi-seed experiment files are untouched.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import replace
import hashlib
import json
from multiprocessing import Pool
import os
from pathlib import Path
import sys
import time

import numpy as np

PROJECT=Path(__file__).resolve().parent
CACHE=PROJECT/'results/report_seed110'
FIGURES=PROJECT/'report/figures'
SEED=110
CASES={'A':{},'ALINEA':{'ramp_control':'alinea'},'B50':{'acc_share':.5}}


def recover_case(name):
    from model import Config,run
    path=CACHE/(name+'.npz')
    summary_path=CACHE/(name+'_summary.json')
    if path.exists() and summary_path.exists():
        return name,json.loads(summary_path.read_text()),'cached'
    print(f'Recovering recorded trajectories: {name}, seed {SEED}',flush=True)
    started=time.monotonic()
    result=run(replace(Config(),seed=SEED,**CASES[name]),record=True)
    summary=result['summary']
    ref_path=PROJECT/('results/tmc_alinea/eval_seeds_101-120/comparison.json' if name=='ALINEA' else 'results/acc_main/eval_seeds_101-120/comparison.json')
    ref=json.loads(ref_path.read_text())['per_seed']['A-ALINEA' if name=='ALINEA' else name][str(SEED)]
    for key in ['accumulated_delay_veh_s','total_delay_main_veh_s','total_delay_ramp_veh_s','stops_at_lane_end']:
        if not np.isclose(summary[key],ref[key],rtol=1e-9,atol=1e-5):
            raise RuntimeError(f'{name}: {key} does not match saved evaluation: {summary[key]} vs {ref[key]}')
    tr=[r for r in result['trajectories'] if r['lane']==0]
    arrivals=np.array(sorted((r['origin'],r['scheduled_s']) for r in result['trips']),dtype=float)
    np.savez_compressed(path,t=np.array([r['t_s'] for r in tr]),
                        id=np.array([r['id'] for r in tr],dtype=np.int32),
                        x=np.array([r['x_km'] for r in tr]),
                        v=np.array([r['v_kmh'] for r in tr]),arrivals=arrivals)
    summary_path.write_text(json.dumps(summary,indent=2))
    if name=='ALINEA':
        with (CACHE/'ALINEA_tmc.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(result['tmc'][0]));writer.writeheader();writer.writerows(result['tmc'])
    print(f'{name}: verified against saved evaluation; {len(tr)} trajectory points; {time.monotonic()-started:.1f} s',flush=True)
    return name,summary,'recovered'


def setup_plotting():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for filename in ['Times New Roman.ttf','Times New Roman Bold.ttf','Times New Roman Italic.ttf']:
        font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/'+filename)
    plt.rcParams.update({'font.family':'Times New Roman','font.size':11,'axes.labelsize':11,
        'axes.titlesize':11,'xtick.labelsize':11,'ytick.labelsize':11,'legend.fontsize':11,
        'pdf.fonttype':42,'figure.facecolor':'white','axes.facecolor':'white',
        'axes.edgecolor':'black','text.color':'black','axes.labelcolor':'black',
        'xtick.color':'black','ytick.color':'black','axes.linewidth':.65})
    return plt


def trajectory_data(name):
    with np.load(CACHE/(name+'.npz')) as d:
        t,ids,x,v=(d[k] for k in ['t','id','x','v'])
    order=np.lexsort((t,ids));t,ids,x,v=(a[order] for a in [t,ids,x,v])
    valid=(ids[1:]==ids[:-1])&((t[1:]-t[:-1])<1.1)&(t[:-1]>=0)&(t[1:]<=2700)
    coordinates=np.column_stack((t/60,x))
    segments=np.stack((coordinates[:-1][valid],coordinates[1:][valid]),axis=1)
    speeds=(v[:-1][valid]+v[1:][valid])/2
    return segments,speeds


def build_comparisons(plt):
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LinearSegmentedColormap,Normalize
    cmap=LinearSegmentedColormap.from_list('report_speed',[(0,'#8b0000'),(.35,'#e8452d'),(.65,'#ffffbf'),(1,'#1a9850')])
    norm=Normalize(0,120)
    arrays={name:trajectory_data(name) for name in CASES}
    specs=[('ALINEA','fig3_trajectories_tmc.pdf','ALINEA, all human-driven'),('B50','fig7_trajectories.pdf','50% ACC, unmetered')]
    baseline_hash=hashlib.sha256(arrays['A'][0].tobytes()+arrays['A'][1].tobytes()).hexdigest()
    for treatment,filename,label in specs:
        fig=plt.figure(figsize=(6.5,3.8))
        axes=[fig.add_axes([.11,.31,.34,.49]),fig.add_axes([.50,.31,.34,.49])]
        for ax,name,title in zip(axes,['A',treatment],['(a) Baseline: 0% ACC','(b) '+label]):
            segments,speeds=arrays[name]
            lc=LineCollection(segments,cmap=cmap,norm=norm,linewidths=.35,rasterized=True)
            lc.set_array(speeds);ax.add_collection(lc)
            for y in [1.05,1.50]:ax.axhline(y,color='black',ls='--',lw=.65)
            ax.axvline(40,color='black',ls=':',lw=.65)
            ax.set(xlim=(0,45),ylim=(0,2),xlabel='Time (min)')
            ax.set_xticks([0,15,30,45]);ax.set_yticks([0,.5,1,1.5,2])
            ax.set_title(title,loc='left',pad=10)
            s=json.loads((CACHE/(name+'_summary.json')).read_text())
            ax.text(.5,-.34,f'Delay: {s["accumulated_delay_veh_s"]/3600:.1f} veh h\nCongested: {s["congestion_duration_s"]/60:.1f} min',
                    transform=ax.transAxes,ha='center',va='top',fontsize=11)
            if name=='A':ax.set_ylabel('Position (km)')
            else:ax.tick_params(labelleft=False)
        fig.text(.11,.95,'Seed 110 | trajectories | 0-45 min',ha='left',va='top',fontsize=11)
        cax=fig.add_axes([.88,.31,.018,.49])
        cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax)
        cb.set_ticks([0,30,60,90,120]);cb.set_label('Speed (km/h)',labelpad=6)
        fig.savefig(FIGURES/filename,dpi=350)
        fig.savefig(FIGURES/filename.replace('.pdf','.png'),dpi=180)
        plt.close(fig)
    from PIL import Image
    a=np.asarray(Image.open(FIGURES/'fig3_trajectories_tmc.png').convert('RGB'))
    b=np.asarray(Image.open(FIGURES/'fig7_trajectories.png').convert('RGB'))
    left=int(a.shape[1]*.47)
    if not np.array_equal(a[:,:left],b[:,:left]):
        raise RuntimeError('The two rendered baseline panels must be pixel-identical')
    return baseline_hash


def build_timeline(plt):
    with (CACHE/'ALINEA_tmc.csv').open() as f:rows=list(csv.DictReader(f))
    def col(key):return np.array([float(r[key]) if r[key] not in ('','None') else np.nan for r in rows])
    t=col('t_s')/60
    fig,axes=plt.subplots(3,1,figsize=(6.5,4.2),sharex=True)
    fig.subplots_adjust(left=.14,right=.98,bottom=.14,top=.86,hspace=.66)
    fig.text(.14,.98,'Seed 110 | controller trace | 0-45 min',ha='left',va='top',fontsize=11)
    axes[0].plot(t,col('occupancy')*100,color='#2878b5',lw=1,label='D1400')
    axes[0].axhline(14,color='black',lw=.8,ls='--',label='Target')
    axes[0].set_ylabel('Occupancy (%)');axes[0].set_ylim(0,40)
    axes[1].step(t,col('rate_veh_h'),where='post',color='#8054a1',lw=1,label='ALINEA')
    axes[1].step([0,5,35,45],[100,450,0,0],where='post',ls='--',color='black',lw=.8,label='Ramp demand')
    axes[1].set_ylabel('Rate (veh/h)');axes[1].set_ylim(0,1000)
    axes[2].plot(t,col('queue_true_veh'),color='#288f87',lw=1,label='Truth')
    axes[2].plot(t,col('queue_est_veh'),color='black',ls=':',lw=1.1,label='Estimate')
    axes[2].plot(col('forecast_target_s')/60,col('forecast_veh'),color='#df9242',ls='--',lw=1,label='60 s forecast')
    axes[2].set_ylabel('Queue (veh)');axes[2].set_xlabel('Time (min)')
    for ax,title in zip(axes,['(a) Occupancy','(b) Ramp release','(c) Ramp queue']):
        ax.set_title(title,loc='left',pad=14)
        ax.legend(frameon=False,ncol=2 if ax!=axes[2] else 3,loc='lower right',bbox_to_anchor=(1,1.03),borderaxespad=0,handlelength=1.2,columnspacing=.7)
        ax.set_xlim(0,45);ax.set_xticks([0,15,30,45]);ax.spines[['top','right']].set_visible(False)
    fig.savefig(FIGURES/'fig4_tmc_timeline.pdf',dpi=300);plt.close(fig)
    window=(t>=5)&(t<40)
    return {'updates':int(window.sum()),'below_450':int(np.sum(col('rate_veh_h')[window]<450)),
            'at_minimum':int(np.sum(col('rate_veh_h')[window]<=200+1e-6)),
            'mean_occupancy_percent':float(np.nanmean(col('occupancy')[window])*100)}


def build_arrivals(plt):
    from arrival_check import arrivals,counts,expected_cum
    from model import Config
    c=Config();m,r=arrivals(SEED,c)
    main_counts=[];ramp_counts=[]
    for seed in range(101,121):
        mm,rr=arrivals(seed,c);main_counts.extend(counts(mm,0,2400));ramp_counts.extend(counts(rr,300,2100))
    fig,axes=plt.subplots(1,2,figsize=(6.5,3.2))
    fig.subplots_adjust(left=.12,right=.98,bottom=.22,top=.85,wspace=.4)
    tt=np.linspace(0,2700,450)
    for arr,profile,color,label in [(m,c.main_profile,'#2878b5','Mainline'),(r,c.ramp_profile,'#e17d22','Ramp')]:
        axes[0].step(np.r_[0,arr,2700]/60,np.r_[0,np.arange(1,len(arr)+1),len(arr)],where='post',color=color,lw=1,label=label)
        axes[0].plot(tt/60,expected_cum(profile,tt),color='black',lw=.7,ls='--')
    axes[0].plot([],[],color='black',lw=.7,ls='--',label='Target')
    axes[0].set(xlim=(0,45),ylim=(0,1250),xlabel='Time (min)',ylabel='Cumulative vehicles')
    axes[0].set_xticks([0,15,30,45]);axes[0].set_yticks([0,400,800,1200])
    axes[0].set_title('(a) Seed 110 arrivals',loc='left');axes[0].legend(frameon=False,loc='upper left',handlelength=1.2)
    import math
    for cc,color,label in [(np.array(main_counts),'#2878b5','Mainline'),(np.array(ramp_counts),'#e17d22','Ramp peak')]:
        k=np.arange(int(max(cc))+2);emp=np.bincount(cc,minlength=len(k))[:len(k)]/len(cc)
        axes[1].bar(k,emp,.8,color=color,alpha=.65,label=label)
        lam=np.mean(cc);pmf=[math.exp(-lam)*lam**int(i)/math.factorial(int(i)) for i in k]
        axes[1].plot(k,pmf,color='black',ls='--',lw=.8)
    axes[1].plot([],[],color='black',ls='--',lw=.8,label='Poisson')
    axes[1].set(xlim=(-.5,28),ylim=(0,.25),xlabel='Vehicles per 30 s',ylabel='Share of intervals')
    axes[1].set_title('(b) 20-seed arrival counts',loc='left');axes[1].legend(frameon=False,handlelength=1.2)
    axes[1].set_xticks([0,10,20]);axes[1].set_yticks([0,.1,.2])
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.savefig(FIGURES/'fig2_arrivals.pdf',dpi=300);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recover-only',action='store_true')
    args=parser.parse_args()
    CACHE.mkdir(parents=True,exist_ok=True);FIGURES.mkdir(exist_ok=True)
    with Pool(3) as pool:recovered=pool.map(recover_case,list(CASES))
    base=np.load(CACHE/'A.npz')['arrivals']
    for name in CASES:
        assert np.array_equal(base,np.load(CACHE/(name+'.npz'))['arrivals']),f'{name}: arrivals differ'
    if args.recover_only:return
    plt=setup_plotting()
    baseline_hash=build_comparisons(plt)
    trace=build_timeline(plt);build_arrivals(plt)
    payload={'seed':SEED,'plot_type':'vehicle trajectories','time_range_min':[0,45],
             'position_range_km':[0,2],'speed_range_kmh':[0,120],
             'baseline_trajectory_sha256':baseline_hash,'same_arrivals_all_cases':True,
             'timeline':trace,'summaries':{name:s for name,s,_ in recovered}}
    (CACHE/'figure_manifest.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps({'baseline_hash':baseline_hash,'timeline':trace,
                      'summary':{name:{'delay_veh_h':s['accumulated_delay_veh_s']/3600,
                                       'congested_min':s['congestion_duration_s']/60,
                                       'approach_kmh':s['approach_speed_kmh']} for name,s,_ in recovered}},indent=2),flush=True)


if __name__=='__main__':main()
