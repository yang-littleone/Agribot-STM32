# 蓝牙架空安全预检实测结果

记录时间：2026-10-02T10:41:23.863038+08:00

当前固件 WRS1-b87ba230e207f646，JDY-33 蓝牙 COM13；车仍架空。两次预检均使用 0.05 m/s，PRE 1 秒；分别在 HOLD 约 0.5 秒主动急停、START 后约 2 秒停止心跳。

|预检|结果|预期故障位|连续故障状态观察|PC 发送到收到首个故障样本|
|---|---|---|---|---|
|主动急停|通过|2|136 样本 / 1.35 秒|79.5 ms|
|停止心跳自动停车|通过|1|132 样本 / 1.31 秒|558.6 ms|
PC 时间间隔分别从 ABORT 发送、最后一次 HEARTBEAT 发送算起，包含蓝牙传输和接收缓冲，不能作为主控内部精确响应时间。

两次均只有预期故障；故障期间四路目标速度和 PWM 全为零，末尾反馈进入预先固定的零速带。原始字节与 CSV 相符，文件哈希和固件身份检查通过；无帧校验错误、序号缺失或队列丢样，控制周期均为 10 ms。

这是故意中断正常阶段的安全试验，普通完整轮速试验校验记录保持 limited，不纳入正式响应统计；独立安全复核通过，原始记录全部保留。

清除两次已确认的故障后，又采集 519 个静止样本（约 5 秒）：全程 IDLE、故障位为零，四路目标速度、反馈和 PWM 均严格为零。

静止电池电压名义估计：中位 12.171 V，范围 12.135–12.206 V；来自 MCU ADC，尚未独立标定。

最终静止复核第一次开蓝牙口遇到设备未连接，未发送运动命令；失败记录保留，随后重新连接的完整复核通过。

落地试验尚未启动。下一步为五米以上瓷砖场地的落地低速预检，需要现场将车放下、摆正，移除随车连接的 ST-Link 排线，并确认前方有效直线距离。

## 原始记录

- [B_AIR_BT_ADC_ABORT050](D:/MCU/STM32/AgriBot-wheel-response/wheel_response/data/B_AIR_BT_ADC_ABORT050_20261002_103343_324680/safety_validation.json)

- [B_AIR_BT_ADC_HEARTBEAT050](D:/MCU/STM32/AgriBot-wheel-response/wheel_response/data/B_AIR_BT_ADC_HEARTBEAT050_20261002_103809_642888/safety_validation.json)

- [最终静止复核](D:/MCU/STM32/AgriBot-wheel-response/wheel_response/evidence/battery/AIR_safety_final_zero/LISTEN_20261002_103938_257073/validation.json)
