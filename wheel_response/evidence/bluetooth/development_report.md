# JDY-33 蓝牙开发与实测交付

生成时间：2026-10-02T09:32:31.959052+08:00。蓝牙功能已实现、实际下载并通过架空验证；小车最后 30 秒记录保持停止状态。

## 当前连接与固件

- WHEELTEC / JDY-33，Windows 出站 COM13，USART2 PD5 TX / PD6 RX，115200 8N1；USB COM12 备用。
- 底板 P1 与 MCU 网络已核对，证据：`pcb_uart_audit.json`。模块原串口 9600，AT 查询确认已改为 115200。
- 构建 ID `WRS1-a1ee5888c276a89b`，Keil 编译 0 错误、0 警告，真实下载 Verify OK，板端身份匹配。镜像在 `firmware_images`；完整源文件和镜像校验在 `source_verification.json`。
- 四路 PI、编码器和方向沿用架空正式试验版本；正常原工作目录未覆盖。实验目标 WheelResponse 启用本功能。

## 通过的真实检查

| 检查 | 结果 | 记录目录（相对于实验工作树） |
|---|---|---|
| 30 秒、100 Hz 蓝牙连续收数复测 | 3015 样本，0 丢序号、0 CRC 错误、0 队列丢样 | wheel_response/evidence/bluetooth/qualification/LISTEN_20261002_013900_717307 |
| 修正电脑等待确认逻辑后 0.05 m/s 架空预检 | PRE/HOLD/POST = 100/100/300 样本，整个采集 1862 样本校验通过，最终反馈及输出归零 | wheel_response/data/B_AIR_BT_PRE050_RETEST02_20261002_092610_243120 |
| 零输出 ARMED 状态失联保护、USB 备用 ABORT | 两项均通过，所有目标、PWM、反馈为零；没有发送 START | wheel_response/evidence/bluetooth/ZERO_ARMED_SAFETY_20261002_013648_346412 |
| USB 零输出重新配置 JDY-33 | AT 验证通过，随后蓝牙重新连接成功 | wheel_response/evidence/bluetooth/BT_SETUP_20261002_092658_446522 |
| 最后 30 秒蓝牙收数及零输出检查 | 3016 样本，0 丢序号、0 CRC 错误、周期均为 10000 us，目标/PWM/反馈全为零 | wheel_response/evidence/bluetooth/qualification/LISTEN_20261002_092740_336178 |
| 自动检查 | 15 项通过，包括协议、通道归属、AT 流程、完整性中止和等待输入持续收数 | wheel_response/evidence/bluetooth/software_tests.log |

## 保留的失败记录与修正

首轮连续收数 `LISTEN_20261002_013124_612949` 有 1 次 CRC 错误、12 个缺失序号，判定不通过；没有纳入通过记录。先前空闲重连引起的 UART 故障及低波特率诊断失败亦保留。

首次蓝牙动力预检 `B_AIR_BT_PRE050_20261002_014353_625653` 的 500 个运行阶段样本完整，但整份采集有 CRC/帧间噪声错误，且等待输入 START 时缺失 1953 个 IDLE 样本。原因是原电脑工具阻塞等待输入，未持续读取蓝牙。已改为持续收数并请求 64 KiB 接收缓冲；新的独立预检通过全记录校验。运行中发现丢帧或 CRC 错误会中止并尝试 ABORT，原始失败数据仍保存。

`B_AIR_BT_PRE050_RETEST01_20261002_015131_039932` 在等待 START 时电脑会话结束，未发送 ARM/START，登记为中断。没有以该记录冒充完成试验。`RETEST02` 使用独立编号完成复测。

通过的短预检用于证明蓝牙链路可执行并记录四轮运动，保持段仅 1 秒，不据此声称速度已充分稳定。零输出安全检查证明状态保护逻辑，未代替运行中的物理急停测量。无线链路仍可能受环境影响，因此保留原始校验、运行中中止和失联归零机制。

## 交付范围

使用方法见 `wheel_response/README_Bluetooth.md`。源码、Keil 工程、最终 HEX/AXF、电脑工具、自动检查、全部本次蓝牙原始记录与 SHA256 清单随开发包交付。原十次架空正式结果的旧固件身份和既有交付包保留；蓝牙预检不混入正式基线。落地、距离及长时间干扰验证尚未进行。
