"""Fixed raw-data response metrics; no smoothing or gap filling."""
import numpy as np
def crossing(t,y,threshold):
    indices=np.flatnonzero(y>=threshold)
    if not len(indices): return None
    k=int(indices[0])
    if k==0:return float(t[0])
    if t[k]-t[k-1]>0.015:return None
    return float(t[k-1]+(threshold-y[k-1])*(t[k]-t[k-1])/(y[k]-y[k-1]))
def wheel_metrics(rows,wheel,definition,plan):
    out={'wheel':wheel,'rise_time_s':None,'settling_time_s':None,'overshoot_pct':None,
         'tail_mean_error_m_s':None,'tail_mae_m_s':None,'hold_rmse_m_s':None,'tail_rmse_m_s':None,
         'pwm_saturation_fraction':None,'band_m_s':None,'stop_time_s':None,'reason':''}
    pre=[r for r in rows if int(r['stage'])==0 and int(r['state'])==2]
    hold=[r for r in rows if int(r['stage'])==1 and int(r['state'])==2]
    post=[r for r in rows if int(r['stage'])==2 and int(r['state'])==3]
    reasons=[]
    if not pre or not hold:out['reason']='missing_pre_or_hold';return out
    key=f'feedback_{wheel}_m_s';target=f'target_{wheel}_m_s'
    start=int(hold[0]['mcu_time_unwrapped_us'])/1e6
    t=np.array([int(r['mcu_time_unwrapped_us'])/1e6-start for r in hold]); y=np.array([float(r[key]) for r in hold])
    r=np.array([float(row[target]) for row in hold]);r1=float(r[0]);t0=int(hold[0]['mcu_time_unwrapped_us'])
    before=[float(row[key]) for row in pre if t0-1_000_000<=int(row['mcu_time_unwrapped_us'])<t0]
    if len(before)<99 or not np.all(np.isfinite(y)) or not np.allclose(r,r1,rtol=0,atol=1e-6):
        out['reason']='insufficient_baseline_or_nonconstant_target';return out
    y0=float(np.mean(before));amplitude=r1-y0
    if amplitude<=0:out['reason']='nonpositive_amplitude';return out
    quant=definition.get('verified_quantization_m_s',{}).get(wheel)
    if quant is None: reasons.append('quantization_not_verified_settling_unavailable')
    else: out['band_m_s']=max(.05*abs(amplitude),2*quant)
    a=crossing(t,y,y0+.1*amplitude);b=crossing(t,y,y0+.9*amplitude)
    if a is not None and b is not None:out['rise_time_s']=b-a
    else:reasons.append('threshold_not_reached_or_crossing_gap')
    gaps=np.array([int(row['sequence_delta'])!=1 or int(row['cycle_dt_us'])>15000 for row in hold]);gaps[0]=False
    complete=len(hold)==plan['hold_ms']//10 and not np.any(gaps)
    if complete and out['band_m_s'] is not None:
        outside=np.abs(y-r1)>out['band_m_s'];bad=np.flatnonzero(outside);k=int(bad[-1]+1) if len(bad) else 0
        if k<len(t) and t[-1]-t[k]>=1-1e-9:out['settling_time_s']=float(t[k])
        else:reasons.append('not_settled_in_hold_window')
    elif not complete:reasons.append('hold_gap_or_incomplete_settling_unavailable')
    out['overshoot_pct']=max(0,float(np.max(y))-r1)/abs(amplitude)*100
    err=y-r1;out['hold_rmse_m_s']=float(np.sqrt(np.mean(err**2)))
    pwm=np.array([int(row[f'pwm_{wheel}_control']) for row in hold]);out['pwm_saturation_fraction']=float(np.mean(np.abs(pwm)>=16700))
    hold_end=(int(post[0]['mcu_time_unwrapped_us'])/1e6-start) if post else float(t[-1])
    tail=t>=hold_end-2-1e-9
    if complete and np.count_nonzero(tail)>=199:
        e=err[tail];out.update(tail_mean_error_m_s=float(np.mean(e)),tail_mae_m_s=float(np.mean(np.abs(e))),tail_rmse_m_s=float(np.sqrt(np.mean(e**2))))
    else:reasons.append('insufficient_complete_tail')
    zero=definition.get('zero_speed_band_m_s',{}).get(wheel)
    if zero is not None and len(post)==plan['post_ms']//10:
        pt=np.array([(int(row['mcu_time_unwrapped_us'])-int(post[0]['mcu_time_unwrapped_us']))/1e6 for row in post])
        py=np.array([float(row[key]) for row in post]);bad=np.flatnonzero(np.abs(py)>zero);k=int(bad[-1]+1) if len(bad) else 0
        continuous=all(int(row['sequence_delta'])==1 and int(row['cycle_dt_us'])<=15000 for row in post[1:])
        if continuous and k<len(pt) and pt[-1]-pt[k]>=1-1e-9:out['stop_time_s']=float(pt[k])
        else:reasons.append('post_gap_stop_unavailable' if not continuous else 'post_zero_band_not_continuously_held')
    else:reasons.append('zero_band_not_verified_stop_unavailable' if zero is None else 'post_incomplete_stop_unavailable')
    out['reason']=';'.join(reasons);out['baseline_y0_m_s']=y0;out['actual_target_m_s']=r1
    return out
