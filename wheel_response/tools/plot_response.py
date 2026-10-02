"""Export raw target/feedback, PWM, error and timing figures."""
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
def write_figure(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=180);fig.savefig(path.with_suffix('.svg'));plt.close(fig)
def plot_trial(directory,rows,trial_id):
    if not rows:return
    dest=pathlib.Path(directory)/'figures';dest.mkdir(exist_ok=True)
    t=np.array([int(r['mcu_time_unwrapped_us']) for r in rows],dtype=float);t=(t-t[0])/1e6
    for kind in ('response','pwm','error'):
        fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,layout='constrained')
        for ax,w in zip(axes.flat,'ABCD'):
            y=np.array([float(r[f'feedback_{w}_m_s']) for r in rows]);target=np.array([float(r[f'target_{w}_m_s']) for r in rows])
            if kind=='response':ax.step(t,target,where='post',label='Recorded target',color='#d65f28');ax.plot(t,y,label='Raw feedback',color='#256caa');unit='Wheel speed (m/s)'
            elif kind=='pwm':ax.plot(t,[int(r[f'pwm_{w}_control']) for r in rows]);ax.axhline(16700,ls=':',color='gray');unit='PWM control value'
            else:ax.plot(t,y-target);ax.axhline(0,color='gray',lw=.7);unit='Feedback - target (m/s)'
            ax.set_title('Wheel '+w);ax.set_ylabel(unit);ax.set_xlabel('MCU time from first trial sample (s)');ax.grid(alpha=.2)
            if kind=='response':ax.legend(fontsize=8)
        fig.suptitle(trial_id+' — '+kind+' (raw samples)');write_figure(fig,dest/kind)
    dt=np.array([int(r['cycle_dt_us']) for r in rows])/1000
    fig,axes=plt.subplots(1,2,figsize=(11,3.5),layout='constrained');axes[0].plot(t,dt);axes[0].axhline(10,color='gray',ls=':')
    axes[0].set(xlabel='MCU time (s)',ylabel='Control interval (ms)');axes[1].hist(dt,bins=max(5,min(30,len(np.unique(dt))*2)))
    axes[1].set(xlabel='Control interval (ms)',ylabel='Sample count');fig.suptitle(trial_id+' — timing');write_figure(fig,dest/'timing')
def plot_repeats(root,groups):
    dest=pathlib.Path(root)/'summary_figures';dest.mkdir(exist_ok=True)
    for (condition,speed),trials in groups.items():
        fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,layout='constrained')
        for label,rows in trials:
            hold=next((r for r in rows if int(r['stage'])==1),None)
            if hold is None:continue
            t=np.array([(int(r['mcu_time_unwrapped_us'])-int(hold['mcu_time_unwrapped_us']))/1e6 for r in rows])
            for ax,w in zip(axes.flat,'ABCD'):
                ax.plot(t,[float(r[f'feedback_{w}_m_s']) for r in rows],alpha=.75,lw=.9,label=label)
                ax.set_title('Wheel '+w);ax.set(xlabel='MCU time relative to recorded step (s)',ylabel='Wheel speed (m/s)');ax.grid(alpha=.2)
        if trials:
            rows=trials[0][1];hold=next((r for r in rows if int(r['stage'])==1),None)
            if hold:
                t=[(int(r['mcu_time_unwrapped_us'])-int(hold['mcu_time_unwrapped_us']))/1e6 for r in rows]
                for ax,w in zip(axes.flat,'ABCD'):ax.step(t,[float(r[f'target_{w}_m_s']) for r in rows],where='post',color='black',ls='--',label='Recorded target');ax.legend(fontsize=6)
        fig.suptitle(f'{condition}, {speed:g} m/s — observed valid repeats; raw overlay')
        write_figure(fig,dest/f'{condition}_V{int(round(speed*1000)):03d}')
