# Linux Codex 接续本次轮速实验

1. 先读 wheel_response/Windows四轮轮速响应测试_执行结果.md（最终回传报告）。
2. 再读 wheel_response/README_Linux回传与复核.md，先核对整包及逐文件SHA256。
3. 论文实测说明在 wheel_response/data/实测结果说明.md；正文候选在 wheel_response/论文第5.3.1节_候选文字.md。
4. 正式选用清单 wheel_response/data/formal_trial_manifest.csv，20次有效、每组n=5；正式指标80行、独立补测指标16行分别在 formal_metrics.csv/supplemental_metrics.csv。
5. 全部原始流、CSV、参数快照、校验、图件、失败和中断都保留。低速落地原正式R05有三轮未稳定；4次补测均未四轮同时满足±5%，必须如实呈现。

本包完整项目可直接浏览。基线bundle不含未提交实验修改；源码补丁和完整快照提供当前实现。不要批量替换原始metadata中的Windows路径，不要把预检/补测混入原n=5，不要自动覆盖Word论文。所有历史状态报告以自身时间戳理解，最终状态以最终回传报告及final_delivery/final_status.json为准。
