"""Reproducible Keil build only; never downloads firmware."""
import argparse, csv, datetime, hashlib, json, os, pathlib, shutil, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[2]
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--uv4')
    ap.add_argument('--baseline', action='store_true')
    ap.add_argument('--rebuild', action='store_true')
    args = ap.parse_args()
    candidates = [args.uv4, os.environ.get('KEIL_UV4'), shutil.which('UV4')]
    for drive in ('C:', 'D:'):
        candidates += [drive+'/Keil_v5/UV4/UV4.exe', drive+'/Keil/UV4/UV4.exe']
    uv4 = next((pathlib.Path(p).resolve() for p in candidates if p and pathlib.Path(p).is_file()), None)
    if uv4 is None:
        ap.error('UV4.exe was not found. Supply --uv4 with its installed path.')
    import xml.etree.ElementTree as ET
    project = ROOT/'MDK-ARM'/('AgriBot.uvprojx' if args.baseline else 'WheelResponse.uvprojx')
    if not args.baseline:
        sources=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in ('.c','.h','.s','.uvprojx')
                       and '.venv' not in p.parts and 'wheel_response' not in p.parts and p.name!='WheelResponseBuildIdentity.h')
        manifest=[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]
        build_id='WRS1-'+hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16]
        header=ROOT/'System/WheelResponseBuildIdentity.h'
        header_text=f'/* Generated from firmware source manifest; excludes this header to avoid a hash cycle. */\n#define WRS_BUILD_ID "{build_id}"\n'
        if not header.exists() or header.read_text(encoding='utf-8')!=header_text:header.write_text(header_text,encoding='utf-8')
        evidence=ROOT/'wheel_response/evidence'
        evidence.mkdir(parents=True,exist_ok=True)
        with (evidence/'source_manifest_sha256.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['path','sha256']);writer.writeheader();writer.writerows(manifest)
        (evidence/'source_identity.json').write_text(json.dumps({'firmware_build_id':build_id,'baseline_git_commit':'8655eb21f9537f84b5a66effc0fdb085a4993a99',
            'source_manifest_sha256':hashlib.sha256((evidence/'source_manifest_sha256.csv').read_bytes()).hexdigest(),
            'generated_header_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),'branch':'codex/wheel-response','dirty_source':True},indent=2),encoding='utf-8')
    target = ET.parse(project).findtext('.//TargetName')
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    logs = ROOT/'wheel_response/evidence/build_logs'
    logs.mkdir(parents=True,exist_ok=True)
    log = logs/(('baseline' if args.baseline else 'experiment')+'_'+stamp+'.log')
    command = [str(uv4), '-r' if args.rebuild else '-b',str(project),'-t',target,'-o',str(log),'-j0','-sg']
    result = subprocess.run(command, cwd=project.parent)
    text = log.read_text(encoding='utf-8',errors='replace') if log.exists() else ''
    success = result.returncode in (0,1) and '0 Error(s)' in text
    meta = {'uv4':str(uv4),'project':str(project),'target':target,'command':command,'exit_code':result.returncode,'success':success,'log':str(log),'compiler_setting':ET.parse(project).findtext('.//pCCUsed')}
    if success:
        output = project.parent/ET.parse(project).findtext('.//OutputDirectory').replace('\\','/')
        name = ET.parse(project).findtext('.//OutputName')
        meta['images']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for ext in ('hex','axf') if (p:=output/(name+'.'+ext)).is_file()}
        success=len(meta['images'])==2
        meta['success']=success
        if not args.baseline:meta['firmware_build_id']=build_id
    log.with_suffix('.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    if not args.baseline:
        (ROOT/'wheel_response/evidence/build_identity.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False))
    raise SystemExit(0 if success else 1)
if __name__=='__main__': main()
