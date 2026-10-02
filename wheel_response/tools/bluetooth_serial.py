"""Resolve a paired classic Bluetooth SPP outgoing COM port; no pairing or motion."""
import json, re, subprocess
from serial.tools import list_ports

def outgoing_ports(name, devices, ports):
    addresses = [d['InstanceId'].split('\\')[1][4:].upper() for d in devices
                 if d.get('FriendlyName','').casefold() == name.casefold()
                 and d.get('InstanceId','').upper().startswith('BTHENUM\\DEV_')]
    return sorted({p.device for p in ports if 'BTHENUM' in p.hwid.upper()
                   and 'LOCALMFG&0002' in p.hwid.upper()
                   and any(re.search(r'(?<![0-9A-F])'+a+r'(?![0-9A-F])',p.hwid.upper()) for a in addresses)})

def resolve_spp(name='WHEELTEC'):
    script = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); @(Get-PnpDevice -Class Bluetooth -PresentOnly | Where-Object { $_.InstanceId -like 'BTHENUM\\DEV_*' } | Select-Object FriendlyName,InstanceId) | ConvertTo-Json -Compress"
    r = subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,
                       encoding='utf-8',errors='replace',timeout=20,check=True)
    devices = json.loads(r.stdout or '[]')
    if isinstance(devices,dict): devices=[devices]
    candidates=outgoing_ports(name,devices,list_ports.comports())
    if len(candidates)!=1:
        raise RuntimeError(f'Expected one paired outgoing SPP port for {name!r}; found {candidates}. Specify the verified COM port explicitly.')
    return candidates[0]

def transport_for_port(port):
    match=next((p for p in list_ports.comports() if p.device.casefold()==port.casefold()),None)
    return 'bluetooth_spp' if match and 'BTHENUM' in match.hwid.upper() else 'usb_serial'
