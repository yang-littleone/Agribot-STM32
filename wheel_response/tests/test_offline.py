"""Synthetic fixtures stay in tests. These are not vehicle results."""
import pathlib, sys, subprocess, shutil, unittest, csv, hashlib, json, tempfile, time
import numpy as np
import io
import threading
from unittest import mock
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'wheel_response/tools'))
from protocol import *
from metrics import wheel_metrics
from validate_data import validate
from bluetooth_serial import outgoing_ports
from wheel_response_cli import Session,read_confirmation_while_pumping
class LiveIntegrityTests(unittest.TestCase):
    def test_confirmation_wait_keeps_draining_serial(self):
        ready=threading.Event();pumps=[]
        def pump():
            pumps.append(1)
            if len(pumps)>=10:ready.set()
        def answer(prompt):
            self.assertTrue(ready.wait(1));return 'START test'
        with mock.patch('builtins.input',answer):
            self.assertEqual(read_confirmation_while_pumping(SimpleNamespace(pump=pump),'prompt'),'START test')
        self.assertGreaterEqual(len(pumps),10)
    def check_stream(self,state):
        s=Session.__new__(Session);s.hb_run=7 if state==2 else None;s.next_hb=float('inf');s.last_sample={'state':state}
        s.integrity_problem=None;s.decoder=Decoder();s.clock=ClockTracker();s.clock.update(10,100000)
        def sample(seq):return frame(1,TELEMETRY.pack(seq,seq*10000,10000,7,state,1,.18,0,*([.18]*4),*([.18]*4),*([1000]*4),*([500]*4),65535,0,0,0,65535))
        s.decoder.feed(sample(10));bad=bytearray(frame(17,ACK.pack(1,1,0,0,255,7,0,0)));bad[-1]^=1
        data=bytes(bad)+sample(11);s.s=SimpleNamespace(in_waiting=len(data),read=lambda n:data)
        s.rx=io.BytesIO();s.csvfile=io.StringIO();s.csv=csv.DictWriter(s.csvfile,fieldnames=CSV_FIELDS);s.samples=0
        s.pump();return s
    def test_corrupt_live_frame_marks_run_for_abort(self):
        self.assertIsNotNone(self.check_stream(2).integrity_problem)
    def test_idle_corruption_is_preserved_without_motion_session_abort(self):
        self.assertIsNone(self.check_stream(0).integrity_problem)
class BatteryTests(unittest.TestCase):
    def test_nonblocking_adc_estimate_failure_staleness_and_wrap(self):
        with tempfile.TemporaryDirectory(prefix='synthetic_bat_',dir=ROOT/'wheel_response/tests') as folder:
            exe=pathlib.Path(folder)/'test.exe'
            subprocess.run([shutil.which('gcc'),'-std=c99','-Wall','-Wextra','-I'+str(ROOT/'wheel_response/tests/battery_stub'),
                            '-I'+str(ROOT/'System'),str(ROOT/'wheel_response/tests/synthetic_battery_test.c'),str(ROOT/'System/WheelResponseBattery.c'),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
class BluetoothPortTests(unittest.TestCase):
    def test_compiled_bootstrap_connected_9600_and_no_false_verification(self):
        with tempfile.TemporaryDirectory(prefix='synthetic_bt_',dir=ROOT/'wheel_response/tests') as folder:
            exe=pathlib.Path(folder)/'test.exe'
            subprocess.run([shutil.which('gcc'),'-std=c99','-Wall','-Wextra','-I'+str(ROOT/'wheel_response/tests/bluetooth_stub'),
                            '-I'+str(ROOT/'System'),str(ROOT/'wheel_response/tests/synthetic_bluetooth_test.c'),str(ROOT/'System/Bluetooth.c'),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
    def test_selects_named_outgoing_spp_not_ble_incoming_or_other_devices(self):
        devices=[{'FriendlyName':'WHEELTEC','InstanceId':'BTHENUM\\DEV_7AA71A040038\\x'},
                 {'FriendlyName':'WHEELTEC-IOS','InstanceId':'BTHLE\\DEV_7AA71A050038\\x'}]
        ports=[SimpleNamespace(device='COM13',hwid='BTHENUM\\SPP_LOCALMFG&0002\\7AA71A040038_C000'),
               SimpleNamespace(device='COM14',hwid='BTHENUM\\SPP_LOCALMFG&0000\\000000000000'),
               SimpleNamespace(device='COM8',hwid='BTHENUM\\SPP_LOCALMFG&0002\\41AA00F3347D_C000')]
        self.assertEqual(outgoing_ports('wheeltec',devices,ports),['COM13'])
class ProtocolTests(unittest.TestCase):
    def test_crc_and_sizes(self):
        self.assertEqual(crc16(b'123456789'),0x29b1);self.assertEqual(TELEMETRY.size,84)
    def test_fragmentation_and_resynchronization(self):
        good=frame(17,ACK.pack(8,1,0,0,255,0,0,0));bad=bytearray(good);bad[-1]^=1
        illegal=HEADER.pack(MAGIC,1,1,1025)
        stream=b'noise'+bytes(bad)+illegal+good+good+good[:7]
        parser=Decoder();out=[]
        for i in range(0,len(stream),3):out.extend(parser.feed(stream[i:i+3]))
        self.assertEqual(len(out),2);self.assertGreater(parser.stats['bad_crc'],0);self.assertGreater(parser.stats['bad_header'],0);self.assertEqual(bytes(parser.buffer),good[:7])
    def test_clock_missing_wrap_restart(self):
        t=ClockTracker();t.update(0xfffffffe,0xffffd8f0);r=t.update(0xffffffff,0xffffff00);self.assertEqual(r['sequence_delta'],1)
        r=t.update(0,9744);self.assertEqual(r['segment'],0);self.assertEqual(r['clock_event'],'time_wrap')
        r=t.update(2,29744);self.assertEqual(r['sequence_delta'],2)
        r=t.update(0,1000);self.assertEqual(r['segment'],1)
    def test_initial_partial_frame_distinguished_from_interior_noise(self):
        good=frame(17,ACK.pack(8,1,0,0,255,0,0,0));parser=Decoder()
        parser.feed(good[12:]+good+b'noise'+good)
        self.assertEqual(parser.stats['noise_before_first_frame'],len(good[12:]))
        self.assertEqual(parser.stats['noise_between_frames'],5)
    def test_compiled_c_protocol_and_engine(self):
        gcc=shutil.which('gcc');self.assertIsNotNone(gcc,'Host GCC must be available for firmware tests.')
        exe=ROOT/'wheel_response/tests/synthetic_firmware_test.exe'
        subprocess.run([gcc,'-std=c99','-Wall','-Wextra','-I'+str(ROOT/'System'),str(ROOT/'wheel_response/tests/synthetic_firmware_test.c'),str(ROOT/'System/WheelResponseEngine.c'),str(ROOT/'System/WheelResponseProtocol.c'),'-o',str(exe)],check=True,capture_output=True)
        result=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
        expected=TELEMETRY.pack(0xffffffff,12345,10000,7,2,1,.18,0,*[i*.125 for i in range(4)],*[i*.25 for i in range(4)],*[i*-10 for i in range(4)],*[i*-20 for i in range(4)],65535,1,12,2,65535)
        self.assertEqual(bytes.fromhex(result.stdout.splitlines()[0]),frame(1,expected))
def synthetic_rows(tau=.2,maximum=None):
    rows=[]
    for i in range(1100):
        stage=0 if i<300 else 1 if i<800 else 2;t=(i-300)*.01
        y=0 if stage==0 else .18*(1-np.exp(-t/tau)) if stage==1 else .18*np.exp(-(i-800)*.01/tau)
        if maximum is not None:y=min(y,maximum)
        row={'stage':stage,'state':2 if stage<2 else 3,'mcu_time_unwrapped_us':i*10000,'sequence_delta':1,'cycle_dt_us':10000}
        for w in 'ABCD':row.update({f'target_{w}_m_s':.18 if stage==1 else 0,f'feedback_{w}_m_s':y,f'pwm_{w}_control':1000})
        rows.append(row)
    return rows
DEFINITION={'verified_quantization_m_s':dict.fromkeys('ABCD',.0003403),'zero_speed_band_m_s':dict.fromkeys('ABCD',.0006806)}
PLAN={'pre_ms':3000,'hold_ms':5000,'post_ms':3000}
class MetricTests(unittest.TestCase):
    def test_late_post_motion_has_no_stop_time_and_explicit_reason(self):
        rows=synthetic_rows();rows[-50]['feedback_A_m_s']=.01
        m=wheel_metrics(rows,'A',DEFINITION,PLAN)
        self.assertIsNone(m['stop_time_s']);self.assertIn('post_zero_band_not_continuously_held',m['reason'])
    def test_known_first_order(self):
        m=wheel_metrics(synthetic_rows(),'A',DEFINITION,PLAN)
        self.assertAlmostEqual(m['rise_time_s'],.2*np.log(9),delta=.011);self.assertAlmostEqual(m['settling_time_s'],.6,delta=.011)
        self.assertEqual(m['overshoot_pct'],0);self.assertLess(abs(m['tail_mean_error_m_s']),1e-6)
    def test_unreachable_no_fake_zero(self):
        m=wheel_metrics(synthetic_rows(maximum=.1),'A',DEFINITION,PLAN)
        self.assertIsNone(m['rise_time_s']);self.assertIsNone(m['settling_time_s']);self.assertGreater(m['hold_rmse_m_s'],0)
    def test_gap_prevents_settling_claim(self):
        rows=synthetic_rows();del rows[400];rows[400]['sequence_delta']=2;rows[400]['cycle_dt_us']=20000
        m=wheel_metrics(rows,'A',DEFINITION,PLAN);self.assertIsNone(m['settling_time_s']);self.assertIsNone(m['tail_rmse_m_s'])
    def test_unknown_quantization(self):
        m=wheel_metrics(synthetic_rows(),'A',{},PLAN);self.assertIsNone(m['settling_time_s']);self.assertIn('not_verified',m['reason'])
class ValidationTests(unittest.TestCase):
    def test_raw_csv_phase_and_hash_audit(self):
        # Temporary synthetic acquisition remains under tests, never real data.
        with tempfile.TemporaryDirectory(prefix='synthetic_',dir=ROOT/'wheel_response/tests') as tmp:
            p=pathlib.Path(tmp);raw=bytearray();clock=ClockTracker();csvrows=[]
            for i in range(1101):
                stage=0 if i<300 else 1 if i<800 else 2 if i<1100 else 255
                state=2 if i<800 else 3 if i<1100 else 4;target=.18 if stage==1 else 0
                payload=TELEMETRY.pack(i,i*10000,10000,7,state,stage,target,0,*([target]*4),*([0.0]*4),*([0]*4),*([0]*4),65535,0,0,0,65535)
                raw.extend(frame(1,payload));row=decode_sample(payload);row.update(clock.update(i,i*10000));row['pc_receive_monotonic_ns']=time.monotonic_ns();csvrows.append(row)
            (p/'raw_rx.bin').write_bytes(raw)
            with (p/'samples.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=CSV_FIELDS);w.writeheader();w.writerows(csvrows)
            meta={'mode':'run','run_id':7,'complete':True,'actual_plan':{**PLAN,'step_mm_s':180,'precheck':True},'board_config':{'firmware_build_id':'SYNTHETIC'},'download_record':{'board_identity_verified':True,'firmware_build_id':'SYNTHETIC'},'hashes':{name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in ['raw_rx.bin','samples.csv']}}
            (p/'metadata.json').write_text(json.dumps(meta),encoding='utf-8')
            result=validate(p);self.assertTrue(result['valid'],result);self.assertEqual(result['actual_samples'],1100)
            (p/'samples.csv').write_text((p/'samples.csv').read_text(encoding='utf-8').replace(',0.18000000715255737,',',0.2,',1),encoding='utf-8')
            result=validate(p);self.assertFalse(result['valid']);self.assertIn('archived_hash_mismatch',result['reasons'])
if __name__=='__main__':unittest.main()
