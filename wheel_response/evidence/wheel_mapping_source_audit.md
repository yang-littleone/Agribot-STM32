# 轮位与方向代码核查（2026-10-01）

最终轮位由用户更正后确认，以Motor.c第3行注释为准：A左后、B左前、C右前、D右后。
原工程与实验基线同一通道顺序，未交换任何通道或增加取反。

| 字段 | 用户确认位置 | 编码器及引脚 | PWM驱动通道及引脚 | 反馈/输出符号适配 |
|---|---|---|---|---|
| A | 左后 | TIM2 CH1 PA15 / CH2 PB3 | TIM11 CH1 PB9 / TIM10 CH1 PB8 | 均不取反 |
| B | 左前 | TIM3 CH1 PB4 / CH2 PB5 | TIM9 CH1 PE5 / CH2 PE6 | 均不取反 |
| C | 右前 | TIM4 CH1 PB6 / CH2 PB7 | TIM1 CH2 PE11 / CH1 PE9 | 编码器和PWM输入分别取反 |
| D | 右后 | TIM5 CH1 PA0 / CH2 PA1 | TIM1 CH4 PE14 / CH3 PE13 | 编码器和PWM输入分别取反 |

依据：原工程 Hardware/Motor.c、Hardware/Encoder.c、Core/Src/tim.c、System/CarControl.c。
Encoder_GetCount对A/B保留原计数，对C/D返回相反计数；每次读取后清零。
Set_PWM对C/D控制输入作方向适配。两处取反服务于不同信号，实验采集层不得再取反。
逆解A/B=v-w*(轮距+轴距)/2，C/D=v+w*(轮距+轴距)/2；按用户实际轮位左右分组一致。w=0正向试验时四轮实际目标相同。
四轮反馈各自进入对应PI，四路PWM按A/B/C/D传递给Set_PWM，无额外交换。
Motor.c第3行与CarControl.c的前后位置注释与用户最终确认一致。此前将注释称为旧注释的判断已撤回；更正记录保存在hardware_manifest的history字段。
轮位登记依据用户确认，不伪称已完成手转实测或拍照。方向实现已完成代码核查，实际运动方向尚待单次0.05 m/s预检记录。
保持编码器换算、PI算法及系数、引脚与驱动全部不变；本轮不烧写、不启动电机。
