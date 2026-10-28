"""M5 · 仿真回读层（`oracle/`，可选）。

`plan/01` §M5 的口径：**只做一致性对照，不改 M3 判定**（`plan/00` D10）。

| 文件 | 职责 |
| --- | --- |
| `layout.py` | 装载模块图案表（`data/vectors/sampler_patterns.json`），把 M2 的字符流变成模块行 |
| `sampler.py` | **纯函数**采样器：`(plan, x_mm, dpi, colors) -> 灰度位图`（无随机、无抗锯齿、不读文件） |
| `zxing.py` | 外部解码引擎探测 + 调用（`shutil.which` + 子进程；**不 import 任何解码库**） |
| `agreement.py` | `agreement` 三态的**纯分类器**（`m3_stricter` 入 known-disagreements；`m3_laxer` 入 bug 通道） |
| `audit.py` | 编排：前提检查 → 采样 → 回读 → `OracleResult`（JSON/MD 两个渲染） |

三条结构纪律（与 M1–M3 同款，`plan/HANDOFF-M5` §二）：

1. **零第三方依赖 + 零网络是红线**（K11）：本层只 import 标准库；解码引擎只能通过
   **外部命令**探测（`tests/test_no_network.py` 的第三方 import 判据自动覆盖本目录）。
2. **采样器是纯函数**：同输入两次调用字节相等；不读数据文件（图案表由编排层装载后传入）。
3. **不伪造结论**：引擎缺失 / 引擎不可用 / 图案表不支持 / 前提不全 —— 一律走
   `skipped`，**不产出** `agreement`，也不把"没跑"写成"通过"（`data/README.md` §8.9 G6）。
"""