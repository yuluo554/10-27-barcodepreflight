# AGENTS.md

本仓库遵循 **`ai-tool-project-sprint`** 方法论（装订日期：2026-10-27）。

## 任何新对话的第一件事

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门；必须绿，红了先修布局再干活
```

- 续接对话：读 `plan/HANDOFF-M<k>.md`（那是第 k 棒的收尾交接单），**先跑上面这条门**。
- 接手对话（无 HANDOFF）：先读 `plan/00`、`plan/05`、`plan/06` 与各 HANDOFF，重建
  "当前状态 + K 口径清单"再动手。
- **门不存在 = 本项目没装订** → 先补第零步三件（本文件 + 布局门 + `plan/00` 顶部装订行），再做别的。

## 强制布局（布局门逐条断言，改动前先看这里）

| 项 | 位置 | 判据 |
| --- | --- | --- |
| 计划套件 | `plan/00`–`plan/06` + `data/README.md` | 存在且各含必需小节（标题关键词） |
| 数据台账 | `data/README.md` | 依据查证记录 + 数值口径两节在位 |
| 交接单 | `plan/HANDOFF-M<k>.md` | 每个 ✅ 里程碑一份（含收尾棒），**七节**齐（含"当前事实·状态不变量"） |
| 里程碑状态副本 | `plan/00` 里程碑表 + `plan/00` 承诺-证据台账 + `plan/05` 状态表 + `README.md` 状态表 | **逐处一致**，枚举式断言；副本必须是**表格行**才可机读 |
| 发布留档 | `plan/RELEASE-M<last>.md`（两栏）或 `plan/WRAPUP-M<n>.md` | 发布里程碑 ✅ 之后才要求存在，未 ✅ 时报 PASS 并写明不适用 |
| 发布门覆盖对账 | `plan/RELEASE-M<last>.md` §覆盖对账 | 阶段 7 出口门逐条：实现 / 不适用+理由 / 待首推 |
| 文档点名的工具 | `tools/*.py` | 文档里出现 `tools/<name>.py` 形式的路径就必须有实物（或登记在布局门的 `PENDING_TOOLS` 里） |

## 门命令一览

| 门 | 命令 | 作用 |
| --- | --- | --- |
| 布局门 | `py -3.12 tools/check_sprint_layout.py` | 方法论装订是否还在 |
| 脱敏门 | `py -3.12 tools/check_desensitized.py` | 入库文本无本机盘符 / 用户名 / 回环代理 |
| 阈值零硬编码门 | `py -3.12 tools/check_thresholds.py` | `src/` 无裸阈值字面量 |
| Python 下限门 | `py -3.12 tools/check_python_floor.py` | 语法未越过 `requires-python` 下限 |
| CI 工作流门 | `py -3.12 tools/check_ci_workflow.py` | 工作流 YAML 留在可解析子集；门各自独立 step；矩阵含 3.8/3.12 |
| 门自检（变异验证） | `py -3.12 tools/verify_gates.py` | 逐条注入缺陷，必须逐条变红 |
| 全量测试 | `py -3.12 -m pytest -q` | 单测与集成 |

CI 里这六条每条都是独立 step（见 `.github/workflows/ci.yml`）。

## 环境事实与禁忌（只写实测过的）

- 本机 **`python` / `python3` 是 Windows Store 占位符**（执行即 exit 49）。**一律用 `py -3.12`**；
  跑脚本带 `-X utf8`（中文控制台编码）。已实测：`py -3.12` = 3.12.10，`py -3.8` = 3.8.8。
- `requires-python = ">=3.8"`：**新语法（`match` / `X | Y` 注解 / 内建泛型注解）不得进 `src/`**，
  由 `tools/check_python_floor.py` 走 AST 拦。
- 运行时**零第三方依赖、零网络**：`src/bpreflight/` 只准 import 标准库；`tests/test_no_network.py`
  走 AST 扫网络模块。
- 禁止：把"未执行"写成已完成；在 tag 之后改代码面；把绝对路径写进入库文件
  （用法行写相对路径，绝对路径只出现在用户侧启动命令里）。
- **内嵌官方字典是唯一第三方数据**（`src/bpreflight/data/gs1-syntax-dictionary/`，Apache-2.0）。
  改动它等于改数据基座：必须同步 `src/bpreflight/data/vectors/dict_manifest.json` 的 `sha256`
  与 `dict_version`（否则每次运行都会因摘要不符 exit 3）与 `NOTICE`。
  复算：`py -3.12 -c "import hashlib,io;print(hashlib.sha256(io.open('src/bpreflight/data/gs1-syntax-dictionary/gs1-syntax-dictionary.txt','rb').read()).hexdigest())"`
- **跑 CLI 要 `PYTHONPATH=src`**（或先 `pip install -e .`）：`py -3.12 -m bpreflight` 不会
  自动看见 `src/` —— `pyproject.toml` 里 `pythonpath` 只对 pytest 生效。
