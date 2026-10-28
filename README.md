# bpreflight · 条码印前可扫描性审计器

> **生成器是红海，解码器是 oracle。空白在"印出来扫得出吗"这一层。**
> `bpreflight` 从**生成参数**（符号类型、X-dimension、静区、目标 DPI、条/空颜色、条高、放大率）
> 直接判定"这个条码印出来会不会扫不出"，并给出**可执行修复项**——**不依赖图像采集**。

纯本地 CLI：**零网络、零遥测、零第三方运行时依赖**。输入是参数文件，不是图片；输出是
JSON（机器消费）+ Markdown（人读）+ 退出码（接 CI 门禁）。

**状态：v0.1.0 · 五层已交付**（M1 数据层 / M2 符号层 / M3 印刷层 / M4 报告层 / M5 回读层）。
已落盘 **M1**（内嵌官方 GS1 AI 字典 + **唯一**校验位实现 + 四个语义解释器 `req` / `ex` / `yymmd0` / `csum`）、
**M2**（八符号 profile 数据表 + 字符集/长度/模式三段判定 + `encoding_plan` 切分唯一）、
**M3**（静区 / 放大率 / DPI 混叠 / 条高 / 颜色 五项检查 + `fix` 必填 + 阈值三态）、
**M4**（退出码 12 格逐格 + JSON/MD 同源 + 首屏三段顺序锁死 + 渲染层零判定）与
**M5**（纯函数采样器 + 外部解码引擎探测 + `agreement` 三态；**本机没有解码引擎**，因此
`oracle` 一律如实报 `skipped: oracle_absent`）。报告会在首屏 `SKIPPED:` 一栏里如实登记
不可判的项。符号规则与印刷阈值本轮**全部 `unverified`**（未取到规范原文 / GenSpec 原表），
由它们派生的判定默认降级为 `warn`，`--strict-thresholds` 恢复 `error`；
**DPI 混叠与颜色两项是工程判据，不参与降级**。

> 发布状态（是否已发布、CI 是否绿、附件与校验和）看 **Release 页**与 `plan/RELEASE-M6.md`；
> 本文件是随包文档，不自称发布进度。

| 里程碑 | 状态 | 说明 |
| --- | --- | --- |
| M0 | ✅ | 计划套件 + 五道门 + 可运行骨架（本地等价校验，未接远端） |
| M1 | ✅ | 数据层：内嵌官方字典 + 校验位 + 语义解释器（本地等价校验，未接远端）；另补第六道门 `check_ci_workflow.py`（CI 工作流 YAML 可解析性） |
| M2 | ✅ | 符号层：八符号 profile（全部 `unverified`）+ 三段判定 + `encoding_plan`（本地等价校验，未接远端） |
| M3 | ✅ | 印刷层：五项检查 + 边界值逐条 + `fix` 必填 + 未核降级 + `gen_fixtures.py`（本地等价校验，未接远端） |
| M4 | ✅ | 报告与门禁：退出码 12 格逐格 + 端到端 JSON/MD 同源 + 首屏三段顺序锁死 + 渲染层零判定 + `--with-timestamp`（本地等价校验，未接远端） |
| M5 | ✅ | 回读层：纯函数采样器 + 模块图案表 + 外部解码引擎探测 + `agreement` 三态（本地等价校验，未接远端）；缺引擎一律 `skipped: oracle_absent`，不伪造实测结论 |
| M6 | ✅ | 发布：annotated tag `v0.1.0` + GitHub Release（`sdist` / `wheel` / `SHA256SUMS`）+ `plan/RELEASE-M6.md`（两栏 + 阶段 7 覆盖对账） |

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

## 下载即用（Release 附件）

Release 页附三件：`bpreflight-0.1.0-py3-none-any.whl`（**推荐**：字典 / 向量 / 图案表随包安装）、
`bpreflight-0.1.0.tar.gz`（含 `plan/` 与六道门，解包即可跑 `pytest`）、`SHA256SUMS`。

```bash
py -3.12 -m pip install bpreflight-0.1.0-py3-none-any.whl
bpreflight --version
```

校验（Git Bash / Linux / macOS 用第一条，Windows `cmd` 用第二条）：

```bash
sha256sum -c SHA256SUMS
certutil -hashfile bpreflight-0.1.0-py3-none-any.whl SHA256
```

两个摘要也逐行列在 **Release 正文**里（与附件同页）。**包内文档不重复写摘要**——
写进包里的摘要会随"写它这个动作"立刻过期；`SHA256SUMS` 与本文件的附件名由
`tests/test_cli_contract.py` 断言与当前版本一致（版本升了忘改这里会红）。

## 用法

```bash
bpreflight check --input examples/spec-ean13.json
mkdir -p out && bpreflight check --input examples/spec-ean13.json --json --md
bpreflight report --input examples/spec-ean13.json --format json
bpreflight check --input examples/spec-ean13.json --fail-on=error
mkdir -p out && bpreflight oracle --input examples/spec-ean13.json
```

**输出落点**：`--json` / `--md` 是**开关**，不是路径 —— 它们把报告写到固定的
`out/report.json` 与 `out/report.md`（`oracle` 写 `out/oracle-report.{json,md}`）。
落点不含任何来自命令行的成分，`out/` 必须已存在（不静默建目录，否则 exit 3 且零副作用）。
默认只打 stdout，CI 里 `bpreflight check --input spec.json > out/report.json` 同样可用。
`oracle` 的退出码沿用主报告的 `--fail-on`（缺引擎**不是**用法错误，也不是 exit 3）。

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

**报告默认不读时钟**：同一输入两次导出逐字节一致。需要时间信息时用 `--with-timestamp`，
报告头标 `deterministic: false` 并给出 `timestamp`，格式固定
`YYYY-MM-DDTHH:MM:SSZ`（ISO-8601 / **UTC**，句尾字面 `Z`）——**不含**本机时区名或主机名，
否则同一份 spec 换个时区就会产出不同报告。

### 数据层判什么（M1）

| 判据 | 说明 |
| --- | --- |
| 校验位 | 单一实现（`gs1/checksum.py`），四官方向量 `02345673` / `416000336108` / `09501101530003` / `4006381333931` 全 PASS |
| AI 表 | **内嵌官方字典**（Apache-2.0），整表 224 条目 → 541 个具体 AI；代码只做四个解释器，不自造 AI 表 |
| `req` / `ex` | 组合校验：逗号 = 任一组满足（OR），`+` = 同一组全到（AND）；`ex` = 互斥 |
| 日期 | `yymmd0` 允许 **DD=00**（= 当月最后一天，`info` 级并归一化）；月份/天数/闰年交给 `calendar.monthrange` |
| 长度 / 字符集 | 按字典的组件规格（`N14` / `X..20` / `[X..16]`）逐段核对 |

**它不假装会判的东西**（都进首屏 `SKIPPED:`）：`gcppos1/2`（要 GCP 分配库 = GEPIR 联网授权，
属非目标）、字典点名但未实现的 linter，以及符号层的三条
（`symbol_not_specified` / `symbol_data_unparsed` / `gs1_2d_fnc1_not_modelled`）。

### 符号层判什么（M2）

| 判据 | 说明 |
| --- | --- |
| 字符集 ⊆ | 每个字符都必须落在目标符号某个模式的字符集里（EAN-13 只收数字、Code 39 不收小写） |
| 长度 ∈ | 定长符号（EAN-8 / EAN-13 / UPC-A）必须精确匹配；变长符号落在数据文件的 `[min, max]` |
| 模式可覆盖 | 贪心 **longest-first** 切分；同长时按数据文件里的模式优先级 |
| `encoding_plan` | `{symbol, mode, segments[], total_modules, checksum, tie_break}`；**不可编码时不输出半个计划**，原因进 findings |
| 零售 GTIN | `(01)` 是 GTIN-14；去掉**真实的前导零**才是 EAN-13 / GTIN-12 / GTIN-8 形态（结构原因，不写"国家前缀"） |

跨符号等价性三例（`tests/test_symbols.py` 逐条断言原因）：

```
012345678905   -> upca PASS；ean13 不可（12 位 ≠ 13）
0012345678905  -> ean13 PASS；upca 不可（13 位 ≠ 12）
00012345678905 -> 三只零售符号都不可（14 位）；gs1-128 可承载
```

符号规则同样是**数据**：`src/bpreflight/data/vectors/symbol_profiles.json`，每条带
`source` / `status` / `verified_at`。本轮没有取到任何符号规范原文 ⇒ **全部 `unverified`**，
判定降级为 `warn`；`--strict-thresholds` 恢复 `error`。校验位仍只有一份实现
（`gs1/checksum.py`），M2 只调用不复制。

### 印刷层判什么（M3）

| 判据 | 说明 |
| --- | --- |
| 静区 | `qz_modules = quiet_zone_mm / x_dimension_mm`，**三档**：零静区（`required` 侧）恒 `error`、低于 `modules_min` 随 `status`、贴近下限 `warn` |
| 放大率 | `x_dimension_mm / nominal_x_mm`；`< 80%` / `> 200%` → `warn`（边界值不报） |
| DPI 混叠 | `dots_per_module = X_mm / 25.4 × DPI`；`< 1.5` → `error`、`< 2.0` → `warn`（**工程判据，不降级**） |
| 条高 | `bar_height_mm / x_dimension_mm` vs 该符号的模块比阈值；**没有阈值的符号不判** |
| 颜色 | 亮度对比（`insufficient_contrast` / `low_contrast`）+ 波长通道塌陷（`wavelength_reflectance_collapse`）；**两项不合并** |

三条纪律：

- **零静区是结构事实**：该侧要求静区却给了 0，就恒为 `error`，不看任何未核数字，
  `--strict-thresholds` 与降级都碰不到它（BinaryEye #616 类场景）。
- **缺参即拒判**：缺 `x_dimension_mm` / `target_dpi` / `quiet_zone_mm` 只产一条
  `input_incomplete`（点名缺哪个），**不产**任何 `quiet_zone_*` / `magnification_*` /
  `raster_*` 结论——不拿默认值替用户编数据。
- **红条 + 白光 ≠ 红条 + 红光**：白光是宽谱只跑亮度项（`#C8102E` 对白底 5.88:1，`ok`），
  红光才跑波长项（红通道差 0.216 → 塌陷）。把两者合成一条判据是最常见的误判。

### 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 门槛未触发（`--fail-on=none` 下恒为 0） |
| `1` | 跨门槛且最严重级别为 `warn` |
| `2` | 跨门槛且最严重级别为 `error` |
| `3` | 用法错误 / 输入不可解析 / 内嵌数据缺失（**优先于 0/1/2**） |

口径只在 `data/README.md` §8.5 定义一次，本表是摘要。

矩阵是 `--fail-on` 三档 × 最严重级别三态 = **9 格**，外加 `3` 的三类触发
（用法错误 / 输入不可解析 / 内嵌字典缺失）。**12 格逐格有测试**，且同一矩阵再经真实 CLI
端到端跑一遍——所以"某个 spec 会返回几"不是靠文档推断，是断言过的。

### 报告层判什么（M4）

| 判据 | 说明 |
| --- | --- |
| 两格式同源 | 同一 spec 走 `--json` 与 `--md`，`findings` 按 `fingerprint` **集合相等**，`verdict` / `summary` 一致——某个渲染器少报一条即红 |
| 首屏三段 | `VERDICT:` / `FINDINGS:` / `TOP FIX:` **连续占前三行**；常量与 `plan/03` §六 逐字一致（改常量不改文档也红） |
| 渲染层零判定 | AST 两条：不得 import 判定模块；不得重算严重级别（import 面 + `.rank`/`.worst`/`.verdict_for` 面，且判据自带阳性对照） |
| `--with-timestamp` | 默认无该字段；开了才有，格式 `YYYY-MM-DDTHH:MM:SSZ`，不含时区名/主机名 |
| `out/` 落点 | 写盘字节与同一渲染器的 stdout **逐字节相等**；跑前跑后目录只多那两个文件 |

### 回读层判什么（M5，可选）

`oracle` 子命令把生成参数**合成**成一张灰度位图，交给**外部解码器**回读，再与 M3 的参数判定
做**一致性对照**（**不改 M3 判定**）：

| 判据 | 说明 |
| --- | --- |
| 采样器 | **纯函数**：`(plan, x_mm, dpi, 颜色) → 灰度位图`；同输入两次**字节相等**；无随机、**无抗锯齿**、不读文件 |
| 几何 | `dots_per_module = X_mm / 25.4 × DPI`；模块边界四舍五入 ⇒ 低 DPI 下模块宽度可为 **0**（真实失现，不是缺陷） |
| 灰度 | 复用 `print/color.py` 的 sRGB 定义，并按**照明的通道**取值：白光走亮度、红光走红通道反射率——所以"红条 + 红光"在回读域同样塌陷 |
| 图案 | `src/bpreflight/data/vectors/sampler_patterns.json`（**全部 `unverified`**）：只存 `L` 组，`R = complement(L)`、`G = reverse(complement(L))` 由装载期派生；只建模 **EAN-13**，其余符号不猜图案 |
| `agreement` | `consistent` / `m3_stricter`（M3 判有风险但解得出来 → 记入 `known-disagreements`）/ `m3_laxer`（**bug 通道**：必须修 M3，不许藏进已知差异） |
| 缺引擎 | `skipped: oracle_absent`，**`agreement` 字段不产出**（不是 `null`）——不伪造实测结论 |
| 引擎在但驱动不起来 | `skipped: engine_unusable:<detail>` —— **不等于**"解不出"（否则会凭空产出一条 `m3_laxer`） |

`agreement` **不参与** `verdict`：同一份 spec 不会因为本机装没装解码引擎而产出不同结论。
报告落 `out/oracle-report.{json,md}`（`oracle` 只写这两个文件）。**本机没有任何候选引擎**
（`zxing-cpp` / `ZXingReader` / `zbarimg` 实测全无），所以真实运行时一律是
`skipped: oracle_absent`；三样本（每模块不足 1 点 / 健康 / 红条 + 红光）的一致性由
`tests/test_oracle.py` 里**可注入的解码器替身**复现（替身读真实落盘的 PNG 像素）——
它验的是管线，**不是**阈值；阈值对错要真引擎才能验。

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
py -3.12 tools/check_ci_workflow.py      # CI 工作流门（YAML 可解析子集）
py -3.12 tools/gen_fixtures.py --check   # fixture 位级自检（第七道常规检查）
py -3.12 tools/verify_gates.py           # 门自检（注入缺陷 → 必须逐条变红）
py -3.12 -m pytest -q                    # 全量测试
py -3.8  -m pytest -q                    # 3.8 通道（requires-python 的下限要有实跑）
```

## 文档索引

| 文档 | 内容 |
| --- | --- |
| `plan/00-README总览.md` | 总览 / 决策记录 / 弃选项 / 承诺-证据台账 |
| `plan/01-题目文档.md` | 题面：痛点、已占位矩阵、五模块任务、评分、边界 |
| `plan/02` – `plan/06` | 架构 / 模块详设 / 数据计划 / 里程碑 / 交付对标 |
| `plan/HANDOFF-M4.md` | 上一棒交接单（报告与门禁的当前事实与不动点） |
| `plan/HANDOFF-M5.md` | 第 5 棒交接单（回读层：纯函数采样器 / 图案表 / `agreement` 三态） |
| `plan/HANDOFF-M6.md` | 第 6 棒交接单（发布棒，已收尾） |
| `plan/RELEASE-M6.md` | 发布留档：tag 前事实 + tag 后追加栏 + 阶段 7 覆盖对账 |
| `data/README.md` | 依据查证三态 + **数值口径唯一定义（§8）** + 内嵌字典身份（§3.1） |
| `AGENTS.md` | 方法论锚点与门命令 |

## 边界（不做）

不做生成器（M5 的采样器只为**回读对照**在内存里合成位图：不落图片文件、不代替生成器）；
不做编解码库；不做纯 GS1 AI 解析器；不做 GTIN/SSCC 主数据一致性（需联网）；
不做图像式 ISO/IEC 15416 ⚠️ 分级；不做色彩管理 / ICC；不做扫描器型号适配；不做 GUI / 服务端。

## 许可证

Apache-2.0（见 `LICENSE`）。内嵌的 GS1 语法字典为 Apache-2.0，其许可、来源 URL 与快照哈希
随字典一同入库：`src/bpreflight/data/gs1-syntax-dictionary/`（`LICENSE` 上游许可 +
`NOTICE` 来源声明 + 正文），字典身份记在 `src/bpreflight/data/vectors/dict_manifest.json`，
每次运行复算 sha256（不符即 exit 3）。
