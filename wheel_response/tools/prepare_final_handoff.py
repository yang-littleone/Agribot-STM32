"""Prepare the final offline report and explicitly selected formal data for Linux."""
import collections
import csv
import datetime
import hashlib
import importlib.metadata
import json
import pathlib
import platform
import shutil
import subprocess
import sys
import numpy as np
from analyze_response import write_csv
from plot_response import write_figure
from validate_data import validate

ROOT = pathlib.Path(__file__).resolve().parents[2]
WR = ROOT/'wheel_response'
DEST = WR/'evidence/final_delivery'
BASE = '8655eb21f9537f84b5a66effc0fdb085a4993a99'
NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    source = csv_rows(WR/'evidence/source_manifest_sha256.csv')
    assert all(sha(ROOT/r['path']) == r['sha256'] for r in source)
    identity = read(WR/'evidence/source_identity.json')
    build = read(WR/'evidence/build_identity.json')
    flash = read(WR/'evidence/download_record.json')
    assert identity['firmware_build_id'] == build['firmware_build_id'] == flash['firmware_build_id']
    assert flash['keil_reported_success'] and flash['board_identity_verified']
    assert sha(WR/'evidence/source_manifest_sha256.csv') == identity['source_manifest_sha256']
    assert sha(ROOT/'System/WheelResponseBuildIdentity.h') == identity['generated_header_sha256']
    assert all(sha(ROOT/p) == h for p,h in build['images'].items())
    save(DEST/'source_and_images_verification.json', {'verified_local': NOW, 'source_files_verified':len(source), 'mismatches':[], 'firmware_build_id':identity['firmware_build_id'], 'images':build['images'], 'source_manifest_sha256':identity['source_manifest_sha256']})
    input_dir = DEST/'original_request'
    input_dir.mkdir(exist_ok=True)
    taskbook = pathlib.Path(r'D:\MCU\STM32\AgriBot\Windows四轮轮速响应测试_Codex执行任务书.md')
    shutil.copy2(taskbook,input_dir/taskbook.name)
    pcb = pathlib.Path(r'C:\Users\28047\Desktop\硕士简历\pcb\ProDoc_小车底板v1_2026-08-23.epro2')
    if pcb.exists():
        shutil.copy2(pcb,input_dir/pcb.name)
    versions = {'python':sys.version,'platform':platform.platform(),'packages':{p:importlib.metadata.version(p) for p in ('pyserial','numpy','matplotlib')}}
    save(DEST/'software_versions.json',versions)
    (WR/'requirements_lock.txt').write_text(''.join(f'{p}=={v}\n' for p,v in versions['packages'].items()),encoding='utf-8')
    register = csv_rows(WR/'records/trial_register.csv')
    plan = read(WR/'config/experiment_plan.json')
    planned = {p['trial_id']:p for p in plan['trials']}
    inventory = []
    formal = []
    formal_metrics = []
    supplemental = []
    supplemental_metrics = []
    mandatory_ids = set()
    for r in register:
        trial = planned[r['trial_id']]
        d = pathlib.Path(r['data_directory']) if r['data_directory'] else None
        entry = dict(r)
        entry['directory_relative'] = d.relative_to(ROOT).as_posix() if d else ''
        entry['category'] = 'supplemental' if trial.get('supplemental') else ('precheck' if trial.get('precheck') else 'formal')
        entry['phase_samples'] = 0
        entry['all_four_settled'] = ''
        if d and (d/'metadata.json').exists():
            quality = read(d/'validation.json') if (d/'validation.json').exists() else validate(d)
            entry.update(phase_samples=quality['actual_samples'],quality_valid=quality['valid'],quality_reasons=';'.join(quality['reasons']))
            meta = read(d/'metadata.json')
            entry['firmware_build_id'] = meta.get('board_config',{}).get('firmware_build_id','')
            metrics = csv_rows(d/'metrics.csv') if (d/'metrics.csv').exists() else []
            if metrics:
                entry['all_four_settled'] = len(metrics)==4 and all(bool(m['settling_time_s']) for m in metrics)
            if r['include_in_baseline'].lower()=='true':
                assert entry['category']=='formal' and quality['valid'] and len(metrics)==4
                fresh = validate(d)
                assert fresh['valid'] and fresh['actual_samples']==1100 and fresh['stage_counts']=={'0':300,'1':500,'2':300}
                assert fresh['sequence_missing']==0 and fresh['queue_drop_max']==0 and fresh['decoder_stats'].get('bad_crc',0)==0
                assert read(d/'continuation_review.json')['passed']
                cfg = meta['board_config']
                assert cfg['kp_ABCD']==[800]*4 and cfg['ki_ABCD']==[500]*4
                assert cfg['nominal_period_us']==10000 and cfg['pwm_limit']==16700
                entry.update(raw_rx_sha256=sha(d/'raw_rx.bin'),raw_tx_sha256=sha(d/'raw_tx.bin'),samples_sha256=sha(d/'samples.csv'))
                formal.append(entry.copy());formal_metrics.extend(metrics);mandatory_ids.add(r['trial_id'])
            if trial.get('supplemental') and r['start_local']:
                assert quality['valid'] and read(d/'continuation_review.json')['passed']
                supplemental.append(entry.copy());supplemental_metrics.extend(metrics)
        inventory.append(entry)
    assert len(formal)==20 and len(supplemental)==4
    counts=collections.Counter((r['condition'],int(r['step_mm_s'])) for r in formal)
    assert counts=={('AIR',180):5,('AIR',400):5,('GROUND',180):5,('GROUND',400):5}
    assert not mandatory_ids.intersection(r['trial_id'] for r in supplemental)
    write_csv(WR/'data/formal_trial_manifest.csv',formal)
    write_csv(WR/'data/formal_metrics.csv',formal_metrics)
    write_csv(WR/'data/supplemental_metrics.csv',supplemental_metrics)
    write_csv(WR/'records/final_trial_inventory.csv',inventory)
    save(DEST/'formal_trial_manifest.json',formal)
    summary=csv_rows(WR/'data/summary_metrics.csv')
    assert len(summary)==16 and all(int(r['valid_trial_n'])==5 for r in summary)
    # Connection attempts have their own count; they are not physical repeats.
    counts_table=[]
    for condition in ('AIR','GROUND'):
        baseline=[r for r in inventory if r['category']=='formal' and r['condition']==condition]
        moving=[r for r in baseline if r['start_local']]
        accepted=[r for r in formal if r['condition']==condition]
        counts_table.append({'condition':condition,'planned':10,'started_attempts':len(moving),'normal_completed_valid':len(accepted),'interrupted':sum(r['status']=='interrupted' for r in baseline),'connection_failed_no_motion':sum(r['status']=='connection_failed_no_motion' for r in baseline),'phase_samples_valid':len(accepted)*1100})
    last=pathlib.Path(supplemental[-1]['data_directory'])
    terminal=read(last/'continuation_review.json')
    assert terminal['passed']
    failed_final_static=[]
    for p in sorted((DEST/'final_zero').glob('*/metadata.json')):
        meta=read(p)
        failed_final_static.append({'directory':p.parent.relative_to(ROOT).as_posix(),'complete':meta['complete'],'samples':meta['samples_received'],'raw_tx_bytes':(p.parent/'raw_tx.bin').stat().st_size,'error':meta.get('error') or 'COM13 open timeout, Windows error121; actual CLI output recorded in final_static_connection_review.json','start_local':meta['start_local']})
    status={'report_generated_local':NOW,'baseline_measurement_complete':True,'formal_valid':20,'formal_counts':counts_table,'supplemental_started':4,'supplemental_all_four_qualified':sum(bool(r['all_four_settled']) for r in supplemental),'supplemental_S05_S06_not_executed':True,'user_requested_report_and_Linux_archive':True,'performance_goal_all_conditions_persistent_5percent_achieved':False,'motor_commands_during_delivery':False,'last_valid_terminal_check':{'trial_id':terminal['trial_id'],'directory':last.relative_to(ROOT).as_posix(),'check':terminal},'new_final_static_connection_attempts':failed_final_static,'fresh_static_connection_verified':False,'no_board_firmware_restoration_performed':True}
    save(DEST/'final_status.json',status)
    progress=read(WR/'evidence/ground_formal/progress.json')
    progress.update(updated_local=NOW,ground_motor_runs_started=21,supplemental_next_trial=None,awaiting_physical_reset=False,delivery_requested=True,motor_experiments_closed=True,performance_goal_achieved=False)
    save(WR/'evidence/ground_formal/progress.json',progress)
    save(DEST/'handoff_manifest.json',{'formal_trial_ids':[r['trial_id'] for r in formal],'formal_directories':[r['directory_relative'] for r in formal],'supplemental_ids':[r['trial_id'] for r in supplemental],'baseline_git_commit':BASE,'firmware_build_ids':sorted({r['firmware_build_id'] for r in formal+supplemental}),'selection_rule':'20 quality-valid registered formal trials, with independently registered retest replacing communication-invalid R02. Supplemental attempts excluded. Performance failures retained.','hash_checks':'delivery_manifest_sha256.csv verifies every packaged payload file; metadata.hashes verifies raw files per capture.','historical_status_note':'Historical AIR/Bluetooth/battery reports are snapshots at their timestamps. final_delivery/final_status.json and final execution report describe the final state.'})
    table='|条件|速度(m/s)|轮|上升时间(s)|调节时间(s；有效n)|超调(%)|尾段RMSE(mm/s)|正常停车时间(s)|\n|---|---:|---|---:|---:|---:|---:|---:|\n'
    for row in summary:
        def value(key,scale=1):
            return f"{float(row[key+'_mean'])*scale:.3f} ± {float(row[key+'_sample_sd'])*scale:.3f}"
        table+='|'+('架空' if row['condition']=='AIR' else '落地')+'|'+row['speed_m_s']+'|'+row['wheel']+'|'+value('rise_time_s')+'|'+value('settling_time_s')+'；n='+row['settling_time_s_n']+'|'+value('overshoot_pct')+'|'+value('tail_rmse_m_s',1000)+'|'+value('stop_time_s')+'|\n'
    method='每次 PRE/HOLD/POST 为 3/5/3 秒，100 Hz，同周期记录目标、反馈、PWM及编码器计数。20 次正式试验共有 22000 个有效阶段样本，均为 300/500/300 周期，周期字段均为 10000 us，无正式有效记录的 CRC 错误、缺序号、FIFO 丢样、故障或 PWM 饱和。时间来自 HAL tick，分辨率 1 ms；control_exec_us=65535 是无效值，不能声称微秒精度或实测执行时长。'
    limits='结果仅描述补测平台 B 在本次架空及室内瓷砖地面条件下的底层四路增量式 PI 编码器轮速闭环。编码器轮速不等于车辆地速，不能推断滑移率、上层路径跟踪精度或其他田间负载性能。B 与 A 的一致性为操作者声明，本次数据不能冒充 A 的历史田间原始数据。轮径 65 mm 来自操作者确认，未提供独立测量方法；单圈计数用于比例核验，并非仪器级校准。'
    result_text='# 实测结果说明（最终正式结果与独立补测）\n\n'+f'生成时间：{NOW}。正式计划 20 次均已有质量有效记录；因蓝牙异常多出 2 次中断运动记录和 1 次未启动连接失败。独立低速补测已执行 4 次，均数据有效，但无一次四轮同时满足持续 ±5% 原判据。第 5、6 次仅登记，未启动；本轮按用户指示转入交付。\n\n'+method+'\n\n'+table+'\n表为均值 ± 样本标准差，以试次为重复单位；正式每组 n=5，不能把同次四轮算成独立重复。0.18 m/s 落地 R05 的 A、C、D 未在观察窗口内持续稳定，调节时间不可判定，该三轮该项统计 n=4；其他正式指标均 n=5。这里的 n=4 均值是可判定试次的条件统计，不代表 5 次均已稳定，也不能代替未达标率。\n\n稳定误差带为正式测量前锁定的 ±5%（0.18 档 ±0.009 m/s，0.40 档 ±0.020 m/s；与两倍量化取大），要求从进入带后持续保持至 HOLD 结束，且至少剩余 1 秒观察。尾段误差取 HOLD 最后 2 秒；正常停车时间只在 POST 内按锁定零速带判定，急停和失联停止不混入正常 PI 停车指标。\n\n'+(WR/'evidence/ground_supplemental/独立补测说明.md').read_text(encoding='utf-8')+'\n\n落地 0.18 档正式四轮同时达标 4/5；0.40 档 5/5；架空两档各 5/5。补测的适应性停止意图为“直到满意”，不能与正式 n=5 合并后声称无偏的重复性估计，也不能以补测通过结果覆盖原性能欠佳的正式记录。未平滑、补样、缩放反馈、扩大误差带或改变 PI 参数。\n\n'+limits+'\n\n电池电压采用 ADC1_IN8 PB0 的名义 3.3 V 参考及 11 倍分压，后台约 10 Hz 更新、轮速 100 Hz 记录；未用万用表独立校准。旧快照中的 battery_mv=65535 保持无效。实际质量、附加载荷、轮径测量方式、电机温度、地面精确宽度和长度仍未知；操作者报告至少 5 m 直线路面并逐次复位，不能写成 Codex 独立测得。\n\n完整逐次指标见 formal_metrics.csv（80 行）及 supplemental_metrics.csv（16 行）；汇总见 summary_metrics.csv。正式数据选用清单见 formal_trial_manifest.csv；中断、连接失败及全部预检见 ../records/final_trial_inventory.csv。通用分析器输出的 formal_recorded=23 包含 20 有效、2 中断及 1 未启动连接目录；不等于实际完成 23 次正式运动。\n'
    (WR/'data/实测结果说明.md').write_text(result_text,encoding='utf-8')
    candidate='''# 论文第5.3.1节候选文字（需论文作者核对）

为考察底层四路增量式 PI 轮速闭环响应，在补测平台 B 上分别开展架空和室内瓷砖地面试验，设定 0.18 m/s 与 0.40 m/s 两档目标轮速，每种条件和速度组合完成 5 次有效重复。每次包含 3 s 零速基线、5 s 速度保持和 3 s 正常停车记录，以 100 Hz 在同一控制周期采集四轮目标速度、编码器反馈与 PWM 输出。控制器保持原参数 Kp=800、Ki=500，不另乘控制周期，PWM 限幅为 ±16700。架空正式试验采用 USB 串口，落地正式试验采用 JDY-33 蓝牙 SPP；两阶段使用不同构建身份，控制递推、方向和速度换算保持一致，通信及电压扩展后另行保存架空桥接和安全预检证据。

架空两档试验均满足预先规定的持续 ±5% 稳定判据，各轮平均调节时间约为 0.682～0.778 s。落地 0.40 m/s 时，各轮平均调节时间为 0.648～0.674 s，平均超调为 1.693%～2.629%，尾段轮速 RMSE 为 2.763～4.269 mm/s；5 次重复均实现四轮同时满足稳定判据，且无 PWM 饱和。

落地 0.18 m/s 时，四轮尾段轮速 RMSE 为 3.023～4.010 mm/s。第 5 次正式记录中 A、C、D 轮未在 5 s 保持窗口内满足持续稳定且剩余至少 1 s 观察的要求，因此相应调节时间不可判定；该项数值统计有效次数为 4，其他指标仍按 5 次有效试验统计。后续 4 次独立补测均取得完整数据，但均未实现四轮同时满足原稳定判据，说明本次条件下低速落地持续稳定性仍存在限制。补测独立呈现，不替代正式记录；各项均值、样本标准差和有效次数见实测指标表。

上述试验反映平台 B 在本次条件下的编码器轮速响应，不能由此直接证明车辆地速、轮胎滑移率或路径跟踪精度。平台 B 与田间平台 A 的部件一致性由操作者声明，本次记录不是 A 的历史田间原始数据。轮径依据操作者确认及手动整圈计数核验；电池电压为未经独立校准的 ADC 名义估计，绝对速度和电压精度仍受这些条件限制。
'''
    (WR/'论文第5.3.1节_候选文字.md').write_text(candidate,encoding='utf-8')
    report=f'''# Windows四轮轮速响应测试：最终执行结果与Linux回传报告

生成时间：{NOW}（Asia/Shanghai）。供下发任务的 Linux 端 Codex 接续论文第5.3.1节；不自动覆盖现有 Word 论文。

## 1. 完成状态

原计划正式试验已完成：架空 10 次、落地 10 次质量有效记录，两个速度各 5 次重复。落地正式试验另有 2 次通信中断、1 次未启动连接失败，原始记录全部保留。落地预检启动 5 次，其中 4 次质量有效、1 次 CRC 受限。独立 0.18 m/s 补测已完成 4 次，质量有效 4 次，四轮同时满足持续 ±5% 为 0 次；S05/S06 未启动，不计完成。正式矩阵测量完成不等于性能目标全部达成，低速持续稳定性仍有局限，用户本轮指示转入报告与打包。

架空正式 10 次均质量有效、无中断；落地正式启动 12 次，其中正常有效完成 10 次、中断 2 次。纳入正式统计共 20 次/22000 个阶段样本，补测另 4 次/4400 个阶段样本。实际落地电机试次合计 21 次 = 5 预检 + 12 正式尝试 + 4 补测，另有 1 次未启动连接尝试；禁止把这些都写成正式 n=5。所有登记及证据路径见 records/final_trial_inventory.csv。

## 2. 基线、源码和实际参数

原用户工程 D:/MCU/STM32/AgriBot/AgriBot 保留版本 1e408a343e9468354fac94a523bff9151bbec0d2 及其本地 Keil 修改；实验在独立工作树 D:/MCU/STM32/AgriBot-wheel-response、分支 codex/wheel-response 上进行，参考基线 {BASE}。实验修改为未提交工作树内容，不能只检出 HEAD 后声称已包含全部实验实现。包内完整源码快照、基线 Git bundle 与 combined_source_changes.patch 提供恢复依据，旧补丁和旧镜像仍保留。

四路均为增量式 PI，Kp=800、Ki=500，Ki 不另乘 0.01，PWM 限幅 ±16700，原逆解限幅 ±1 m/s，原反馈 65 mm 轮径、60000 输出轴计数比例保留。每 10 ms 仅一次读清零编码器，快照复制该次计数；C/D 编码器与驱动原符号适配均保留。实验模式仍通过原控制入口调用原逆解与 PI，增加阶段状态机、独立 UART 采集、32 样本静态 FIFO、心跳及故障停止；旧 IMU、显示、手柄和旧上传任务在实验模式不创建。故本试验不验证整机所有上层任务并发下性能，也不等价于独立硬件看门狗验证。

后续新增 JDY-33 蓝牙与后台 ADC 电压读取，没有调 PI。Encoder.c、Motor.c、tim.c、CarControl.c 和 freertos.c 在电压扩展前后哈希一致，见 evidence/battery/source_verification.json；本次再次核对 {len(source)} 个当前固件源清单文件和 HEX/AXF 哈希，全部一致，见 final_delivery/source_and_images_verification.json。

## 3. 编译、烧写与构建身份

Keil ARMCC 5.06 update 7 build 960。最终实验工程 MDK-ARM/WheelResponse.uvprojx 的 WheelResponse 目标实际构建 0 errors、0 warnings；已完成 ST-Link 下载 Programming Done/Verify OK，并通过板端 GET_CONFIG 核对身份。2026-10-02 10:06:54 开始的成功下载以及此前三次失败日志均保留。最新构建为 {identity['firmware_build_id']}。

最新 HEX SHA256：{build['images']['MDK-ARM' + chr(92) + 'WheelResponse' + chr(92) + 'WheelResponse.hex']}。

最新 AXF SHA256：{build['images']['MDK-ARM' + chr(92) + 'WheelResponse' + chr(92) + 'WheelResponse.axf']}。

架空正式 10 次使用 WRS1-db73c13a727f9ae5、COM12 USB；落地正式 10 次及 4 次补测使用 WRS1-b87ba230e207f646、COM13 蓝牙。中间蓝牙固件身份与桥接核验见 evidence/bluetooth 和 evidence/battery。不同阶段不能写成相同固件哈希；原控制参数和换算一致，通信/电压扩展后架空预检另有记录，作为追溯依据。最新离线软件检查 17 项通过，日志 evidence/ground_preparation/software_tests_5m_protocol.log；软件合成测试仅在 tests，不能作为实测数据。

## 4. 实际硬件与核验

轮位 A 左后、B 左前、C 右前、D 右后。用户重新焊接电机/编码器共用插头后恢复四路反馈；维修前后低速异常和恢复记录均保留。输出轮各完整前进一圈的净计数：A 59997、B 59666、C 59682、D 60031，最大与名义 60000 差异约 0.557%。B 核验时额外碰动 C，操作者确认并保留严格单轮检查失败；随后 C 独立整圈采集。未偷偷按这些计数缩放正式反馈。

轮径 65 mm 为操作者确认与原配置一致，独立尺量方法未知。操作者声明 B 与田间 A 的电机、减速箱、编码器、驱动、轮径、供电和载荷一致，但具体型号、质量和载荷数值未提供。场地为用户报告至少 5 m 的室内瓷砖直线路面，逐次实物复位摆正；精确清空长度、宽度和车辆真实行程未独立测量。原 3 m 方案已取消，未实施 3 m 落地试验。硬件资料、用户地面照片和 PCB 项目源文件随包保留。

蓝牙模块用户确认为 JDY-33，经典 SPP 名称 WHEELTEC，COM13 为出站端、COM14 为入站端未采集。USART2 PD5/PD6，115200 8N1；原模块 9600 波特率经维护链 AT+BAUD8 实际核验调整为 115200，名称和密码未更改。USB 为 USART3 PD8/PD9、COM12，在落地阶段已拔下以避免拖线。

电池估计采用 ADC1_IN8 PB0、名义 3.3 V 参考、11 倍分压，后台约 100 ms 更新，轮速仍 100 Hz。没有独立万用表校准；旧 battery_mv=65535 保持无效。当前估计约 12 V，逐次值见原始 CSV 和报告；不得宣称仪器精度。质量、额外负载、电机温度、精确测距与独立轮径测量仍未知。

## 5. 采样、固定指标与正式结果

{method}

上升时间为相邻真实样本的 10%～90% 交点插值；不跨越超过 15 ms 的缺口。调节时间须进入锁定 ±5% 带并持续到 HOLD 结束，剩余至少 1 s；带宽按 max(幅值5%,两倍核验量化) 取值。尾段为最后 2 s。缺失调节或停车时间保留空值与原因；正常 POST 停车与急停/失联停车区分。四轮不是独立重复，均值与样本 SD 按试次计算。

{table}

0.18 m/s 落地 R05 的 A、C、D 未调节，其调节时间各 n=4，均值只描述可判定记录，并需并列报告未达标次数；其他正式指标各 n=5。落地第 4 次虽然均可判定，但 C、D 调节分别约 3.07/3.84 s，不能称为所有试次均快速稳定。架空两档各 5/5、落地 0.40 档 5/5、落地 0.18 档 4/5 实现四轮同时达标。4 次低速独立补测无一次四轮同时达标，全部独立保留，详见 evidence/ground_supplemental/独立补测说明.md。未调参、未筛选较好曲线替代正式结果、未扩大误差带。

## 6. 通信异常、安全检查与最后状态

原正式 R02 在 POST 中出现 CRC/缺序号并经主机 ABORT 应答停止，阶段为 300/500/12、缺 12 个序号，排除正式汇总；其后静态 30 s 也出现 CRC 37、缺 486，记录不完整，不能用作持续静止有效证明。操作者确认车停住并调整蓝牙距离/遮挡后，60 s 接收 6017 清洁 FAULT2 样本，随后清除已知 ABORT 故障且静态恢复有效。第 1 次重测又在 HOLD 中缺 11、CRC1，阶段 300/254/0，ABORT 应答停止并排除。第 2 次重测端口打开超时，在 ARM/START 前失败，无运动。第 3 次重测完整有效，填入原 R02 重复位置。全部失败及恢复保留；接近蓝牙后改善不能证明唯一物理根因。

更新后架空主动 ABORT、停止心跳两个安全预检均经独立安全校验通过，预期故障位分别 2/1；正常试验数据校验将其视为故障/不完整是预期，不能混入正式响应。PC 时间含蓝牙缓冲/传输延迟，不能当精确 MCU 超时。旧架空急停及失联记录、下载失败与维修前异常也未删除。

正式矩阵结束后曾取得 30 s/3019 样本有效零驱动记录。最后一次补测 S04 正常结束，COMPLETE 目标/PWM 全零、末尾 100 ms 四轮反馈在锁定零速带；完整检查在该次 continuation_review.json。交付前又尝试两次只读静态连接（30 s、5 s），均为 Windows COM13 打开超时121、0接收样本和0发送字节，未发送 ARM/START，也未获得新的静态证明。最后可信停止证据为 S04 结束记录；此时连接失败的原因未知，不能声称“交付前重新连续测得30秒静止”。本次未恢复其他固件或自动解除故障。

## 7. 论文适用范围和接续工作

{limits}

数据具备本节真实响应分析的可用性，但不支持“所有落地工况四轮均持续 ±5% 达标”。Linux 端应以完整正式矩阵为主，说明低速持续稳定性的限制，将独立补测单独呈现；不把未达标时间写成零，不仅统计通过曲线，也不把通信中断样本当完整重复。现有证据不能确定低速波动由电池、温度、地砖、机械摩擦或采样细节中的哪项导致；尾段相关性只是描述，不是因果诊断。

候选正文见 论文第5.3.1节_候选文字.md；逐次数据、汇总 CSV、每次四种原始图 PNG/SVG 和四组正式重复叠图已生成。供作者审核，不直接覆盖论文。建议论文报告每项有效 n、样本 SD、未达标试次数，并声明补测事后性质。若将来改 PI、换场地或测量真实地速，应登记新的条件组，不合并成当前原参数 n=5。

## 8. 回传内容、哈希与恢复

归档包含整个实验项目快照（包括已存在的历史压缩包及构建输出）、所有 wheel_response 原始/派生/异常证据、Python 工具与版本、任务书和 PCB 资料、当前及历史 HEX/AXF、构建/下载日志、基线 Git bundle 和完整源码补丁。不包含 .git 工作树链接、Python .venv 和 __pycache__ 缓存；这些无法作为跨系统运行环境。所有现有文件在 Windows 原位保留，没有删除失败数据或历史交付包。

包内 delivery_manifest_sha256.csv 逐文件列出路径、字节数、SHA256；压缩包旁同名 .verification.json 和 .sha256 给出整包哈希及校验结果。读取入口 README_Linux回传与复核.md。历史状态文档按各自时间保留（可能写“落地尚未执行”），最终状态以本报告和 evidence/final_delivery/final_status.json 为准。

在 Linux 解压到新的空目录，先运行 tools/verify_package.py 验证全部文件，再在工作副本中按 requirements_lock.txt 创建环境并运行离线分析。Windows 绝对路径保留为历史采集记录，不要批量改写 metadata；当前相对路径索引位于 formal_trial_manifest.csv 和 handoff_manifest.json。Linux 重算不需要串口、蓝牙或 Keil，更不会自动启动电机。详细步骤见 Linux 说明。

完整源码快照可直接检查；若需 Git 基线，使用 final_delivery/baseline_history.bundle 克隆 codex/wheel-response，再应用 combined_source_changes.patch 或复制包内当前源码。此分支 bundle 对应基线，实验修改由补丁与完整快照提供。参考固件 evidence/baseline_images 为实际编译基线，不能假称为烧写前板上读回镜像。硬件恢复须另由现场确认，当前交付未进行恢复烧写。
'''
    oldroot=ROOT/'Windows四轮轮速响应测试_执行结果.md'
    backup=WR/'evidence/historical_AIR_delivery/root_执行结果.md'
    if oldroot.exists() and not backup.exists():shutil.copy2(oldroot,backup)
    (WR/'Windows四轮轮速响应测试_执行结果.md').write_text(report,encoding='utf-8')
    oldroot.write_text(report,encoding='utf-8')
    (WR/'README_Linux回传与复核.md').write_text('''# Linux Codex 接续入口

先读 Windows四轮轮速响应测试_执行结果.md，再读 data/实测结果说明.md、data/formal_trial_manifest.csv 和 evidence/final_delivery/final_status.json。第5.3.1节候选正文已另存，作者审核后再并入论文。

正式矩阵20次有效，两个条件×两个速度×5次；4次补测独立保留，全部没有实现四轮同时满足持续±5%。原低速落地R05三轮未在窗口内稳定，不能被补测或均值覆盖。S05/S06仅登记未执行。历史报告中的“落地未执行”是旧时点，不是最终状态。

## 1. 接收和完整性检查

把 ZIP、同名 .verification.json 和 .sha256 一起复制到 Linux。先核对 ZIP SHA256，再解压到新空目录。ZIP 使用相对路径和 UTF-8 文件名，根目录就是实验项目，不含 Windows 虚拟环境。

```sh
sha256sum -c Windows四轮轮速响应测试_完整回传_实际时间戳.zip.sha256
unzip Windows四轮轮速响应测试_完整回传_实际时间戳.zip -d wheel-response-delivery
cd wheel-response-delivery
python3 wheel_response/tools/verify_package.py .
```

上例文件名中的“实际时间戳”需替换为收到的实际文件名。verify_package.py 仅用 Python 标准库，只读检查包内清单。清单本身不包含其自身，整包哈希覆盖它；所有源文件和原始证据均在逐文件清单中。

## 2. 在副本中重算

保留解压原件用于哈希核查，复制工作副本后再分析（分析会重写派生 validation/metrics/图表，不改原始字节或 samples.csv）。Windows 实际使用 Python3.13.14、pyserial3.5、numpy2.5.3、matplotlib3.11.2。优先同系列 Python3.13，按锁定依赖安装；Linux 环境未在本机实际运行，以下为按路径兼容工具准备的步骤。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r wheel_response/requirements_lock.txt
.venv/bin/python wheel_response/tools/analyze_response.py wheel_response/data
```

分析器只离线读取 raw_rx.bin/CSV/metadata，生成逐次校验、指标、四种图和正式有效重复叠图，不需要板卡或 Keil。普通分析器打印 formal_recorded=23 包含2个中断和1个未启动连接目录；formal_valid=20 才是完整正式试次数。它还会将 data/实测结果说明.md 重写成通用简版，因此最终完整说明请保留本包原件。论文正式选用清单为 data/formal_trial_manifest.csv；补测 precheck=true，仅为独立分组排除正式汇总，不表示没有测量价值。

正式逐轮指标为 data/formal_metrics.csv（80行），补测为 data/supplemental_metrics.csv（16行）；总指标 all_metrics.csv 同时包括预检及失败尝试，不能直接全部当正式数据。每项 *_n 指标表示可判定的次数；0.18落地A/C/D调节时间n=4，必须同时报告该轮1次未调节，不能用4次均值代表5次全部稳定。

若运行离线测试，需 GCC：.venv/bin/python -m unittest discover -s wheel_response/tests -v。合成数据仅在 tests，禁止放进 real data；Windows已保存17项通过日志。没有要求重新烧写或实物测试。

## 3. 源码和路径

完整项目当前源码、MDK工程、构建输出都在包内。evidence/final_delivery/baseline_history.bundle 保留参考 Git 历史；在项目根目录路径下为 wheel_response/evidence/final_delivery/baseline_history.bundle。bundle分支对应8655eb2基线，实验未提交修改由 combined_source_changes.patch 及完整快照提供。可使用 git clone -b codex/wheel-response <bundle绝对路径> <新目录>，在新克隆目录 git apply --check <补丁绝对路径> 后应用；原始数据仍从完整包复制。

旧 Windows metadata 中绝对路径是历史事实，不要改写。当前索引的 directory_relative、handoff_manifest.json 和各目录相对原始文件名可用于 Linux 定位。Keil 编译/下载日志是 Windows 已完成工作的证据；本次没有在 Linux 上验证固件重建，也没有读回板上完整 Flash。

## 4. 论文表述边界

四路增量式PI，不写成底层四轮PID；Kp800/Ki500保持不变。只论编码器轮速响应，不推断地速、滑移率或田间路径跟踪。B与A一致为操作者声明，不是A历史原始数据。轮径65mm为操作者确认；单圈比例核验非仪器级校准。ADC电压为名义估计，未校准；65535为无效字段。任务书和PCB原件、维修前异常、所有中断和静态连接失败都保留。

本次正式矩阵已测完，但低速全达标目标未实现；用户已要求转入回传交付，不能把“尚未达标”改写成“全部满意”。最后补测终端零输出/零速带检查通过；交付前两次只读重连失败，没有得到新的30秒静态记录。以各自时间戳精确描述，不虚构当前通信状态。
''',encoding='utf-8')
    # Scientific summary plots use actual trial-level estimates and sample SD.
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for ax,speed in zip(axes,(.18,.4)):
        for condition,color,offset in [('AIR','#256caa',-.12),('GROUND','#d65f28',.12)]:
            rows=[r for r in summary if r['condition']==condition and abs(float(r['speed_m_s'])-speed)<1e-8]
            ax.errorbar(np.arange(4)+offset,[float(r['tail_rmse_m_s_mean'])*1000 for r in rows],yerr=[float(r['tail_rmse_m_s_sample_sd'])*1000 for r in rows],fmt='o',capsize=4,color=color,label=condition+' n=5')
        ax.set(xticks=np.arange(4),xticklabels=list('ABCD'),ylabel='Last 2 s RMSE (mm/s)',title=f'{speed:.2f} m/s: mean and sample SD')
        ax.grid(alpha=.2);ax.legend()
    fig.suptitle('Formal trials: wheel-speed errors; not vehicle ground speed')
    write_figure(fig,WR/'data/summary_figures/AIR_GROUND_tail_RMSE')
    for family,selected in [('GROUND_V180_formal', [r for r in formal if r['condition']=='GROUND' and int(r['step_mm_s'])==180]),('GROUND_V180_supplemental', supplemental)]:
        fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,sharey=True,layout='constrained')
        for trial in selected:
            rows=csv_rows(pathlib.Path(trial['data_directory'])/'samples.csv')
            hold=[r for r in rows if int(r['run_id'])==int(trial['run_id']) and int(r['state'])==2 and int(r['stage'])==1]
            t=np.array([(int(r['mcu_time_unwrapped_us'])-int(hold[0]['mcu_time_unwrapped_us']))/1e6 for r in hold])
            tail=t>=3-1e-9
            for ax,w in zip(axes.flat,'ABCD'):
                error=np.array([float(r[f'feedback_{w}_m_s'])-float(r[f'target_{w}_m_s']) for r in hold])*1000
                ax.plot(t[tail],error[tail],lw=.8,alpha=.8,label=trial['trial_id'].replace('B_GROUND_',''))
        for ax,w in zip(axes.flat,'ABCD'):
            ax.axhline(9,color='black',ls='--',lw=.8,label='Locked +/-5% band')
            ax.axhline(-9,color='black',ls='--',lw=.8)
            ax.axhline(0,color='gray',lw=.5)
            ax.set(title='Wheel '+w,xlabel='Time from HOLD start (s)',ylabel='Raw wheel speed - target (mm/s)')
            ax.grid(alpha=.2);ax.legend(fontsize=7)
        fig.suptitle(family+' — last 2 s raw samples; full 11 s records retained')
        write_figure(fig,WR/'data/summary_figures'/family)
    save(DEST/'preparation_result.json',{'generated_local':NOW,'formal_valid':20,'supplemental_valid':4,'source_files_verified':len(source),'formal_phase_samples':22000,'reports_generated':True})
    print(json.dumps({'formal_valid':20,'supplemental_valid':4,'source_files_verified':len(source),'counts':counts_table},ensure_ascii=False))

if __name__=='__main__':
    main()
