"""Review one completed AIR trial before the next separately issued START."""
import argparse, csv, json, pathlib
from analyze_response import write_csv
from metrics import wheel_metrics
from validate_data import validate
from wheel_response_cli import register_update, save_json, local_now

def review(directory,condition='AIR'):
    directory = pathlib.Path(directory)
    meta = json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    plan = meta['actual_plan']
    definition = json.loads((directory/'metric_definition.json').read_text(encoding='utf-8'))
    report = validate(directory)
    with (directory/'samples.csv').open(encoding='utf-8', newline='') as f:
        rows = [r for r in csv.DictReader(f) if int(r['run_id']) == plan['run_id']]
    active = [r for r in rows if int(r['state']) in (2,3)]
    complete = [r for r in rows if int(r['state']) == 4]
    terminal_tail = [r for r in complete if int(r['mcu_time_unwrapped_us']) >= int(complete[-1]['mcu_time_unwrapped_us']) - 90000] if complete else []
    hold = [r for r in active if int(r['stage']) == 1]
    reasons = list(report['reasons'])
    if plan['condition'] != condition: reasons.append('not_'+condition.lower()+'_trial')
    if not meta.get('complete') or meta.get('final_state') != 4: reasons.append('not_complete')
    if not complete: reasons.append('no_terminal_samples')
    if any(int(r['fault_flags']) for r in rows): reasons.append('fault_present')
    checks = {}; metrics = []
    for w in 'ABCD':
        values = [float(r[f'feedback_{w}_m_s']) for r in hold]
        zero = definition['zero_speed_band_m_s'][w]
        c = {'hold_peak_m_s': max(values) if values else None,
             'hold_min_m_s': min(values) if values else None,
             'hold_net_counts': sum(int(r[f'encoder_{w}_counts']) for r in hold),
             'complete_feedback_max_abs_m_s': max((abs(float(r[f'feedback_{w}_m_s'])) for r in complete), default=None),
             'final_100ms_feedback_max_abs_m_s': max((abs(float(r[f'feedback_{w}_m_s'])) for r in terminal_tail), default=None),
             'complete_pwm_max_abs': max((abs(int(r[f'pwm_{w}_control'])) for r in complete), default=None)}
        # Gross anomaly screening, fixed before repeated starts; no tuning of metric bands.
        if not values or c['hold_net_counts'] <= 0: reasons.append('no_forward_feedback_'+w)
        if values and (max(values) > plan['step_mm_s']/1000*1.5 + .03 or min(values) < -.02): reasons.append('gross_speed_anomaly_'+w)
        if any(abs(int(r[f'pwm_{w}_control'])) >= 16700 for r in hold): reasons.append('pwm_saturation_'+w)
        if len(terminal_tail) < 10 or (terminal_tail and c['final_100ms_feedback_max_abs_m_s'] > zero): reasons.append('terminal_tail_not_zero_'+w)
        if complete and (c['complete_feedback_max_abs_m_s'] > .05 or c['complete_pwm_max_abs'] != 0): reasons.append('terminal_gross_motion_or_output_'+w)
        c['zero_drive_transition_note'] = 'Any short COMPLETE transition feedback is retained; continuation requires final 100 ms within the prelocked zero band and zero PWM throughout COMPLETE. Normal POST metrics remain unchanged.'
        checks[w] = c
        m = wheel_metrics(active,w,definition,plan)
        m.update(trial_id=plan['trial_id'],condition=plan['condition'],planned_speed_m_s=plan['step_mm_s']/1000,
                 valid_data=report['valid'],precheck=bool(plan.get('precheck')),validation_reasons=';'.join(report['reasons']))
        metrics.append(m)
    performance_notes = {m['wheel']:m['reason'] for m in metrics if m['reason']}
    result = {'trial_id': plan['trial_id'], 'reviewed_local': local_now(), 'passed': not reasons,
              'reasons': sorted(set(reasons)), 'data_valid': report['valid'], 'samples': report['actual_samples'],
              'wheels': checks, 'performance_notes':performance_notes,
              'physical_setup_source': 'User authorizes remaining AIR trials while continuously raised; no new visual observation claimed.' if condition=='AIR' else 'GROUND setup recorded in the trial snapshot; operator independently confirms placement for each START. No physical observations inferred from telemetry.'}
    save_json(directory/'continuation_review.json',result)
    write_csv(directory/'metrics.csv',metrics)
    register_update(plan['trial_id'],actual_order=meta['actual_order'])
    print(json.dumps(result,ensure_ascii=False))
    return result['passed']

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory');args=ap.parse_args()
    raise SystemExit(0 if review(args.directory) else 2)
