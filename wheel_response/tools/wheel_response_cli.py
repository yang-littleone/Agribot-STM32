"""Single-session Windows WRS1 acquisition. Motion requires typed confirmation."""
import argparse, csv, datetime, hashlib, importlib.metadata, json, pathlib, platform, sys, time, queue, threading
import serial
from serial.tools import list_ports
from protocol import ACK, CSV_FIELDS, ClockTracker, Decoder, OP, command, decode_sample
from bluetooth_serial import resolve_spp, transport_for_port
ROOT=pathlib.Path(__file__).resolve().parents[2]
WR=ROOT/'wheel_response'
BASE='8655eb21f9537f84b5a66effc0fdb085a4993a99'
def local_now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def save_json(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def load_json(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalize_config(c):
    mapping={'fw':'firmware_build_id','base':'baseline_git_commit','cv':'configuration_version','kp':'kp_ABCD','ki':'ki_ABCD',
             'hb_ms':'heartbeat_timeout_ms','period_us':'nominal_period_us','ppr':'encoder_ppr','quadrature':'encoder_quadrature','reduction':'motor_reduction_ratio'}
    return {mapping.get(k,k):v for k,v in c.items()}
def verify_config(c):
    cfg=normalize_config(c)
    expected={'baseline_git_commit':BASE,'kp_ABCD':[800]*4,'ki_ABCD':[500]*4,'nominal_period_us':10000,'heartbeat_timeout_ms':500,
              'diameter_m':.065,'encoder_ppr':500,'encoder_quadrature':4,'motor_reduction_ratio':30,'pwm_limit':16700,
              'inverse_limit_m_s':1,'allowed_mm_s':[50,100,180,400]}
    bad=[k for k,v in expected.items() if cfg.get(k)!=v]
    if bad:raise RuntimeError('Board configuration differs from baseline: '+', '.join(bad))
    build=load_json(WR/'evidence/build_identity.json')
    if not build.get('success') or not build.get('images'):raise RuntimeError('No successful experiment build with image hashes.')
    identity=load_json(WR/'evidence/source_identity.json')
    if cfg['firmware_build_id']!=identity['firmware_build_id']:raise RuntimeError('Board build ID differs from source identity.')
    return cfg
class Session:
    def __init__(self,port,out,metadata):
        self.out=out;self.metadata=metadata;self.decoder=Decoder();self.clock=ClockTracker();self.next_seq=1
        self.last_sample=None;self.acknowledgements={};self.config=None;self.hb_run=None;self.next_hb=0
        self.integrity_problem=None
        self.transport=transport_for_port(port);metadata['transport']=self.transport
        self.s=serial.Serial(port=None,baudrate=115200,timeout=.02,write_timeout=.5 if self.transport=='bluetooth_spp' else .1)
        self.s.dtr=False;self.s.rts=False;self.s.port=port
        self.rx=(out/'raw_rx.bin').open('wb');self.tx=(out/'raw_tx.bin').open('wb')
        self.events=(out/'commands.jsonl').open('w',encoding='utf-8')
        self.csvfile=(out/'samples.csv').open('w',encoding='utf-8',newline='');self.csv=csv.DictWriter(self.csvfile,fieldnames=CSV_FIELDS);self.csv.writeheader()
        self.samples=0;self.opened=False
        save_json(out/'metadata.json',metadata)
    def __enter__(self):
        try:
            self.s.open();self.opened=True
            if sys.platform=='win32':
                try:self.s.set_buffer_size(rx_size=65536,tx_size=8192);self.metadata['windows_receive_buffer_requested_bytes']=65536
                except (AttributeError,serial.SerialException,OSError) as e:self.metadata['buffer_size_request_note']=str(e)
            self.event('connection_opened',port=self.s.port)
        except Exception:
            self.close();raise
        return self
    def event(self,kind,**values):
        self.events.write(json.dumps({'event':kind,'pc_monotonic_ns':time.monotonic_ns(),'local_time':local_now(),**values},ensure_ascii=False)+'\n');self.events.flush()
    def send(self,opcode,run_id=0,step=0,pre=0,hold=0,post=0,wait=True):
        seq=self.next_seq;self.next_seq=(seq+1)&0xffffffff
        data=command(seq,opcode,run_id,step,pre,hold,post)
        try:
            n=self.s.write(data);self.tx.write(data[:n]);self.tx.flush()
            self.event('command_sent',command_sequence=seq,opcode=opcode,run_id=run_id,step_mm_s=step,pre_ms=pre,hold_ms=hold,post_ms=post,bytes_confirmed=n)
            if n!=len(data):raise RuntimeError('Incomplete command write.')
        except Exception as e:
            self.event('command_send_failed',command_sequence=seq,opcode=opcode,error=str(e),partial_bytes_if_exception='unknown');raise
        if not wait:return seq
        end=time.monotonic()+2
        while time.monotonic()<end:
            self.pump()
            if seq in self.acknowledgements:
                ack=self.acknowledgements.pop(seq)
                if ack[1]!=OP[opcode] or ack[2]!=0:raise RuntimeError(f'{opcode} rejected: {ack}')
                return ack
        raise TimeoutError(f'No matching {opcode} acknowledgement.')
    def pump(self):
        if self.hb_run is not None and time.monotonic()>=self.next_hb:
            self.next_hb=time.monotonic()+.1;self.send('HEARTBEAT',self.hb_run,wait=False)
        data=self.s.read(max(1,min(self.s.in_waiting,4096)))
        if not data:return
        self.rx.write(data);self.rx.flush();pc=time.monotonic_ns()
        active_before=self.hb_run is not None and self.last_sample and self.last_sample['state'] in (1,2,3)
        crc_before=self.decoder.stats['bad_crc'];noise_before=self.decoder.stats['noise_between_frames']
        decoded=self.decoder.feed(data)
        if active_before and (self.decoder.stats['bad_crc']>crc_before or self.decoder.stats['noise_between_frames']>noise_before):
            self.integrity_problem='CRC_or_nonframing_bytes_during_active_run'
        for kind,payload in decoded:
            if kind==1:
                row=decode_sample(payload);row.update(self.clock.update(row['sequence'],row['mcu_time_us']));row['pc_receive_monotonic_ns']=pc
                if active_before and (row['sequence_delta']!=1 or row['clock_event']=='restart_or_ambiguous_gap'):
                    self.integrity_problem='sequence_gap_or_restart_during_active_run'
                self.csv.writerow(row);self.last_sample=row;self.samples+=1
                if self.samples%100==0:self.csvfile.flush()
            elif kind==17:
                ack=ACK.unpack(payload);self.acknowledgements[ack[0]]=ack;self.event('ack',fields=list(ack))
            elif kind==18:
                self.config=json.loads(payload.decode('utf-8'));(self.out/'board_config_raw.json').write_bytes(payload)
                save_json(self.out/'board_config.json',normalize_config(self.config))
            else:self.event('unexpected_frame',frame_type=kind,payload_hex=payload.hex())
    def inspect(self):
        ack=self.send('HELLO')
        if ack[3] not in (0,4,5):raise RuntimeError('Board is active; inspect will not arm or restart it.')
        self.send('GET_CONFIG');end=time.monotonic()+3
        while self.config is None and time.monotonic()<end:self.pump()
        if self.config is None:raise TimeoutError('Board configuration not received.')
        cfg=verify_config(self.config)
        expected=1 if self.transport=='bluetooth_spp' else 0
        if cfg.get('configuration_version',1)>=2 and cfg.get('link')!=expected:
            raise RuntimeError('Stopped-session HELLO did not select the requested transport.')
        if self.transport=='bluetooth_spp' and (cfg.get('configuration_version',1)<2 or cfg.get('btbaud',0)<115200):
            raise RuntimeError('Bluetooth UART is not configured for full-rate 100 Hz capture.')
        return cfg,ack
    def safe_abort(self):
        self.hb_run=None
        try:self.send('ABORT',int(self.last_sample['run_id']) if self.last_sample else 0)
        except Exception as e:
            self.metadata['abort_error']=str(e)
            try:self.event('abort_delivery_unconfirmed',error=str(e))
            except OSError:pass
            return False
        try:self.event('abort_acknowledged')
        except OSError:pass
        return True
    def close(self):
        if self.opened:self.s.close();self.opened=False
        for f in [self.rx,self.tx,self.events,self.csvfile]:
            if not f.closed:f.close()
        self.metadata.update(end_local=local_now(),decoder_stats=dict(self.decoder.stats),trailing_bytes=len(self.decoder.buffer),samples_received=self.samples)
        self.metadata['hashes']={p.name:sha(p) for p in self.out.iterdir() if p.is_file() and p.name not in ('metadata.json','validation.json','metrics.csv')}
        save_json(self.out/'metadata.json',self.metadata)
    def __exit__(self,kind,value,tb):
        if kind:self.metadata.update(error=str(value),complete=False)
        self.close()
def output_dir(label,root):
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');p=pathlib.Path(root)/(label+'_'+stamp);p.mkdir(parents=True,exist_ok=False);return p
def versions():
    return {'python':sys.version,'platform':platform.platform(),'packages':{n:importlib.metadata.version(n) for n in ['pyserial','numpy','matplotlib']}}
def register_update(trial_id,**changes):
    path=WR/'records/trial_register.csv'
    with path.open(encoding='utf-8',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    row=next((r for r in rows if r['trial_id']==trial_id),None)
    if row is None:raise RuntimeError('Trial is not registered.')
    row.update({k:str(v) for k,v in changes.items()})
    with path.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def get_registered(trial_id):
    with (WR/'records/trial_register.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    row=next((r for r in rows if r['trial_id']==trial_id),None)
    if row is None or row['status']!='planned':raise RuntimeError('Only an unused planned trial can run. Register a separate retest ID for a repeat.')
    return row

def read_confirmation_while_pumping(session,prompt):
    """The console may wait arbitrarily long; UART acquisition must keep draining.
    Only the main thread touches the serial port, decoder and evidence files.
    """
    answer=queue.Queue(maxsize=1)
    def reader():
        try:answer.put((True,input(prompt)))
        except BaseException as error:answer.put((False,error))
    threading.Thread(target=reader,daemon=True,name='console-confirmation').start()
    while answer.empty():session.pump()
    ok,value=answer.get()
    if not ok:raise value
    return value
def acquire(args):
    trial=None;hardware=load_json(args.hardware);meta={'mode':args.mode,'robot_id':'B','port':args.port,'start_local':local_now(),'timezone':'Asia/Shanghai','software':versions(),
        'complete':False,'sampling_order':'timestamp;encoder_once;nominal_velocity;stage_target;original_inverse_PI_PWM;snapshot;nonblocking_fifo',
        'time_resolution_us':1000,'raw_data_processing':'none','hardware_manifest':hardware,'operator':getattr(args,'operator',None)}
    if args.mode=='run':
        plan=load_json(args.plan);trial=next((p for p in plan['trials'] if p['trial_id']==args.trial),None)
        if trial is None:raise RuntimeError('Unknown trial in plan.')
        get_registered(args.trial)
        if trial['condition']=='GROUND':
            setup=hardware.get('planned_ground_setup',{})
            if setup.get('vehicle_still_raised') is not False or setup.get('physical_ready_confirmed') is not True:
                raise RuntimeError('GROUND placement is not confirmed. Record the actual ground setup before START.')
        if not args.operator:raise RuntimeError('Supply actual operator with --operator.')
        if not trial.get('precheck'):
            required=['wheel_mapping_verified','forward_direction_verified','counts_per_wheel_revolution_verified','wheel_diameter_measured','platform_correspondence_recorded']
            if not all(hardware.get('verification',{}).get(k) is True for k in required):raise RuntimeError('Hardware verification is incomplete for a formal trial.')
            metric=load_json(WR/'config/metric_definition.json')
            if not metric.get('locked_before_formal_measurement') or any(metric.get('verified_quantization_m_s',{}).get(w) is None for w in 'ABCD'):raise RuntimeError('Lock verified metric bands before formal measurements.')
        if args.heartbeat_loss_at is not None and not trial.get('precheck'):raise RuntimeError('Intentional heartbeat loss is allowed only for a registered precheck.')
        abort_hold_ms=getattr(args,'abort_hold_ms',None)
        if abort_hold_ms is not None:
            if not trial.get('precheck') or not 0<abort_hold_ms<trial['hold_ms']:
                raise RuntimeError('Timed ABORT requires a precheck and a time inside its HOLD stage.')
        flash=load_json(WR/'evidence/download_record.json')
        if not flash.get('board_identity_verified'):raise RuntimeError('Actual download and board identity must be verified first.')
        meta.update(trial_id=args.trial,run_id=trial['run_id'],condition=trial['condition'],repeat_index=trial.get('repeat_index'),actual_plan=trial,baseline_git_commit=BASE,download_record=flash)
    label=args.trial if trial else args.mode.upper()
    out=output_dir(label,args.output or (WR/'data' if trial else WR/'evidence/static_checks'))
    if trial:
        save_json(out/'experiment_plan.json',plan);save_json(out/'hardware_manifest.json',hardware)
        save_json(out/'metric_definition.json',load_json(WR/'config/metric_definition.json'))
        save_json(out/'source_identity.json',load_json(WR/'evidence/source_identity.json'))
        save_json(out/'build_identity.json',load_json(WR/'evidence/build_identity.json'))
    print('Evidence directory:',out,flush=True)
    with Session(args.port,out,meta) as session:
        config,ack=session.inspect();meta['board_config']=config;meta['initial_state']=ack[3]
        if args.mode=='inspect':
            for _ in range(10):session.pump()
            meta['complete']=True;print(json.dumps({'state':ack[3],'config':config},ensure_ascii=False));return
        if args.mode=='listen':
            if ack[3] not in (0,4):raise RuntimeError('Zero-drive listen requires IDLE or COMPLETE.')
            end=time.monotonic()+args.duration
            if getattr(args,'end_on_key',False):print('Passive recording ready. q ends capture; no ARM/START is sent.',flush=True)
            while time.monotonic()<end:
                session.pump()
                if getattr(args,'end_on_key',False) and sys.platform=='win32':
                    import msvcrt
                    if msvcrt.kbhit() and msvcrt.getwch().lower()=='q':
                        session.event('passive_capture_operator_end');meta['capture_end_reason']='operator_key_q';break
            if getattr(args,'end_config',False):
                session.config=None;session.send('GET_CONFIG');deadline=time.monotonic()+3
                while session.config is None and time.monotonic()<deadline:session.pump()
                if session.config is None:raise TimeoutError('Missing end-of-capture configuration snapshot.')
                meta['board_config_end']=normalize_config(session.config)
                save_json(out/'board_config_end.json',meta['board_config_end'])
            meta['complete']=True;return
        if ack[3] not in (0,4):raise RuntimeError('Clear the cause of FAULT before running.')
        expected='START '+args.trial
        print(f"One trial: {trial['condition']}, {trial['step_mm_s']/1000:g} m/s; {trial['pre_ms']}/{trial['hold_ms']}/{trial['post_ms']} ms.",flush=True)
        if read_confirmation_while_pumping(session,f'Confirm physical readiness by typing {expected}: ').strip()!=expected:
            session.event('start_cancelled');return
        register_update(args.trial,status='started',start_local=local_now(),data_directory=str(out))
        meta['actual_order']=sum(1 for _ in (WR/'data').glob('*/metadata.json')) if (WR/'data').exists() else 1
        motion_possible=True
        try:
            session.hb_run=trial['run_id'];session.next_hb=time.monotonic()+.1
            session.send('ARM',trial['run_id'],trial['step_mm_s'],trial['pre_ms'],trial['hold_ms'],trial['post_ms'])
            session.send('HEARTBEAT',trial['run_id'],wait=False);session.send('START',trial['run_id'])
            started=time.monotonic();limit=(trial['pre_ms']+trial['hold_ms']+trial['post_ms'])/1000+8
            loss=False;early_stop=False;hold_started_us=None;abort_sent=False
            print('q or Ctrl+C: ABORT; s: enter normal POST. No next trial will start automatically.',flush=True)
            while time.monotonic()-started<limit:
                if args.heartbeat_loss_at is not None and not loss and time.monotonic()-started>=args.heartbeat_loss_at:
                    loss=True;session.hb_run=None;session.event('intentional_heartbeat_loss',seconds_from_pc_start=time.monotonic()-started)
                session.pump()
                if session.integrity_problem:raise RuntimeError(session.integrity_problem)
                row=session.last_sample
                if abort_hold_ms is not None and row and row['run_id']==trial['run_id'] and row['stage']==1:
                    if hold_started_us is None:hold_started_us=row['mcu_time_unwrapped_us']
                    if not abort_sent and row['mcu_time_unwrapped_us']-hold_started_us>=abort_hold_ms*1000:
                        session.event('intentional_abort_trigger',hold_elapsed_us=row['mcu_time_unwrapped_us']-hold_started_us,trigger_sequence=row['sequence'])
                        session.hb_run=None;session.send('ABORT',trial['run_id']);abort_sent=True
                        meta['intentional_abort']=True
                if sys.platform=='win32':
                    import msvcrt
                    if msvcrt.kbhit():
                        key=msvcrt.getwch().lower()
                        if key in ('q','\x03'):raise KeyboardInterrupt()
                        if key=='s':session.send('STOP',trial['run_id']);early_stop=True;session.event('human_stop')
                row=session.last_sample
                if row and row['run_id']==trial['run_id'] and row['state'] in (4,5):
                    meta.update(complete=row['state']==4 and not early_stop,final_state=row['state'],human_stop=early_stop,fault_flags=row['fault_flags'])
                    session.hb_run=None;motion_possible=False
                    # Drain trailing samples so the last POST and COMPLETE are archived.
                    drain=time.monotonic()+(1.3 if row['state']==5 else .3)
                    while time.monotonic()<drain:session.pump()
                    break
            else:raise TimeoutError('Single trial did not reach a terminal state.')
        except BaseException as e:
            meta.update(complete=False,error=type(e).__name__+': '+str(e))
            if motion_possible:meta['abort_acknowledged']=session.safe_abort()
            try:session.event('run_exception',reason=meta['error'])
            except OSError:pass
            register_update(args.trial,status='interrupted',end_local=local_now(),include_in_baseline='False',reason=meta['error'])
            raise
        register_update(args.trial,status='completed' if meta['complete'] else 'interrupted',end_local=local_now(),include_in_baseline='pending_validation',reason='human_stop_or_fault' if not meta['complete'] else '')
    if trial:
        from validate_data import validate
        report=validate(out);register_update(args.trial,status='valid' if report['valid'] else 'limited',include_in_baseline=report['valid'] and not trial.get('precheck'),reason=';'.join(report['reasons']) or ('precheck_only' if trial.get('precheck') else ''))
def emergency(args):
    out=output_dir('ABORT',WR/'evidence/static_checks')
    meta={'mode':'abort','start_local':local_now(),'port':args.port,'complete':False}
    with Session(args.port,out,meta) as session:
        ack=session.send('ABORT');meta.update(complete=True,ack=list(ack))
    print('ABORT acknowledged; evidence:',out)
def clear_fault(args):
    out=output_dir('CLEAR_FAULT',WR/'evidence/static_checks')
    meta={'mode':'clear-fault','start_local':local_now(),'port':args.port,'complete':False,'reason':args.reason}
    with Session(args.port,out,meta) as session:
        config,ack=session.inspect()
        if ack[3]!=5:raise RuntimeError('Board is not in FAULT.')
        print('Current fault flags:',ack[-1],'; recorded cause resolution:',args.reason,flush=True)
        if read_confirmation_while_pumping(session,'After resolving the cause, type CLEAR_FAULT: ').strip()!='CLEAR_FAULT':
            session.event('clear_fault_cancelled');return
        ack=session.send('CLEAR_FAULT');meta.update(complete=True,ack=list(ack),board_config=config)
        session.event('fault_cause_resolution',reason=args.reason)
    print('Fault cleared to IDLE. No ARM/START sent. Evidence:',out)

def configure_bluetooth(args):
    if transport_for_port(args.port)!='usb_serial':raise RuntimeError('Module configuration requires the USB maintenance link.')
    out=output_dir('BT_SETUP',WR/'evidence/bluetooth')
    meta={'mode':'bluetooth_setup','port':args.port,'start_local':local_now(),'complete':False,'motion_commands_sent':False,
          'telemetry_pause_note':'Zero-drive module setup may pause diagnostic telemetry; not a trial or performance record.'}
    with Session(args.port,out,meta) as session:
        session.inspect();session.send('BT_SETUP')
        end=time.monotonic()+8
        while time.monotonic()<end:session.pump()
        session.config=None;cfg,ack=session.inspect()
        meta.update(complete=cfg.get('btat')==1 and cfg.get('btbaud')==115200,board_config=cfg,final_state=ack[3])
    print(json.dumps({'verified':meta['complete'],'config':cfg,'evidence':str(out)},ensure_ascii=False))
    if not meta['complete']:raise RuntimeError('JDY-33 AT configuration was not verified; keep motion tests stopped.')
def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='mode',required=True)
    sub.add_parser('list-ports',help='Enumerate ports; sends nothing.')
    for mode in ('inspect','listen','run','abort'):
        p=sub.add_parser(mode);p.add_argument('--port',required=True)
        p.add_argument('--bluetooth-name',default='WHEELTEC',help='With --port auto, resolve this paired classic SPP device; never chooses BLE or an incoming COM port.')
        if mode!='abort':
            p.add_argument('--hardware',default=str(WR/'config/hardware_manifest.json'));p.add_argument('--output')
        if mode=='listen':
            p.add_argument('--duration',type=float,default=30)
            p.add_argument('--end-config',action='store_true',help='Capture final UART diagnostics while still on the same stopped connection.')
            p.add_argument('--end-on-key',action='store_true',help='Windows passive recording: q ends capture normally; never arms the board.')
        if mode=='run':
            p.add_argument('--trial',required=True);p.add_argument('--plan',default=str(WR/'config/experiment_plan.json'));p.add_argument('--operator',required=True)
            p.add_argument('--heartbeat-loss-at',type=float,help='Precheck only: intentionally stop heartbeats after this many PC seconds.')
            p.add_argument('--abort-hold-ms',type=int,help='Precheck only: send ABORT once this many board-clock milliseconds into HOLD.')
    p=sub.add_parser('clear-fault');p.add_argument('--port',required=True);p.add_argument('--reason',required=True)
    p.add_argument('--bluetooth-name',default='WHEELTEC')
    p=sub.add_parser('bluetooth-port');p.add_argument('--bluetooth-name',default='WHEELTEC')
    p=sub.add_parser('configure-bluetooth');p.add_argument('--port',default='COM12');p.add_argument('--bluetooth-name',default='WHEELTEC')
    p=sub.add_parser('validate');p.add_argument('trial_dir')
    p=sub.add_parser('analyze');p.add_argument('data_root')
    args=ap.parse_args()
    try:
        if hasattr(args,'port') and args.port.casefold()=='auto':args.port=resolve_spp(args.bluetooth_name)
        if args.mode=='bluetooth-port':
            print(json.dumps({'device_name':args.bluetooth_name,'outgoing_spp_port':resolve_spp(args.bluetooth_name)}));return
        if args.mode=='list-ports':
            for p in list_ports.comports():print(p.device,p.description,p.hwid)
        elif args.mode=='abort':emergency(args)
        elif args.mode=='clear-fault':clear_fault(args)
        elif args.mode=='configure-bluetooth':configure_bluetooth(args)
        elif args.mode=='validate':
            from validate_data import validate
            print(json.dumps(validate(pathlib.Path(args.trial_dir)),ensure_ascii=False,indent=2))
        elif args.mode=='analyze':
            from analyze_response import analyze
            analyze(pathlib.Path(args.data_root))
        else:acquire(args)
    except (Exception,KeyboardInterrupt) as e:
        print(f'{type(e).__name__}: {e}',file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':main()
