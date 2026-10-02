"""Audit raw frames against CSV and the board-recorded trial phases."""
import argparse, csv, hashlib, json, pathlib
import numpy as np
from protocol import ClockTracker, Decoder, FIELDS, decode_sample
def validate(directory):
    directory=pathlib.Path(directory);meta=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    with (directory/'samples.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    decoder=Decoder();raw_samples=[decode_sample(p) for kind,p in decoder.feed((directory/'raw_rx.bin').read_bytes()) if kind==1]
    reasons=[];hash_bad=[]
    for name,expected in meta.get('hashes',{}).items():
        p=directory/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:hash_bad.append(name)
    if hash_bad:reasons.append('archived_hash_mismatch')
    identical=len(rows)==len(raw_samples)
    if identical:
        for csvrow,rawrow in zip(rows,raw_samples):
            for name in FIELDS:
                try:
                    same=float(csvrow[name])==rawrow[name] if isinstance(rawrow[name],float) else int(csvrow[name])==rawrow[name]
                except (ValueError,KeyError):same=False
                if not same:identical=False;break
            if not identical:break
    if not identical:reasons.append('raw_csv_mismatch')
    clock=ClockTracker();derived_match=True
    for r in rows:
        derived=clock.update(int(r['sequence']),int(r['mcu_time_us']))
        if any(str(r.get(k))!=str(v) for k,v in derived.items()):derived_match=False
    if not derived_match:reasons.append('derived_clock_or_sequence_mismatch')
    for a,b in zip(rows,rows[1:]):
        if int(a['segment'])==int(b['segment']):
            difference=(int(b['mcu_time_us'])-int(a['mcu_time_us']))&0xffffffff
            if int(b['sequence_delta'])==1 and difference!=int(b['cycle_dt_us']):reasons.append('timestamp_period_inconsistent')
    for kind in ('bad_crc','bad_header','noise_between_frames'):
        if decoder.stats[kind]:reasons.append(kind)
    if decoder.stats['noise_before_first_frame']>1033:reasons.append('excessive_nonframing_prefix')
    trial=meta.get('actual_plan');run_id=meta.get('run_id')
    selected=[r for r in rows if int(r['run_id'])==run_id and int(r['state']) in (2,3) and int(r['stage']) in (0,1,2)] if trial else rows
    if not selected:reasons.append('no_samples')
    stages={str(s):sum(int(r['stage'])==s for r in selected) for s in (0,1,2)}
    missing=sum(max(0,int(r['sequence_delta'])-1) for r in selected[1:])
    duplicates=sum(r['clock_event']=='duplicate' for r in selected)
    segments=sorted({int(r['segment']) for r in selected})
    if missing:reasons.append('missing_sequence')
    if duplicates:reasons.append('duplicate_sequence')
    if len(segments)>1 or any(r['clock_event']=='restart_or_ambiguous_gap' for r in selected):reasons.append('mcu_restart_or_ambiguous_gap')
    if any(int(r['fault_flags']) for r in selected):reasons.append('fault_flags_present')
    drops=[int(r['queue_drop_count']) for r in selected]
    if drops and max(drops)>min(drops):reasons.append('fifo_drops_during_record')
    if drops and trial and max(drops)>0:reasons.append('cumulative_fifo_drops_nonzero')
    dt=np.array([int(r['cycle_dt_us']) for r in selected],dtype=float)
    if len(dt) and (np.any(dt<=0) or np.any(dt>15000)):reasons.append('invalid_or_missed_period')
    feedback_jump_count={}
    for w in 'ABCD':
        values=np.array([float(r[f'feedback_{w}_m_s']) for r in selected])
        feedback_jump_count[w]=int(np.count_nonzero(np.abs(np.diff(values))>.2))
        if len(values) and not np.all(np.isfinite(values)):reasons.append('nonfinite_feedback_'+w)
    if trial:
        expected={str(s):trial[k]//10 for s,k in enumerate(['pre_ms','hold_ms','post_ms'])}
        if stages!=expected:reasons.append('phase_sample_count_mismatch')
        order=[int(r['stage']) for r in selected]
        if order!=sorted(order):reasons.append('phase_order_mismatch')
        if not meta.get('complete'):reasons.append('not_normal_complete')
        complete=[r for r in rows if int(r['run_id'])==run_id and int(r['state'])==4 and int(r['stage'])==255]
        if not complete:reasons.append('missing_complete_sample')
        for r in selected:
            expected_speed=trial['step_mm_s']/1000 if int(r['stage'])==1 else 0
            if abs(float(r['cmd_v_m_s'])-expected_speed)>1e-6 or abs(float(r['cmd_w_rad_s']))>1e-7:
                reasons.append('body_command_mismatch');break
            if any(abs(float(r[f'target_{w}_m_s'])-expected_speed)>1e-6 for w in 'ABCD'):
                reasons.append('wheel_target_mismatch');break
        build=meta.get('download_record',{});config=meta.get('board_config',{})
        if not build.get('board_identity_verified') or build.get('firmware_build_id')!=config.get('firmware_build_id'):reasons.append('firmware_identity_evidence_missing')
        if not trial.get('precheck'):
            hardware=meta.get('hardware_manifest',{});required=['wheel_mapping_verified','forward_direction_verified','counts_per_wheel_revolution_verified','wheel_diameter_measured','platform_correspondence_recorded']
            if not all(hardware.get('verification',{}).get(k) is True for k in required):reasons.append('hardware_verification_incomplete')
    elif meta.get('mode')=='listen':
        if any(int(r['state']) not in (0,4) or any(int(r[f'pwm_{w}_control']) or float(r[f'target_{w}_m_s']) for w in 'ABCD') for r in selected):reasons.append('static_zero_drive_violation')
    cycle_stats={k:float(v) for k,v in zip(['min_us','median_us','mean_us','p95_us','max_us'],[np.min(dt),np.median(dt),np.mean(dt),np.percentile(dt,95),np.max(dt)])} if len(dt) else {}
    report={'valid':not reasons,'reasons':sorted(set(reasons)),'mode':meta.get('mode'),'raw_csv_match':identical,'hash_mismatch_files':hash_bad,
        'expected_samples':sum(trial[k]//10 for k in ['pre_ms','hold_ms','post_ms']) if trial else None,'actual_samples':len(selected),
        'all_csv_samples':len(rows),'stage_counts':stages,'sequence_missing':missing,'duplicates':duplicates,'segments':segments,
        'decoder_stats':dict(decoder.stats),'trailing_incomplete_bytes':len(decoder.buffer),'queue_drop_max':max(drops) if drops else None,
        'cycle_distribution':cycle_stats,'feedback_jump_threshold_m_s_per_sample':.2,'feedback_jump_counts':feedback_jump_count}
    (directory/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('trial_dir');a=ap.parse_args();print(json.dumps(validate(a.trial_dir),ensure_ascii=False,indent=2))
