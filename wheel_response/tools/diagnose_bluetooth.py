"""Zero-drive UART rate sweep via USB, HELLO/GET_CONFIG via SPP; never ARM/START."""
import argparse,json,time
from wheel_response_cli import Session, output_dir, local_now, save_json
from bluetooth_serial import resolve_spp

def diagnostic(usb_port,bt_port):
    root=output_dir('UART_RATE_DIAG','wheel_response/evidence/bluetooth')
    u=root/'usb';b=root/'spp';u.mkdir();b.mkdir()
    result={'complete':False,'tested':[],'usb_port':usb_port,'spp_port':bt_port,'motion_commands_sent':False}
    with Session(usb_port,u,{'mode':'uart_rate_diagnostic','start_local':local_now(),'complete':False}) as usb:
        usb.inspect()
        with Session(bt_port,b,{'mode':'uart_rate_diagnostic','start_local':local_now(),'complete':False}) as bt:
            until=time.monotonic()+1
            while time.monotonic()<until:bt.pump();usb.pump()
            for baud,code in [(115200,8),(9600,4),(19200,5),(38400,6),(57600,7),(128000,9)]:
                usb.config=None;usb.inspect();usb.send('BT_UART_BAUD',step=code)
                attempt={'baud':baud,'matched':False}
                try:
                    ack=bt.send('HELLO');attempt['ack']=list(ack)
                    bt.config=None;bt.send('GET_CONFIG');until=time.monotonic()+3
                    while bt.config is None and time.monotonic()<until:bt.pump()
                    if bt.config is None:raise TimeoutError('No SPP configuration frame')
                    attempt.update(matched=True,board_config=bt.config)
                except (TimeoutError,RuntimeError) as e:attempt['error']=str(e)
                usb.config=None;cfg,_=usb.inspect();attempt['usb_config_after']=cfg
                result['tested'].append(attempt);save_json(root/'result.json',result)
                print(json.dumps(attempt),flush=True)
                if attempt['matched']:result.update(matched_uart_baud=baud,complete=True);break
            usb.metadata['complete']=True;bt.metadata['complete']=True
        # Finish on the USB owner. No motion and no automated fault clearing.
        usb.config=None;cfg,ack=usb.inspect();result.update(final_state=ack[3],final_usb_config=cfg)
    save_json(root/'result.json',result);print('Evidence:',root,flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--usb-port',default='COM12');ap.add_argument('--spp-port');a=ap.parse_args()
    r=diagnostic(a.usb_port,a.spp_port or resolve_spp());raise SystemExit(0 if r['complete'] else 2)
