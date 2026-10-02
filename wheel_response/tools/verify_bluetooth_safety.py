"""Zero-drive ARMED checks: owner heartbeat timeout and USB backup ABORT. Never START."""
import argparse,csv,json,time
from wheel_response_cli import Session,output_dir,local_now,save_json
from protocol import Decoder,OP

def check(bt_port,usb_port):
    root=output_dir('ZERO_ARMED_SAFETY','wheel_response/evidence/bluetooth')
    paths={k:root/k for k in ('spp','usb')}
    for p in paths.values():p.mkdir()
    result={'motion_start_sent':False,'checks':[],'passed':False}
    with Session(usb_port,paths['usb'],{'mode':'zero_armed_safety','complete':False,'start_local':local_now()}) as usb, \
         Session(bt_port,paths['spp'],{'mode':'zero_armed_safety','complete':False,'start_local':local_now()}) as bt:
        bt.inspect()
        for rid,kind,expected in [(65000,'wrong_link_heartbeats_do_not_prevent_owner_timeout',1),(65001,'usb_backup_abort',2)]:
            bt.hb_run=rid;bt.next_hb=time.monotonic()+.1
            bt.send('ARM',rid,50,1000,1000,1000);bt.send('HEARTBEAT',rid,wait=False)
            end=time.monotonic()+.35
            while time.monotonic()<end:bt.pump();usb.pump()
            before=bt.last_sample
            if not before or before['state']!=1:raise RuntimeError('Expected zero-drive ARMED state.')
            bt.hb_run=None
            if expected==1:usb.hb_run=rid;usb.next_hb=time.monotonic()
            else:usb.send('ABORT',rid)
            deadline=time.monotonic()+1.5;fault=None
            while time.monotonic()<deadline:
                bt.pump();usb.pump()
                row=bt.last_sample
                if row and row['run_id']==rid and row['state']==5:
                    if row['fault_flags']!=expected:raise RuntimeError('Unexpected fault; refusing automatic clear.')
                    fault=dict(row);break
            usb.hb_run=None
            if fault is None:raise RuntimeError('Expected fault did not occur.')
            end=time.monotonic()+.3
            while time.monotonic()<end:bt.pump();usb.pump()
            result['checks'].append({'kind':kind,'expected_fault_flags':expected,'observed_fault_flags':fault['fault_flags'],
                                    'run_id':rid,'first_fault_sample':fault,'passed':True})
            # Only the exact fault intentionally caused above is cleared; no START follows.
            bt.send('CLEAR_FAULT');bt.event('clear_exact_intentional_zero_armed_fault',flags=expected)
        bt.metadata['complete']=usb.metadata['complete']=True
    traces=[];all_zero=True;starts=0
    for channel,p in paths.items():
        decoder=Decoder();decoder.feed((p/'raw_rx.bin').read_bytes())
        with (p/'samples.csv').open() as f:rows=list(csv.DictReader(f))
        all_zero=all_zero and all(float(r[k])==0 for r in rows for w in 'ABCD' for k in (f'target_{w}_m_s',f'pwm_{w}_control',f'feedback_{w}_m_s'))
        starts+=sum(json.loads(line).get('opcode')=='START' for line in (p/'commands.jsonl').read_text(encoding='utf-8').splitlines())
        traces.append({'channel':channel,'samples':len(rows),'sequence_missing':sum(max(0,int(r['sequence_delta'])-1) for r in rows[1:]),'bad_crc':decoder.stats['bad_crc'],'bad_header':decoder.stats['bad_header']})
    result.update(traces=traces,all_targets_pwm_feedback_zero=all_zero,START_commands=starts,
                  passed=all_zero and starts==0 and all(not t['bad_crc'] and not t['bad_header'] and not t['sequence_missing'] for t in traces))
    save_json(root/'safety_validation.json',result);print(json.dumps({'passed':result['passed'],'all_zero':all_zero,'checks':[x['kind'] for x in result['checks']],'evidence':str(root)}))
    return result['passed']

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--spp-port',default='COM13');ap.add_argument('--usb-port',default='COM12');a=ap.parse_args()
    raise SystemExit(0 if check(a.spp_port,a.usb_port) else 2)
