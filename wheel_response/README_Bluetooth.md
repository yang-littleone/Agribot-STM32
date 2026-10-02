# JDY-33 蓝牙连接与轮速采集

已在实际小车上完成开发和下载。Windows 连接名称为 WHEELTEC，使用经典蓝牙 SPP **出站 COM13**，模块与主控串口为 **115200、8N1**。原 USB 串口 COM12 仍可使用。COM14 是入站端口，不用于本采集工具；WHEELTEC-IOS 是另一种 BLE 接口，本次未使用。

代码位于 `D:\MCU\STM32\AgriBot-wheel-response`，分支 `codex/wheel-response`，Keil 工程为 `MDK-ARM/WheelResponse.uvprojx`，目标为 WheelResponse。原工作目录 `D:\MCU\STM32\AgriBot\AgriBot` 未被这次蓝牙开发覆盖。普通 AgriBot 目标未启用这套实验通信功能；要使用本次实现，请下载 WheelResponse 目标。

## 电脑连接

关闭占用 COM13 的串口助手。在实验工作目录执行：

```powershell
Set-Location 'D:\MCU\STM32\AgriBot-wheel-response'
# 查找已配对 WHEELTEC 的唯一出站端口
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py bluetooth-port
# 读取固件身份和配置，不启动电机
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py inspect --port auto
# 零驱动连续采集 30 秒，并保存结束时的串口诊断
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py listen --port auto --duration 30 --end-config
```

`--port auto` 根据 Windows 已配对设备查找 WHEELTEC 的出站 SPP 端口；也可明确填写 `--port COM13`。工具不会自动配对或选取入站端口。换电脑后端口编号可能不同。实际输出目录内包含原始收发字节、逐周期 CSV、配置、命令和元数据；用下面的命令验证该目录：

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py validate '实际输出目录'
```

## 执行已登记的轮速试验

蓝牙沿用原 WRS1 命令和数据格式，使用已登记、尚未执行的试次。不要复用已完成或失败的试次编号。落地试验前仍需操作者布置场地；本次只进行了架空蓝牙预检。

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py run --port auto --trial '已登记且未执行的试次编号' --operator '现场操作者姓名'
```

工具会显示速度与持续时间，等待输入 `START 试次编号`。等待期间持续接收遥测，避免蓝牙缓存积压。输入后仅启动该次试验；运行时按 `q` 或 Ctrl+C 发送急停，按 `s` 提前进入正常停车段。急停使固件进入 FAULT，需要排除原因并明确清故障后才能再次运行。独立急停命令：

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py abort --port auto
```

在 IDLE、COMPLETE 或 FAULT 状态，有效 HELLO 可选定 USB 或蓝牙作为本次通信通道。ARMED、运行和停车段不允许切换控制来源；另一通道的心跳不能延长当前试验。两通道均可发送 ABORT。主控保留 500 ms 心跳超时归零输出；电脑发现运行中 CRC 错误、帧间异常字节、序号缺失或重启，会中止采集并尝试发送 ABORT，保留失败记录，不补帧、不插值、不计入正式有效试次。急停发送失败会记录未确认状态，主控仍执行原有失联逻辑。

## 底板接口与模块设置

已只读核对用户提供的 `.epro2` 底板工程。P1 的连接如下，供电说明针对当前底板上的模块载板接口：

| P1 引脚 | 底板网络 | 用途 |
|---|---|---|
| 1、6 | 无连接 | 未使用 |
| 2 | 5V | 模块载板供电 |
| 3 | GND | 共地 |
| 4 | PD6 | 主控 USART2 RX，接模块 TX |
| 5 | PD5 | 主控 USART2 TX，接模块 RX |

实测模块原串口为 9600；已识别 JDY-33 的 AT 版本响应后设置为 115200，并查询得到 `+BAUD=8`。固件启动时在电机零输出状态进行有界检测；会断开现有蓝牙连接以进入 AT 设置，随后可重新连接。没有修改设备名称、配对密码或恢复出厂设置。

如更换模块，可在停止状态通过 USB 重新检测和配置：

```powershell
.\.venv\Scripts\python.exe .\wheel_response\tools\wheel_response_cli.py configure-bluetooth --port COM12
```

此命令只允许 USB、零驱动状态使用，设置期间禁止 ARM，可能暂停诊断遥测；该记录不作为轮速性能试次。固件还保留低波特率诊断操作，低于 115200 时禁止从蓝牙 ARM；日常采集无需使用这些操作。

制造商提交的 [JDY-33 使用手册](https://fccid.io/2AXM8-JDY-33/User-Manual/15-JDY-33-UserMan-US-r2-4936883.pdf) 列出了 SPP、串口波特率和 AT 命令。接口映射的本地证据在 `evidence/bluetooth/pcb_uart_audit.json`。

## 已完成的验证及范围

当前板端构建 ID 为 `WRS1-b87ba230e207f646`，在原蓝牙版本 `WRS1-a1ee5888c276a89b` 上增加后台 ADC 电压估计。实际 Keil 下载和 Verify OK 日志、镜像 SHA256、板端身份核验均已保存。四路 PI 参数、编码器计数方式、轮号和方向未改变：A 左后、B 左前、C 右前、D 右后。

电压字段现在采用原 PB0 ADC1_IN8 的名义 3.3 V 参考及 11 倍分压公式，每 100 ms 在后台发起非阻塞转换。轮速控制只读取缓存，电压过期或转换失败仍为 65535；该值不是 65.535 V。读数尚未独立校准，方法与实板记录见 `evidence/battery/README_voltage.md`。旧数据中的无效电压不回填。

实测已通过 30 秒、100 Hz 蓝牙连续收数，0.05 m/s 架空短预检，以及零输出 ARMED 状态下的失联和 USB 备用急停检查。后者没有发送 START，验证的是通信及状态保护逻辑，不冒充运行中的物理停车测量。早期丢帧、空闲重连故障、等待启动时缓存溢出的记录均保留；空闲蓝牙错误与运行故障处理已区分，等待输入改为持续收数，并请求 Windows 64 KiB 接收缓冲。请求缓冲大小不等同于驱动保证。

实测结果及失败记录索引见 [开发报告](evidence/bluetooth/development_report.md)。先前十次正式架空试验属于旧固件，原交付归档保留；本次蓝牙预检不混入旧正式结果。尚未执行落地、无线距离或长时间抗干扰试验。
