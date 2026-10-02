"""Audit a passive, operator-confirmed full-turn capture; sends no serial commands."""
import argparse, csv, json, pathlib
from validate_data import validate

def check(directory,wheel,turns):
    directory=pathlib.Path(directory)
    if turns<=0:raise ValueError('Positive complete turns are required.')
    meta=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    if meta.get('mode')!='listen' or not meta.get('complete'):raise ValueError('A completed passive capture is required.')
    rows=list(csv.DictReader((directory/'samples.csv').open(encoding='utf-8',newline='')))
    quality=validate(directory)
    events=[json.loads(line) for line in (directory/'commands.jsonl').read_text(encoding='utf-8').splitlines()]
    opcodes=[e['opcode'] for e in events if e['event']=='command_sent']
    net={w:sum(int(r[f'encoder_{w}_counts']) for r in rows) for w in 'ABCD'}
    absolute={w:sum(abs(int(r[f'encoder_{w}_counts'])) for r in rows) for w in 'ABCD'}
    nominal=60000
    measured=net[wheel]/turns
    result={'wheel':wheel,'turns':turns,'operator_confirmed':True,'counts_net':net,'counts_absolute':absolute,
        'counts_per_output_turn':measured,'source_nominal_counts_per_turn':nominal,
        'relative_difference_from_source':(measured-nominal)/nominal,
        'comparison_tolerance_fraction':.01,'comparison_tolerance_note':'One-turn marked manual check, 1% screening tolerance fixed before auditing B/C/D results; not an instrument precision claim.',
        'direction_and_mapping_match':net[wheel]>0 and all(net[w]==0 for w in 'ABCD' if w!=wheel),
        'no_motion_commands':all(op in ('HELLO','GET_CONFIG') for op in opcodes),'data_quality':quality,
        'method':'Net signed original control samples during a marked complete forward wheel/output-shaft turn; no second encoder reader.'}
    result['source_scale_consistent']=abs(result['relative_difference_from_source'])<=.01
    result['passed']=quality['valid'] and result['no_motion_commands'] and result['direction_and_mapping_match'] and result['source_scale_consistent']
    meta['manual_turn_confirmation']={'wheel':wheel,'turns':turns,'direction':'forward','operator_confirmed_exact_full_turn_and_stopped':True}
    (directory/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'calibration_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory');ap.add_argument('--wheel',choices=list('ABCD'),required=True)
    ap.add_argument('--turns',type=int,required=True);ap.add_argument('--operator-confirmed',action='store_true');args=ap.parse_args()
    if not args.operator_confirmed:ap.error('Exact complete turns and stop must be confirmed by the operator.')
    print(json.dumps(check(args.directory,args.wheel,args.turns),ensure_ascii=False,indent=2))
