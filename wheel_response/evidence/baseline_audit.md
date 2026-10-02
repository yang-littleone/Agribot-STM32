# 基线核查

原工程保持不变，实验工作树 D:/MCU/STM32/AgriBot-wheel-response，分支 codex/wheel-response，基线 8655eb21f9537f84b5a66effc0fdb085a4993a99。

## git status --short

```text
 M MDK-ARM/AgriBot.uvguix.28047
 M MDK-ARM/AgriBot/AgriBot.axf
 M MDK-ARM/AgriBot/AgriBot.build_log.htm
 M MDK-ARM/AgriBot/AgriBot.htm
 M MDK-ARM/AgriBot/AgriBot_AgriBot.dep
 M MDK-ARM/AgriBot/carcontrol.crf
 M MDK-ARM/AgriBot/carcontrol.o
 M MDK-ARM/AgriBot/data.crf
 M MDK-ARM/AgriBot/data.o
 M MDK-ARM/AgriBot/freertos.crf
 M MDK-ARM/AgriBot/freertos.o
 M MDK-ARM/AgriBot/icm20948.crf
 M MDK-ARM/AgriBot/icm20948.o
 M MDK-ARM/AgriBot/mytask.crf
 M MDK-ARM/AgriBot/mytask.o
 M MDK-ARM/AgriBot/usb_host.crf
 M MDK-ARM/AgriBot/usb_host.o
?? wheel_response/

```
Exit code: 0

## git remote -v

```text
github	https://github.com/yang-littleone/Agribot-STM32.git (fetch)
github	https://github.com/yang-littleone/Agribot-STM32.git (push)
origin	git@gitee.com:yangxyi/AgriBot-stm32-hal.git (fetch)
origin	git@gitee.com:yangxyi/AgriBot-stm32-hal.git (push)

```
Exit code: 0

## git log -5 --oneline

```text
1e408a3 进行IMU九轴融合前的备份工作
8655eb2 完善数据接收，两位uchar转换short再转换float
17c64cc 修正IMU方向x变-y
065220c 开启串口数据发送，修复串口接收长度错误引起的接收bug
c72792d 完成串口数据收发，实现手柄和串口控制

```
Exit code: 0

## git rev-parse --show-toplevel

```text
D:/MCU/STM32/AgriBot/AgriBot

```
Exit code: 0

## git cat-file -t 8655eb21f9537f84b5a66effc0fdb085a4993a99

```text
commit

```
Exit code: 0

## 控制链与实验适配

ARMCC 5.06 update 7 build 960；STM32F407VETx；USART3 115200 8N1 PD8/PD9。
原反馈公式分母 CONTROL_PERIOD=0.01 保留。编码器 A TIM2、B TIM3、C TIM4、D TIM5；C/D取反保留，每周期一次读清零，复制同一次计数供快照。
原 ROS_Control→InverseKinematic→VelocityPIDControl→Set_PWM 保留。原 PI 递推函数仅用数值相同的命名宏替代 16700；系数仅用 800.0f/500.0f 宏替代字面量；Ki不乘周期。原逆解限幅1.0不变。
实验模式通过原 CarControlTask 入口转入相同优先级4、512-word栈、vTaskDelayUntil 10 tick 控制；旧显示、IMU、USB手柄、旧上行任务不创建。独立UART任务优先级3、512-word栈。异常驱动停止只覆盖被执行的软件路径；没有独立硬件看门狗保证。
实验模式 fputc/fgetc 不访问 USART3，旧RX回调编译排除。UART中断优先级5保持；新ISR不用RTOS API。发送缓冲1034 bytes直到TX完成；32×84=2688 bytes采样静态队列，加8×14 ACK缓冲和512-byte RX环，无heap扩容。配置报告实际剩余heap和两个栈高水位。
采用 HAL_GetTick 1 ms时基，mcu_time_us是其整数单位换算后uint32模回卷；不得宣称1 us精度。执行时长和未校准电池电压使用65535。
计数超int16范围则FAULT并零驱动，该样本编码器字段0表示无效，fault标志明确；没有静默取模。
硬件、实际轮号、计数比例、轮径和A/B对应关系尚待实物核验，模板未知项为null。
基线完整重编译日志 baseline.log：0 errors，27 warnings（原工程警告）。后续增量基线构建保存真实exit code与镜像hash。实验编译和烧写状态以各自日志与download_record为准。
Keil命令行依据 https://www.keil.com/support/man/docs/uv4/uv4_commandline.asp 。构建脚本只构建，禁止包含-f下载动作。
