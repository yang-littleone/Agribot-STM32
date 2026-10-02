"""Validate each real trial, compute fixed metrics, then summarize per wheel."""
import argparse, collections, csv, json, pathlib
import numpy as np
from metrics import wheel_metrics
from validate_data import validate
from plot_response import plot_trial, plot_repeats
def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def analyze(root):
    root=pathlib.Path(root);all_metrics=[];groups=collections.defaultdict(list)
    for metadata in sorted(root.glob('*/metadata.json')):
        directory=metadata.parent;meta=json.loads(metadata.read_text(encoding='utf-8'));plan=meta.get('actual_plan')
        if not plan:continue
        report=validate(directory)
        with (directory/'samples.csv').open(encoding='utf-8',newline='') as f:rows=[r for r in csv.DictReader(f) if int(r['run_id'])==plan['run_id'] and int(r['state']) in (2,3)]
        definition=json.loads((directory/'metric_definition.json').read_text(encoding='utf-8'))
        metrics=[]
        for w in 'ABCD':
            result=wheel_metrics(rows,w,definition,plan)
            result.update(trial_id=plan['trial_id'],condition=plan['condition'],planned_speed_m_s=plan['step_mm_s']/1000,
                          valid_data=report['valid'],precheck=bool(plan.get('precheck')),validation_reasons=';'.join(report['reasons']))
            metrics.append(result);all_metrics.append(result)
        write_csv(directory/'metrics.csv',metrics);plot_trial(directory,rows,plan['trial_id'])
        if report['valid'] and not plan.get('precheck'):groups[(plan['condition'],plan['step_mm_s']/1000)].append((plan['trial_id'],rows))
    write_csv(root/'all_metrics.csv',all_metrics)
    summary=[]
    metric_names=['rise_time_s','settling_time_s','overshoot_pct','tail_mean_error_m_s','tail_mae_m_s','hold_rmse_m_s','tail_rmse_m_s','pwm_saturation_fraction','stop_time_s']
    grouped=collections.defaultdict(list)
    for row in all_metrics:
        if not row['precheck']:grouped[(row['condition'],row['planned_speed_m_s'],row['wheel'])].append(row)
    for condition in ('AIR','GROUND'):
        for speed in (.18,.4):
            for wheel in 'ABCD':
                rows=grouped[(condition,speed,wheel)];valid=[r for r in rows if r['valid_data']]
                s={'condition':condition,'speed_m_s':speed,'wheel':wheel,'planned_n':5,'recorded_n':len(rows),'valid_trial_n':len(valid)}
                for key in metric_names:
                    values=[r[key] for r in valid if r[key] is not None];s[key+'_n']=len(values)
                    s[key+'_mean']=float(np.mean(values)) if values else None;s[key+'_sample_sd']=float(np.std(values,ddof=1)) if len(values)>1 else None
                summary.append(s)
    root.mkdir(parents=True,exist_ok=True);write_csv(root/'summary_metrics.csv',summary)
    plot_repeats(root,groups)
    count=len({r['trial_id'] for r in all_metrics if not r['precheck']});validcount=len({r['trial_id'] for r in all_metrics if r['valid_data'] and not r['precheck']})
    wording=f'# 实测结果说明\n\n平台B正式试次已记录{count}次，当前通过数据校验{validcount}次，计划20次。\n'
    if not count:wording+='\n尚无正式实测数据，不生成响应性能结论。\n'
    else:wording+='\n结果仅描述登记硬件和条件下的底层四路增量式PI轮速响应。分轮统计，以试次为重复单位；未达到阈值或存在关键缺口的时间指标留空并附原因。编码器轮速不等于车辆地速。详细指标和异常见CSV及每次validation.json。\n'
    (root/'实测结果说明.md').write_text(wording,encoding='utf-8');print(json.dumps({'formal_recorded':count,'formal_valid':validcount,'output':str(root.resolve())},ensure_ascii=False))
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('data_root');a=ap.parse_args();analyze(a.data_root)
