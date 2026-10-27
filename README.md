# bpreflight · 条码印前可扫描性审计器

> **生成器是红海，解码器是 oracle。空白在"印出来扫得出吗"这一层。**
> `bpreflight` 从**生成参数**（符号类型、X-dimension、静区、目标 DPI、条/空颜色、条高、放大率）
> 直接判定"这个条码印出来会不会扫不出"，并给出**可执行修复项**——**不依赖图像采集**。

纯本地 CLI：**零网络、零遥测、零第三方运行时依赖**。输入是参数文件，不是图片；输出是
JSON（机器消费）+ Markdown（人读）+ 退出码（接 CI 门禁）。

**状态：M1（数据先行）**。已落盘的是**数据层**：内嵌官方 GS1 AI 字典（commit 钉版、
逐次运行校验哈希）+ **唯一**校验位实现 + 四个语义解释器（`req` / `ex` / `yymmd0` / `csum`）
+ GTIN/SSCC/日期/字符集/长度校验。**M2（符号合法性）与 M3（印刷可读性）未实现**，
报告会在首屏 `SKIPPED:` 一栏里自己说（`module_not_implemented:M2/M3`）——不会让人把
只做了数据层的结论读成"整个条码没问题"。

| 里程碑 | 状态 | 说明 |
| --- | --- | --- |
| M0 | ✅ | 计划套件 + 五道门 + 可运行骨架（本地等价校验，未接远端） |
| M1 | ✅ | 数据层：内嵌官方字典 + 校验位 + 语义解释器（本地等价校验，未接远端） |
| M2 | ⬜ | 符号合法性 |
| M3 | ⬜ | 印刷可读性（差异化核心） |
| M4 | ⬜ | 报告与 CI 门禁 |
| M5 | ⬜ | 栅格化仿真回读（可选） |
| M6 | ⬜ | 发布 |

## 为什么不是又一个生成器

| 层 | 已占位 | 本项目 |
| --- | --- | --- |
| 生成 | JsBarcode / zint / python-barcode / BWIPP | **不做** |
| 解码 | zxing / zxing-cpp / zbar | **不重造**，只在 M5 作可选 oracle |
| GS1 AI 解析 | 官方 `gs1/gs1-syntax-engine`（lint 完整） | **不立项**，只内嵌官方字典驱动 M1（整表当数据读，代码只做四个解释器） |
| **印刷可读性审计** | 几乎空白 | **本项目**：参数域判定 + 可执行修复项 + CI 门禁 |

## 安装（开发态）

```bash
py -3.12 -m pip install -e ".[dev]"
```

不装也能跑（`pytest` 的 `pythonpath` 直指 `src/`）：

```bash
py -3.12 -m bpreflight --help
```

> Windows 上 `python` / `python3` 可能是应用商店占位符（执行即 exit 49）。**一律用 `py -3.12`**；
> 中文输出加 `-X utf8`。`requires-python = ">=3.8"`，由 `tools/check_python_floor.py` 用 AST 守。

## 用法

```bash
bpreflight check --input examples/spec-ean13.json
mkdir -p out && bpreflight check --input examples/spec-ean13.json --json --md
bpreflight report --input examples/spec-ean13.json --format json
bpreflight check --input examples/spec-ean13.json --fail-on=error
```

**输出落点**：`--json` / `--md` 是**开关**，不是路径 —— 它们把报告写到固定的
`out/report.json` 与 `out/report.md`（`oracle` 写 `out/oracle-report.{json,md}`）。
落点不含任何来自命令行的成分，`out/` 必须已存在（不静默建目录，否则 exit 3 且零副作用）。
默认只打 stdout，CI 里 `bpreflight check --input spec.json > out/report.json` 同样可用。

**首屏三段**（顺序与措辞是契约）：

```
VERDICT: pass
FINDINGS: ok=0 info=0 warn=0 error=0
TOP FIX: none
```

下面是**真的会出问题**的输入（校验位错一位 + 月份 13），同样一个命令：

```
VERDICT: fail
FINDINGS: ok=0 info=0 warn=0 error=2
TOP FIX: recompute_check_digit -> 09501101530003 digits
```

**`--fail-on` 默认 `none`**：只报告不拦。要接 CI 请显式写 `--fail-on=error`——
否则你的流水线会一直是绿的。

### 数据层判什么（M1）

| 判据 | 说明 |
| --- | --- |
| 校验位 | 单一实现（`gs1/checksum.py`），四官方向量 `02345673` / `416000336108` / `09501101530003` / `4006381333931` 全 PASS |
| AI 表 | **内嵌官方字典**（Apache-2.0），整表 224 条目 → 541 个具体 AI；代码只做四个解释器，不自造 AI 表 |
| `req` / `ex` | 组合校验：逗号 = 任一组满足（OR），`+` = 同一组全到（AND）；`ex` = 互斥 |
| 日期 | `yymmd0` 允许 **DD=00**（= 当月最后一天，`info` 级并归一化）；月份/天数/闰年交给 `calendar.monthrange` |
| 长度 / 字符集 | 按字典的组件规格（`N14` / `X..20` / `[X..16]`）逐段核对 |

**它不假装会判的东西**（都进首屏 `SKIPPED:`）：`gcppos1/2`（要 GCP 分配库 = GEPIR 联网授权，
属非目标）、字典点名但本棒未实现的 linter、以及 M2/M3 两个未落地模块。

### 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 门槛未触发（`--fail-on=none` 下恒为 0） |
| `1` | 跨门槛且最严重级别为 `warn` |
| `2` | 跨门槛且最严重级别为 `error` |
| `3` | 用法错误 / 输入不可解析 / 内嵌数据缺失（**优先于 0/1/2**） |

口径只在 `data/README.md` §8.5 定义一次，本表是摘要。

### 输入格式

**首期只收 `.json`**，扩展名不符即 exit 3（**不做内容嗅探**）：

```json
{
  "schema": "bpreflight/spec/1",
  "mode": "params",
  "symbol": "ean13",
  "x_dimension_mm": "0.330",
  "target_dpi": 300,
  "quiet_zone_mm": {"left": "3.63", "right": "2.31", "top": "0", "bottom": "0"},
  "bar_height_mm": "22.85",
  "bar_color": "#000000",
  "space_color": "#FFFFFF",
  "illumination": "red",
  "magnification_pct": "100",
  "gs1_element_string": "(01)04006381333931"
}
```

数值一律写成**定点字符串**（避免 JSON 浮点抖动，保证逐字节可复现）。

**数据层面**（M1）二选一，两者都不给就是 `error: input_incomplete`（绝不会静默判成 pass）：

- `gs1_element_string` —— 元素串，两种形态都收：
  `"(01)09501101530003(10)BATCH1"`（HRI 括号形态）或
  `"0109501101530003\u001d10BATCH1"`（FNC1 原生形态，`\u001d` 是 GS）；
- `identifier` —— 裸标识（GTIN-8/12/13/14、SSCC-18），例如 `"09501101530003"`。

## 阈值为什么不是数字，而是数据

印刷阈值（静区模块数、放大率区间、名义 X、条高）本轮**一条都没核实到 GenSpec 原表**
（`gs1.org` / `iso.org` 均 403）。因此它们全部外置成版本化数据文件，每项带四态字段：

```json
{"value": 7, "source": "…", "status": "unverified", "verified_at": null, "basis": "gen-spec"}
```

- `status: unverified` 的项在门禁里**降级为 `warn`**，不拦死别人的流水线；
- `--strict-thresholds` 时恢复 `error`，并在报告首屏打 `THRESHOLDS: unverified (…)`；
- `basis: engineering-heuristic` 的判据（DPI 每模块点数、颜色对比）**没有** `status`，
  不参与降级。

**本工具不把传闻伪装成标准。**

## 开发

```bash
py -3.12 tools/check_sprint_layout.py    # 布局门（方法论装订）
py -3.12 tools/check_desensitized.py     # 脱敏门
py -3.12 tools/check_thresholds.py       # 阈值零硬编码门
py -3.12 tools/check_python_floor.py     # Python 下限门（AST）
py -3.12 tools/verify_gates.py           # 门自检（注入缺陷 → 必须逐条变红）
py -3.12 -m pytest -q                    # 全量测试
```

## 文档索引

| 文档 | 内容 |
| --- | --- |
| `plan/00-README总览.md` | 总览 / 决策记录 / 弃选项 / 承诺-证据台账 |
| `plan/01-题目文档.md` | 题面：痛点、已占位矩阵、五模块任务、评分、边界 |
| `plan/02` – `plan/06` | 架构 / 模块详设 / 数据计划 / 里程碑 / 交付对标 |
| `plan/HANDOFF-M2.md` | 下一棒交接单（当前事实与不动点） |
| `data/README.md` | 依据查证三态 + **数值口径唯一定义（§8）** + 内嵌字典身份（§3.1） |
| `AGENTS.md` | 方法论锚点与门命令 |

## 边界（不做）

不做生成器；不做编解码库；不做纯 GS1 AI 解析器；不做 GTIN/SSCC 主数据一致性（需联网）；
不做图像式 ISO/IEC 15416 ⚠️ 分级；不做色彩管理 / ICC；不做扫描器型号适配；不做 GUI / 服务端。

## 许可证

Apache-2.0（见 `LICENSE`）。内嵌的 GS1 语法字典为 Apache-2.0，其许可、来源 URL 与快照哈希
随字典一同入库：`src/bpreflight/data/gs1-syntax-dictionary/`（`LICENSE` 上游许可 +
`NOTICE` 来源声明 + 正文），字典身份记在 `src/bpreflight/data/vectors/dict_manifest.json`，
每次运行复算 sha256（不符即 exit 3）。
