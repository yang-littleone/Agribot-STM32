# Linux Codex 接续入口

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
