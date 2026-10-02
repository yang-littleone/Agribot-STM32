"""Archive the complete experiment snapshot and verify every payload byte."""
import csv
import datetime
import hashlib
import io
import json
import pathlib
import subprocess
import tempfile
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
WR=ROOT/'wheel_response'
DEST=WR/'evidence/final_delivery'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    archive=pathlib.Path(r'D:\MCU\STM32\AgriBot')/('Windows四轮轮速响应测试_完整回传_'+now.strftime('%Y%m%d_%H%M%S')+'.zip')
    assert not archive.exists()
    scopes=['Core','System','Hardware','MDK-ARM/WheelResponse.uvprojx','MDK-ARM/WheelResponse.uvoptx','MDK-ARM/RTE/_WheelResponse',
            'wheel_response/tools','wheel_response/tests','wheel_response/config','wheel_response/records',
            'wheel_response/requirements.txt','wheel_response/requirements_lock.txt','wheel_response/build.ps1',
            'wheel_response/README_Windows.md','wheel_response/README_Bluetooth.md','wheel_response/README_Linux回传与复核.md',
            'wheel_response/完整落地轮速响应实验_5米瓷砖地面.md','wheel_response/Windows四轮轮速响应测试_执行结果.md',
            'wheel_response/论文第5.3.1节_候选文字.md','Windows四轮轮速响应测试_执行结果.md']
    patch=subprocess.run(['git','diff','HEAD','--binary','--',*scopes],cwd=ROOT,capture_output=True,check=True).stdout
    untracked=subprocess.run(['git','ls-files','--others','--exclude-standard','-z','--',*scopes],cwd=ROOT,capture_output=True,check=True).stdout
    additions=[]
    for name in untracked.decode('utf-8').split('\0'):
        if not name or '__pycache__' in pathlib.PurePosixPath(name).parts:continue
        if pathlib.Path(name).suffix.lower() in ('.pyc','.exe'):continue
        result=subprocess.run(['git','diff','--no-index','--binary','--','/dev/null',name],cwd=ROOT,capture_output=True)
        assert result.returncode in (0,1),result.stderr.decode(errors='replace')
        patch+=result.stdout;additions.append(name)
    patch_path=DEST/'combined_source_changes.patch';patch_path.write_bytes(patch)
    # Verify reconstruction in a fresh clone, leaving the measured worktree alone.
    clone=pathlib.Path(tempfile.mkdtemp(prefix='codex_handoff_patch_check_'))/'source'
    subprocess.run(['git','clone','--quiet','-b','codex/wheel-response',str(DEST/'baseline_history.bundle'),str(clone)],capture_output=True,check=True)
    check=subprocess.run(['git','apply','--check',str(patch_path)],cwd=clone,capture_output=True)
    assert check.returncode==0,check.stderr.decode(errors='replace')
    applied=subprocess.run(['git','apply',str(patch_path)],cwd=clone,capture_output=True)
    assert applied.returncode==0,applied.stderr.decode(errors='replace')
    source=list(csv.DictReader((WR/'evidence/source_manifest_sha256.csv').open(encoding='utf-8-sig')))
    normalized_equal=[];exact_equal=[];mismatch=[]
    for row in source:
        actual=ROOT/row['path'];reconstructed=clone/row['path']
        if not reconstructed.exists():mismatch.append(row['path']);continue
        a=actual.read_bytes();b=reconstructed.read_bytes()
        if a==b:exact_equal.append(row['path'])
        elif a.replace(b'\r\n',b'\n')==b.replace(b'\r\n',b'\n'):normalized_equal.append(row['path'])
        else:mismatch.append(row['path'])
    assert not mismatch,mismatch
    save(DEST/'patch_reconstruction_verification.json',{'verified_local':now.isoformat(),'fresh_clone':str(clone),'baseline_bundle_verified':True,'git_apply_check_passed':True,'git_apply_passed':True,'source_files_checked':len(source),'exact_bytes_equal':len(exact_equal),'line_endings_only_different':normalized_equal,'substantive_mismatches':mismatch,'patch_sha256':sha(patch_path),'additional_untracked_files_in_patch':additions,'note':'Windows fresh clone/patch verification; not a Linux firmware build. Full snapshot source_manifest preserves exact original bytes.'})
    save(DEST/'package_contents_policy.json',{'archive_filename':archive.name,'package_scope':'Complete experiment worktree snapshot, including current source, vendor dependencies, all build outputs, all wheel_response records, historical archives already in this worktree, baseline history bundle, source patch, taskbook, PCB and floor evidence.','excluded_paths':['.git','.venv','__pycache__'],'no_original_files_deleted':True,'external_prior_delivery_zips':'Remain at D:/MCU/STM32/AgriBot. All underlying experiment source and evidence are in this final full snapshot; those separate ZIP containers are not duplicated here.','no_Word_thesis_overwritten':True})
    # Clear, user-facing entry point at the archive root.
    (ROOT/'开始阅读_Linux_Codex.md').write_text('''# Linux Codex 接续本次轮速实验

1. 先读 wheel_response/Windows四轮轮速响应测试_执行结果.md（最终回传报告）。
2. 再读 wheel_response/README_Linux回传与复核.md，先核对整包及逐文件SHA256。
3. 论文实测说明在 wheel_response/data/实测结果说明.md；正文候选在 wheel_response/论文第5.3.1节_候选文字.md。
4. 正式选用清单 wheel_response/data/formal_trial_manifest.csv，20次有效、每组n=5；正式指标80行、独立补测指标16行分别在 formal_metrics.csv/supplemental_metrics.csv。
5. 全部原始流、CSV、参数快照、校验、图件、失败和中断都保留。低速落地原正式R05有三轮未稳定；4次补测均未四轮同时满足±5%，必须如实呈现。

本包完整项目可直接浏览。基线bundle不含未提交实验修改；源码补丁和完整快照提供当前实现。不要批量替换原始metadata中的Windows路径，不要把预检/补测混入原n=5，不要自动覆盖Word论文。所有历史状态报告以自身时间戳理解，最终状态以最终回传报告及final_delivery/final_status.json为准。
''',encoding='utf-8')
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and not any(part in ('.git','.venv','__pycache__') for part in p.relative_to(ROOT).parts) and p.name!='delivery_manifest_sha256.csv')
    payload=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=['path','sha256','bytes']);writer.writeheader();writer.writerows(payload)
    manifest=stream.getvalue()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as zipped:
        for p in files:zipped.write(p,p.relative_to(ROOT).as_posix())
        zipped.writestr('delivery_manifest_sha256.csv',manifest)
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert len(zipped.namelist())==len(payload)+1
        for row in payload:
            with zipped.open(row['path']) as f:
                h=hashlib.sha256()
                for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
            assert h.hexdigest()==row['sha256'],row['path']
    verification={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'payload_files':len(payload),'zip_entries':len(payload)+1,'uncompressed_payload_bytes':sum(r['bytes'] for r in payload),'all_payload_hashes_verified':True,'zip_CRC_verified':True,'formal_valid':20,'supplemental_valid':4,'low_speed_all_four_goal_met':False,'source_files_verified':len(source),'patch_reconstruction_verified':True,'verified_local':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()}
    save(archive.with_suffix('.verification.json'),verification)
    archive.with_suffix('.zip.sha256').write_text(verification['sha256']+'  '+archive.name+'\n',encoding='utf-8')
    (ROOT/'delivery_manifest_sha256.csv').write_text(manifest,encoding='utf-8',newline='')
    # Receipts written after hashing cannot be included in the same archive.
    save(DEST/'delivery_archive_receipt.json',verification)
    import shutil
    shutil.copy2(WR/'Windows四轮轮速响应测试_执行结果.md',archive.with_suffix('.报告.md'))
    print(json.dumps(verification,ensure_ascii=False))

if __name__=='__main__':
    main()
