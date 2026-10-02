# Windows四轮响应实验

实验工作树：`D:\MCU\STM32\AgriBot-wheel-response`；分支 `codex/wheel-response`。
基线：`8655eb21f9537f84b5a66effc0fdb085a4993a99`。原工程未覆盖。

2026-10-02 已新增 JDY-33 蓝牙 SPP 通信并下载实测，使用 WHEELTEC 出站 COM13 / 115200，可通过 `--port auto` 选择；USB COM12 保留。操作和验证范围见 [README_Bluetooth.md](README_Bluetooth.md)。原正式架空结果按原固件身份保留，新增蓝牙预检单独登记。

落地方案已按用户提供的至少 5 米瓷砖直线场地重写，见 [完整落地实验](完整落地轮速响应实验_5米瓷砖地面.md)。原 3 米场地方案未执行，已保留为历史准备记录。正式落地两档各 5 次仍为 planned，新增预检独立编号；操作者实际摆车后再登记落地就绪。

2026-10-02现场执行补充：用户明确确认小车持续架空，并授权直接完成架空测试，无需逐次询问效果。各次仍独立发送START，上一试次结束并通过数据及最终零输出核查后再启动；异常时停止继续。授权原文在evidence/continuous_air_authorization.json，替代本次架空重复试验的逐次口头确认。落地需要操作者重新布置现场。review_air_trial.py只分析已保存记录，不发送任何串口命令，也不按性能优劣删除试次。

## 固件和软件

正常工程 `MDK-ARM/AgriBot.uvprojx` 的实验开关默认关闭。实验工程 `MDK-ARM/WheelResponse.uvprojx` 唯一目标为 `WheelResponse`，输出 `MDK-ARM/WheelResponse/WheelResponse.hex` 和 `.axf`。
固件保留原四路增量式PI与速度计算、逆解及驱动方向：Kp=800、Ki=500，PWM限幅16700，名义10 ms；Ki不再乘周期。实验控制任务沿用原入口、优先级、栈大小和周期；遥测任务独立，旧显示/IMU/USB遥控/业务发送任务不创建。
时间分辨率1 ms，时间字段以us单位表示。执行时长与未校准电池电压字段65535表示不可用。32个样本的静态FIFO，不扩容RTOS heap。软件心跳超时不构成独立硬件看门狗保证。

```powershell
Set-Location 'D:\MCU\STM32\AgriBot-wheel-response'
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\wheel_response\requirements.txt
py -3 .\wheel_response\tools\build_firmware.py
.\.venv\Scripts\python.exe -m unittest discover -s .\wheel_response\tests -v
```

构建只编译，不烧写。构建ID由固件源文件清单派生，最终镜像hash在PC归档；板端GET_CONFIG返回构建ID，需与真实下载记录匹配。

## 物理检查与下载

B平台已由用户报告架空，控制板和电机已上电。实际支撑方式、芯片、电机、轮号、轮径、计数比例和A/B对应关系仍需逐项记录。USB串口已识别为CH9102 COM12。
核对板端PD8/TX→转换器RX、PD9/RX←转换器TX和共地，确认逻辑电平及原有供电方案。下载前确认四轮可靠架空或电机供电断开；不要凭排针位置猜MCU引脚。
独立下载脚本只在用户明确就绪后使用，固定目标B；不会ARM/START。

```powershell
py -3 .\wheel_response\tools\download_firmware.py --robot B --physical-ready
```

下载后记录Keil日志，并用板端GET_CONFIG验证身份，再更新 `download_record.json` 的 `board_identity_verified` 和检查记录路径。脚本中的下载成功不等于已完成身份核验。
也可在Keil打开实验工程，选择WheelResponse目标，在ST-Link设置中确认芯片和下载算法后下载同一镜像；手动下载必须归档下载日志及镜像hash。

## 首次静态核验

关闭其他串口助手，单进程使用COM12。先读取身份/配置，不发运动指令：

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py list-ports
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py inspect --port COM12
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py listen --port COM12 --duration 30
.\.venv\Scripts\python.exe .\wheel_response\tools\validate_data.py '上条命令显示的实际目录'
```

静态记录保存在evidence/static_checks，不作为正式轮速试次。维持未ARM，逐轮手动转动，按控制任务记录的同一次计数累加确认轮号、前进方向及输出轴完整圈计数；用照片记录，实测轮径。不得新增任务读清零编码器。
将核验写入config/hardware_manifest.json。未知值保持null，不把源码常量填成实测值。

## 单次预检

每次运行要求实际操作者名称，并要求交互输入 `START <试次ID>`；不会自动连跑。先完成低速、急停、停止心跳和可达性预检，再进行正式20次。

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py run --port COM12 --trial B_AIR_PRE050 --operator '实际操作者姓名'
```

q或Ctrl+C直接ABORT；s提前进入POST（标记人为停止）。原始接收字节、实际确认发送字节、命令日志、CSV及metadata同步保存。串口断线的急停投递失败会记录，MCU心跳500 ms超时负责失联停止，实际响应还受控制调度影响。
主要急停由run会话处理，不能用另一个程序抢占同一COM口。串口无人占用时，可用独立abort命令。
FAULT排除原因后再发送CLEAR_FAULT；程序不会自动解除故障或续跑。

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py clear-fault --port COM12 --reason '实际排除故障的过程'
```

此命令读取当前故障位并要求输入CLEAR_FAULT，只恢复IDLE，不启动电机。

## 正式计划与分析

experiment_plan.json登记20次正式试次、6个单独编号预检。每个正式试次PRE/HOLD/POST为300/500/300周期。已运行试次不能覆盖；补测需先在计划和登记表新增独立run_id和RETEST编号。每次结束后重新摆车、检查线材/温度/电压并重新确认。
正式试验前将验证过的每轮量化分辨率和零速带写入metric_definition.json，并固定locked_before_formal_measurement；不能看结果后改带宽。无实物校准时调节时间保持空值，不假称精度。

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py analyze .\wheel_response\data
```

指标逐轮逐次输出，汇总按条件/速度/轮号n=5，使用样本SD，不将同一次四轮视作独立重复。无阈值交点、未调节、关键缺口均留空附原因。图件为原始曲线PNG+SVG，不平滑、不补样、不平移。
合成测试仅保存在tests，不得移入真实data或论文。
基线数据质量判定不按误差大小筛选；反馈跳变阈值仅提示人工核验，不据此自动删性能差的试次。

## 归档与恢复

保留整个wheel_response目录、实验源文件、实验Keil工程、source_manifest、patch、HEX/AXF、构建/下载日志和所有原始数据。恢复原参考固件可使用evidence/baseline_images中的镜像，但该镜像仅为已编译参考基线，不能假称是读回的烧写前板上镜像。
Linux接收整个证据与data目录以及实验分支/源码补丁；原始记录保持不变。执行结果报告会注明已完成和待操作项目。

## 主动急停预检入口

仅登记的预检可使用 `--abort-hold-ms 1000`，表示收到HOLD阶段首样本后，按板载展开时间经过1000 ms发送一次ABORT。`--heartbeat-loss-at 2`按电脑START应答后的时间停止发送心跳。两种测试各自单次启动，必须事先确认架空、监护和试次目的；不用于正式性能记录。故障后额外保留1.3 s遥测，预期故障试次用safety_validation.json单独核查停车；不能把其不完整HOLD/POST当作正常停车指标。

## 手动输出轴整圈计数核验

在IDLE/COMPLETE零驱动状态使用listen，新增`--end-on-key`允许按q正常结束只读采集。只发送HELLO/GET_CONFIG，不发送ARM/START。操作者先做轮胎/车架对齐标记，收到采集已就绪通知后，仅按前进方向缓慢转目标轮完整一圈，停稳并确认实际圈数。用`check_manual_turn.py 目录 --wheel A --turns 1 --operator-confirmed`核对原始字节、CSV、零驱动与净计数；不增设编码器读取任务，不使用绝对计数总和替代净位移。手动标记一圈为比例核对，不声称仪器级精度。额外触动其他轮时保留完整轨迹和操作者说明，独立轮号检查的失败不能隐藏。
