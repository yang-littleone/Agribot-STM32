"""Explicit Keil download, separate from build; never sends ARM or START."""
import argparse, datetime, hashlib, json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--robot',required=True,choices=['B'])
    ap.add_argument('--physical-ready',action='store_true',help='Use only after the user confirms reliable wheel support or disconnected motor power.')
    args=ap.parse_args()
    if not args.physical_ready:ap.error('Physical readiness confirmation is required for programming.')
    evidence=ROOT/'wheel_response/evidence'
    build=json.loads((evidence/'build_identity.json').read_text(encoding='utf-8'))
    if not build.get('success') or len(build.get('images',{}))!=2:raise RuntimeError('A successful build and both image hashes are required.')
    for name,digest in build['images'].items():
        p=ROOT/name
        if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise RuntimeError('Image differs from the recorded build: '+name)
    with (evidence/'source_manifest_sha256.csv').open(encoding='utf-8',newline='') as f:
        import csv
        for row in csv.DictReader(f):
            if hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Firmware source changed after build: '+row['path'])
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    log=evidence/'download_logs'/('download_'+now.strftime('%Y%m%d_%H%M%S_%f')+'.log');log.parent.mkdir(exist_ok=True)
    cmd=[build['uv4'],'-f',build['project'],'-t',build['target'],'-o',str(log),'-j0','-sg']
    record={'robot_id':args.robot,'physical_readiness':'User confirmed four wheels raised, board and motor supply on in chat.','start_local':now.isoformat(),
            'firmware_build_id':build['firmware_build_id'],'image_sha256':build['images'],'command':cmd,'log':str(log),'board_identity_verified':False}
    try:
        result=subprocess.run(cmd,cwd=ROOT/'MDK-ARM',timeout=60)
        record['exit_code']=result.returncode
        text=log.read_text(encoding='utf-8',errors='replace') if log.is_file() else ''
        record['keil_reported_success']=result.returncode in (0,1) and 'Error' not in text and ('Programming Done' in text or 'Flash Load finished' in text or 'Verify OK' in text)
        record['keil_log_text']=text
    except Exception as e:
        record['error']=str(e);record['keil_reported_success']=False
    record['end_local']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    log.with_suffix('.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    (evidence/'download_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))
    raise SystemExit(0 if record['keil_reported_success'] else 1)
if __name__=='__main__':main()
