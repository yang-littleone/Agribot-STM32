"""Record independent supplemental outcomes without changing formal baseline selection."""
import csv
import datetime
import json
import pathlib
import sys
import numpy as np
from plot_response import plot_trial

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def record(directory):
    d = pathlib.Path(directory).resolve()
    meta = read_json(d/'metadata.json')
    plan = meta['actual_plan']
    assert plan.get('supplemental') and plan['precheck'] and plan['condition'] == 'GROUND'
    quality = read_json(d/'validation.json')
    continuation = read_json(d/'continuation_review.json')
    with (d/'metrics.csv').open(encoding='utf-8-sig', newline='') as f:
        metrics = list(csv.DictReader(f))
    with (d/'samples.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f) if int(r['run_id']) == meta['run_id']]
    active = [r for r in rows if int(r['state']) in (2,3)]
    hold = [r for r in active if int(r['state']) == 2 and int(r['stage']) == 1]
    results = {}
    for metric in metrics:
        w = metric['wheel']
        t = np.array([(int(r['mcu_time_unwrapped_us'])-int(hold[0]['mcu_time_unwrapped_us']))/1e6 for r in hold])
        y = np.array([float(r[f'feedback_{w}_m_s']) for r in hold])
        target = float(metric['actual_target_m_s'])
        band = float(metric['band_m_s'])
        outside = np.abs(y-target) > band
        tail = t >= 3.0-1e-9
        tail_bad = np.flatnonzero(tail & outside)
        results[w] = {
            'satisfies_original_settling_criterion': bool(metric['settling_time_s']),
            'settling_time_s': float(metric['settling_time_s']) if metric['settling_time_s'] else None,
            'band_m_s': band,
            'tail_2s_samples': int(tail.sum()),
            'tail_2s_outside_samples': int(len(tail_bad)),
            'last_outside_hold_time_s': float(t[np.flatnonzero(outside)[-1]]) if outside.any() else None,
            'tail_min_m_s': float(y[tail].min()),
            'tail_max_m_s': float(y[tail].max()),
            'reason': metric['reason'],
        }
    qualified = quality['valid'] and continuation['passed'] and all(r['satisfies_original_settling_criterion'] for r in results.values())
    result = {
        'trial_id': meta['trial_id'], 'run_id': meta['run_id'],
        'recorded_local': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'data_directory': str(d), 'data_valid': quality['valid'],
        'continuation_stop_passed': continuation['passed'], 'all_four_qualified': qualified,
        'criterion': 'Original unsmoothed +/-5% band, continuous until HOLD end, >=1 s remaining observation.',
        'PI_changed': False, 'included_in_formal_baseline': False,
        'all_attempts_retained': True, 'wheels': results, 'metrics': metrics,
    }
    dest = ROOT/'evidence/ground_supplemental'
    dest.mkdir(exist_ok=True)
    (dest/(meta['trial_id']+'_report.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    reports = [read_json(p) for p in sorted(dest.glob('*_report.json'))]
    progress = {'attempts': len(reports), 'qualified': sum(r['all_four_qualified'] for r in reports), 'all_attempts_retained': True, 'formal_baseline_unchanged': True, 'reports': reports}
    (dest/'progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text = '# 独立落地补测记录\n\n原 PI 参数不变；沿用正式试验原始样本持续 ±5% 判据，进入误差带后必须保持到 5 秒 HOLD 结束，且至少有 1 秒剩余观察。全部补测独立保留，不替换原正式 n=5 结果。缺失调节时间不写成零。\n\n'
    text += '|试验|数据有效|四轮达标|A调节时间(s)|B调节时间(s)|C调节时间(s)|D调节时间(s)|\n|---|---|---|---:|---:|---:|---:|\n'
    for r in reports:
        times = [f"{r['wheels'][w]['settling_time_s']:.2f}" if r['wheels'][w]['settling_time_s'] is not None else '未满足' for w in 'ABCD']
        text += '|'+r['trial_id']+'|'+('是' if r['data_valid'] else '否')+'|'+('是' if r['all_four_qualified'] else '否')+'|'+'|'.join(times)+'|\n'
    text += '\n尾段越界次数、幅度及最后越界时间见各试验 JSON。各次均独立复位后启动；轮速记录不等于车辆地速。\n'
    (dest/'独立补测说明.md').write_text(text,encoding='utf-8')
    plot_trial(d,active,meta['trial_id'])
    p = ROOT/'evidence/ground_formal/progress.json'
    baseline = read_json(p)
    baseline.update(supplemental_completed=len(reports), supplemental_qualified=progress['qualified'], supplemental_latest_trial=meta['trial_id'])
    p.write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('metrics',)},ensure_ascii=False))

if __name__ == '__main__':
    for argument in sys.argv[1:]:
        record(argument)
