"""Offline review of an intentional AIR ABORT/heartbeat test; never clears a fault or sends commands."""
import argparse,csv,json,pathlib,math
from validate_data import validate
from wheel_response_cli import save_json,local_now
def review(directory,kind):
    d=pathlib.Path(directory);m=json.loads((d/'metadata.json').read_text(encoding='utf-8'));p=m['actual_plan']
    expected=2 if kind=='abort' else 1
    events=[json.loads(line) for line in (d/'commands.jsonl').read_text(encoding='utf-8').splitlines()]
    report=validate(d)
    # FAULT deliberately interrupts the normal phases. Integrity/identity failures remain failures.
    expected_normal_failures={'phase_sample_count_mismatch','not_normal_complete','missing_complete_sample','fault_flags_present'}
    reasons=[r for r in report['reasons'] if r not in expected_normal_failures]
    if not p.get('precheck') or p['condition']!='AIR':reasons.append('requires_AIR_precheck')
    if not any(e.get('event')==('intentional_abort_trigger' if kind=='abort' else 'intentional_heartbeat_loss') for e in events):reasons.append('missing_intentional_trigger')
    rows=[r for r in csv.DictReader((d/'samples.csv').open(encoding='utf-8')) if int(r['run_id'])==p['run_id']]
    faults=[r for r in rows if int(r['state'])==5]
    if m.get('final_state')!=5 or not faults:reasons.append('missing_terminal_fault')
    if any(int(r['fault_flags']) not in (0,expected) for r in rows):reasons.append('unexpected_fault_flags')
    if any(int(r['fault_flags'])!=expected for r in faults):reasons.append('wrong_expected_fault')
    if any(int(r[f'pwm_{w}_control']) or float(r[f'target_{w}_m_s']) for r in faults for w in 'ABCD'):reasons.append('fault_output_not_zero')
    zero_modes={}
    if faults:
        tail=[r for r in faults if int(r['mcu_time_unwrapped_us'])>=int(faults[-1]['mcu_time_unwrapped_us'])-90000]
        definition=json.loads((d/'metric_definition.json').read_text(encoding='utf-8'))
        bands=definition.get('zero_speed_band_m_s',{})
        thresholds={w:bands.get(w) if bands.get(w) is not None else 0.0 for w in 'ABCD'}
        zero_modes={w:'locked_zero_band' if bands.get(w) is not None else 'exact_recorded_zero_unverified_band' for w in 'ABCD'}
        if len(tail)<10 or any(not math.isfinite(float(r[f'feedback_{w}_m_s'])) or abs(float(r[f'feedback_{w}_m_s']))>thresholds[w] for r in tail for w in 'ABCD'):reasons.append('terminal_feedback_not_in_zero_band')
    if len(faults)<100:reasons.append('less_than_1s_fault_output_observation')
    result={'reviewed_local':local_now(),'trial_id':p['trial_id'],'kind':kind,'passed':not reasons,
        'reasons':sorted(set(reasons)),'expected_fault_flags':expected,'fault_samples':len(faults),
        'normal_trial_validation':report,'formal_baseline_eligible':False,'zero_check_modes':zero_modes}
    save_json(d/'safety_validation.json',result);print(json.dumps(result,ensure_ascii=False));return result['passed']
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory');ap.add_argument('--kind',choices=['abort','heartbeat'],required=True);a=ap.parse_args()
    raise SystemExit(0 if review(a.directory,a.kind) else 2)
