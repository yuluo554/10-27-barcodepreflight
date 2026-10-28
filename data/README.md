# data/README — 依据查证、数据源、合成与口径纪律

> **本文件是本题「数值口径」的唯一真相源**。`plan/` 下的文档、代码、报告只可**引用**本文件的口径键，不得复述第二份数值；如有冲突，以本文件为准。
>
> **基准日**：2026-10-27。**代理实际检索窗口**：**2026-10-27T10:56Z – 11:14Z**（18 分钟）。星数、`total_count` 均为该窗口内的快照，属**可过期事实**。

---

## 一、三态图例与检索边界

| 标记 | 含义 |
|---|---|
| ✅ | 已核对：官方源码 / 官方 JSON-LD / 官方单测向量可直连，或代理本机实测可复现 |
| ⚠️ | 部分核对：只见到二手转述、只见到单一来源、或编号/条款未能直连核实 → **落地前须核对** |
| ⬜ | 未获取（403 / 000 / 未检索）→ **不得用确定语气** |

### 1.1 检索边界（如实登记，不得美化）

- **GitHub search 中途触发** HTTP **403 secondary rate limit**。**限流不是 0 结果**：命中限流的检索式一律记「⬜ 未取」，绝不写成 `total_count = 0`。本文出现的 0 结果，只来自**未限流且请求成功**的检索式。
- **不可达源**：
  - `en.wikipedia.org` → **000（连接超时）**
  - `iso.org` → **403**
  - `gs1.org` → **403**
  - Google / DuckDuckGo → **000**
- 因此：**本轮没有任何一条 ISO/IEC 编号被直接核实过**（见 §1.2）。
- 星数为检索当刻 `stargazers_count` 快照；`total_count` 为搜索接口返回的快照。两者都是**软论据**。

### 1.2 ISO/IEC 编号纪律（关键，必须遵守）

因 `iso.org` 返回 403、`en.wikipedia.org` 与搜索引擎不可达，**本次未能直接核实任何 ISO/IEC 编号**。凡文档中出现 ISO/IEC 编号，**一律加 ⚠️ 并注明「落地前需核对」**：

| 编号（⚠️ 全部未核实） | 本文档中的用途 | 纪律 |
|---|---|---|
| ISO/IEC 15417（Code 128） | 符号类别名 | ⚠️ 落地前需核对编号与版本年 |
| ISO/IEC 15420（EAN·UPC） | 符号类别名 | ⚠️ 同上 |
| ISO/IEC 16388（Code 39） | 符号类别名 | ⚠️ 同上 |
| ISO/IEC 16022（Data Matrix） | 符号类别名 | ⚠️ 同上 |
| ISO/IEC 18004（QR Code） | 符号类别名 | ⚠️ 同上 |
| ISO/IEC 15418（GS1 Application Identifiers 与 ASC MH10 Data Identifiers） | AI 注册表 | ⚠️ 同上 |
| ISO/IEC 15416（条码印刷质量分级） | 分级术语来源 | ⚠️ 同上；**本工具不做图像式 15416 分级**（见 §8.6） |

**替代做法**：凡是能通过**官方源码 / 官方 JSON-LD / 官方单测向量**实证的事实，一律走那条路（§3、§4）；不能实证的，只写「符号类别名」而不写编号条款，或写编号并打 ⚠️。

### 1.3 过宽 / 污染检索式（逐条筛掉，不作论据）

| 检索式 | `total_count` | 为什么不作论据 |
|---|---|---|
| `barcode lint` | **12557** | 过宽噪声：绝大多数命中是"给条码库加 lint 脚本"这类无关仓 |
| `quiet zone in:readme` | **1237** | 过宽噪声：`quiet zone` 亦指铁路/航空噪声区、代码静默区 |
| `SSCC` | **751** | **污染值**：`SSCC` 同时是"单细胞聚类""串行 SCSI 控制器""纠错码"等缩写 |
| `barcode`（HN 侧） | 1481 | 只作弱旁证：头部是「Reverse engineering Ticketmaster's rotating barcodes」2305pts、「Barcode Detection API」331pts，**均非"审计缺口"讨论** |

> 上表数字**只登记、不使用**。任何"空白"论断都不得拿这些数当支撑。

---

## 二、已占位矩阵（✅ 星数快照 @ 2026-10-27T10:56Z）

### 2.1 生成（红海，明确不做）

| 项目 | 星数 | fork | 判读 |
|---|---|---|---|
| JsBarcode | **5896★** | 1113 | 浏览器端生成事实标准 |
| zint | **821★** | 172 | 50+ 符号、GS1 数据校验强 |
| python-barcode | **658★** | 139 | Python 生成主流（其 `quiet_zone` 缺陷见 §2.4） |
| BWIPP / postscriptbarcode | **504★** | 80 | PostScript 生成器全集 |
| treepoem | 164★ | — | BWIPP 的 Python 封装 |
| pyStrich | 108★ | — | 纯 Python 生成 |

### 2.2 解码（可作 oracle，明确不重造）

| 项目 | 星数 | fork | 判读 |
|---|---|---|---|
| zxing/zxing | **34185★** | 9441 | Java 参考实现 |
| quagga2 | **5212★** | 972 | 2023-07-05 停更 |
| zxing-cpp | **2070★** | 567 | 首期 oracle 首选（C++ / 有多语言绑定） |
| zbar | **1385★** | 243 | 老牌 1D 解码 |
| pyzbar | **832★** | — | 2023-10-13 停更（zbar 包装） |
| barcode-detector-polyfill | 171★ | — | 浏览器 BarcodeDetector 填充 |

### 2.3 GS1 AI 解析 / 校验：**已被官方 + 60+ 第三方覆盖**（本题最重要的反直觉结论）

| 项目 | 星数 | fork | 时间 | 判读 |
|---|---|---|---|---|
| `gs1/gs1-syntax-engine`（**官方**） | **52★** | 12 | 2026-10-08 | AI 元素串 / Digital Link 的解析**与校验**；C 核心 + C#/Java/Swift/JS-WASM 绑定；lint 集含 `lint_csum`、`lint_yymmd0`、`lint_iso3166`、`lint_iban`、`lint_gcppos1/2` |
| `gs1/gs1-syntax-dictionary`（**官方**） | **21★** | 3 | 2026-08-29 | 机器可读 AI 表 + Linter 规则集（本题 M1 的内嵌依据） |
| `PeterBrockfeld/BarcodeParser` | 77★ | — | — | 第三方解析 |
| `tmattsson/gs1utils` | 65★ | — | — | 第三方解析 |
| Bark-JS | 31★ | — | — | 第三方解析 |
| SwiftGS1Barcode | 30★ | — | — | 第三方解析 |
| gs1-barcode-parser | 21★ | — | — | 第三方解析 |
| gs1js | 18★ | — | — | 第三方解析 |
| IsoCodes | 804★ | — | — | 国别/货币等码表（非 AI 专属） |

> **结论（写进题面的反直觉点）**：「GS1 AI 解析/校验」**不是空白**。官方 `gs1-syntax-engine` 已占住且 lint 完整。本题**只内嵌官方字典驱动 M1，不立项做第三方 AI 解析器**。

### 2.4 核心空白：印刷可读性审计（检索式 + 结果，✅ 未限流请求成功）

| 检索式 | `total_count` | 头部 / 判读 |
|---|---|---|
| `barcode quality verification print` | **2** | `EnricoPittini/Barcodes-verification` **14★**（**图像式** ISO/IEC 15416 ⚠️ 思路）、`CiumbaSpe` 0★ |
| `"print quality" barcode` | **3** | 同上两仓 + 1 无关 |
| `data matrix print quality` | **1** | 0★，无关 |
| `barcode scan distance X-dimension DPI` | **0** | 0 结果（软论据⬜） |
| `barcode readability scan reliability` | **0** | 0 结果（软论据⬜） |
| `barcode preflight print audit` | **0** | 0 结果（软论据⬜） |
| `barcode grade ANSI` | **0** | 0 结果（软论据⬜） |
| `"quiet zone" in:name,description` | **63** | **全部 ≤8★**：MarginQR 8★、`digimental-teknoloji/qr-print-checklist` **1★（仅文档）**、qr-svg-sanitizer 1★ |

### 2.5 必须点名的近邻：`SUDARSHANCHAUDHARI/BarStripeLab` **1★**

- created **2026-04-15**，pushed **2026-10-24**（检索窗口内快照）。
- README 自述："makes EAN-13/8, UPC-A, Code 128 barcodes with a **scan-safety estimate** and a **decode check**"。
- 代码含 `lib/printSize.ts`（X-dimension / 放大率 / DPI）、`lib/phoneRead.ts`（用 `@zxing/library` 作回读 oracle）、`lib/gs1.ts`（条高模块比）、`lib/colorEngine.ts`。
- **但它（五点差异，必须写进题面）**：
  1. **浏览器艺术生成器**（46 种剪影样式）——产出图，不是审计器；
  2. **仅 EAN-13/EAN-8/UPC-A/Code 128**——**无 GS1-128 / Data Matrix / QR**；
  3. **无 CLI / 无 API / 无 CI 门禁**——不能进流水线；
  4. **无 ISO/IEC 15416 ⚠️ 分级**——只有自定 `scan-safety estimate`；
  5. **GenSpec 数值硬编码在自己文件里**——不可替换、不可追溯来源。
- **判定**：**概念被部分验证，但"可集成审计器 + CI 门禁"这个位置仍空**（措辞限定，不作首创主张）。

---

## 三、AI 字典实证抽行（✅ 来自 `gs1/gs1-syntax-dictionary`，Apache 许可）

以下为字典原文行（保留原缩进与注释），**不是转述**：

```
00  *?  N18,csum,gcppos2                    # SSCC
01  *?  N14,csum,gcppos2  ex=255,37         # GTIN      <- AI 01 是 GTIN 不是 SSCC ✓
10     ?  X..20           req=01,02,03,8006,8026   # BATCH/LOT（需 FNC1）
17  *?  N6,yymmd0         req=01,02,03,255,8006,8026  # 有效期
21        X..20           req=01,03,8006 ex=235   # 序列号（变长需 FNC1）
250    ?  X..30           req=01+21,03+21,8006+21  # "+"=AND，逗号=OR
8003   ?  N1,zero N13,csum,gcppos1 [X..16]  # GRAI
8006   ?  N14,csum,gcppos2 N4,pieceoftotal  # ITIP
```

**逐行语义（驱动 M1 的四个字段）**：

| 记号 | 语义 | M1 必须实现 |
|---|---|---|
| `N` / `X` | 定长数字 / 可变字符集（CSET 82） | 字符集 + 长度校验 |
| `..20` / `N14` | 变长上限 / 定长 | 长度校验与截断判定 |
| `*` | **定长 AI 且不需要 FNC1 分隔**（上游原话："Pre-defined length AI not requiring FNC1 separator"） | 字段边界推导（**不是**"该 AI 必填"） |
| `?` | **允许作为 GS1 Digital Link 数据属性**（上游原话："AI that is permitted as a GS1 Digital Link data attribute"） | 本棒只记录不作判定（Digital Link 不在首期范围） |
| `csum` | 该 AI 含校验位 | 走 §8.1 算法，**不自造** |
| `yymmd0` | YYMMDD，且 **DD=00 合法** | **不得判 DD=00 为错**（见下） |
| `gcppos1` / `gcppos2` | 校验位所处位置（1 位 / 2 位尾部） | 校验位定位 |
| `req=a,b,c` | **OR**：任一同组 AI 存在即可 | 组合校验（或） |
| `req=a+b` | **AND**：同组 AI 必须同时存在 | 组合校验（与） |
| `ex=255,37` | 该 AI 的**互斥集** | 冲突校验 |
| `zero` | 允许前导零语义（如 `N1,zero` 表示 1 位可为 0） | 不得把 `0` 当空 |
| `pieceoftotal` | N4 拆成"件/总件"两段 | 拆段校验，不整体当数字 |

**`yymmd0` 的关键注意点（自造解析器最常错的一处）**：

- `yymmd0` 允许 **DD = 00**，语义为**当月最后一天**。
- 该规则在 11/12/13/15/16/17/**4324/4325** 八条 AI 上均按此理解（**✅ M1 已逐条核对**：
  以字典原文行逐条读 `N6,yymmd0` 的归属，见下）。
- **八条 `yymmd0` 逐条核对的结论**（✅ 2026-10-27，依据 = 字典原文行）：
  `11 PROD DATE` / `12 DUE DATE` / `13 PACK DATE` / `15 BEST BEFORE or BEST BY` /
  `16 SELL BY` / `17 USE BY or EXPIRY` / `4324 NOT BEF DEL DT` / `4325 NOT AFT DEL DT`。
  其中 `4324`/`4325` 的 `yymmd0` 是**组件级**（`N6,yymmd0 N4,hhmi`），即日期只占前 6 位。
- **`yymmdd`（无 DD=00 惯例）另有 6 条**：`4326` / `7003` / `7006` / `7007` / `7011` / `8008`；
  **`yyyymmdd` 2 条**：`7250` / `7251`。同一族但**不允许 DD=00**，M1 一并实现（同一 id `invalid_date`）。
- M1 的验收里必须含两条：①`(17)251200`（YY=25/MM=12/DD=00）**不得**被判 `invalid_date`，应判 `dd00_last_day_of_month` 并以 **2025-12-31** 参与后续比对；②对照 `(17)251301`（MM=13）**必须**判 `invalid_date`。两条一起才证明「DD=00 特例」没有被实现成「日期校验全关」。
- **YY → CCYY 的世纪窗口**（`lint_yymmd0.c` 里是编译期 `CURRENT_YEAR`）：M1 **固定**为
  数据文件 `gs1_vectors.json[yymmd0.century_resolution]`（参考年 21 / 窗口 50），
  **不读系统时钟**——否则同一输入会因"跑的年份"不同而产出不同报告（违反 K10）。

**为什么不自造 AI 表**：AI 表有上千行、带 `req`/`ex`/`minmax` 组合语义，任何手抄都会漂移。M1 **内嵌 `gs1-syntax-dictionary`（Apache-2.0）**，把字典当数据读，代码只实现四个语义解释器（`req`/`ex`/`yymmd0`/`csum`）。

### 3.1 内嵌快照与身份（✅ M1 已落盘）

| 项 | 值 |
|---|---|
| 上游 | `gs1/gs1-syntax-dictionary`（Apache-2.0） |
| 快照 commit | `c63d8a12210dd0cfaceac4aae45ccf57b48eb15b`（committed 2026-08-29T06:07:59Z） |
| 抓取日 | **2026-10-27** |
| 入库位置 | `src/bpreflight/data/gs1-syntax-dictionary/`（正文 + 上游 `LICENSE` + 本项目 `NOTICE`） |
| `dict_version` | `gs1-syntax-dictionary@c63d8a12210d-2026-08-29` |
| `sha256`（正文） | `1ea02f4e3b81d3092e095987600e01c7fd55310f4da5181f5a070262ff6ffc94` |
| 整表解析结果 | **224 条目行 → 541 个具体 AI**（区间展开后）；283 个组件；193 条带 `req`；85 条带 `ex` |

- **上游头部是 `# Release: UNSET`**（树不在 tag 上），因此 `dict_version` 用
  **commit 短哈希 + 提交日**拼出，而不是编一个版本号。
- 哈希在**每次运行**由 `src/bpreflight/gs1/dictionary.py` 复算；不符即
  `DictionaryError` → exit 3（**安装问题，不是关于条码的结论**）。
- 复算方式：`py -3.12 -c "import hashlib,io;print(hashlib.sha256(io.open('src/bpreflight/data/gs1-syntax-dictionary/gs1-syntax-dictionary.txt','rb').read()).hexdigest())"`。
- **linter 的归宿**（不许"静默略过"）：字典点名的 linter 里，M1 **解释** `csum` +
  日期族（`yymmd0`/`yymmdd`/`yyyymmdd`，`yyyymmd0` 当前表内无使用者）；
  `gcppos1`/`gcppos2` 需要 **GCP 分配库（GEPIR，联网授权）** 才能判 —— 那是
  `plan/01` §7 的**非目标**，因此标 `skipped: gcp_lookup_unavailable`（**不冒充已判**）；
  其余 linter 标 `skipped: linter_not_implemented:<name>`，由后续里程碑收编。

---

## 四、校验位自证记录（"合成样本如何自证"的范式）

### 4.1 过程（如实记录，含**首版写错**）

1. 代理先按"常见网文写法"实现 GS1 校验位：**数据位自右向左交替 3/1**。
2. 用两个官方单测向量回归，**首版结果与官方向量不符**：得 `…79` / `…06`，正确应为 `…73` / `…08`。
3. 据此**重读官方 `gs1-syntax-dictionary/src/lint_csum.c`**，确认规则是：

   > **权重按「含校验位的全长」决定起始**：全长**偶数**时最左数据位权重为 **3**，全长**奇数**时最左权重为 **1**；此后**自左向右交替 3/1**；**只对数据位求和**；`check = (10 - sum % 10) % 10`。

4. 修正后重跑四个向量，全部 PASS。

> **二次留痕（本文件落盘时）**：把修正后的算法写进 §8.1 时，代理把交替权重写成 `6 - W`（应当 `4 - W`），同一组四向量立刻报 1 PASS / 3 FAIL（`0234567` 得 9、`0950110153000` 得 5、`400638133393` 得 5）。改正后 4/4 PASS。**同一套向量在同一天抓住了两次不同写法错误**——这正是"向量必须先于实现"的直接证据。

### 4.2 回归向量表（✅ 修正后）

| 数据位 | 计算得校验位 | 官方完整向量 | 结果 |
|---|---|---|---|
| `0234567` | **3** | `02345673` | PASS |
| `41600033610` | **8** | `416000336108` | PASS |
| `0950110153000` | **3** | `09501101530003`（GTIN-14） | PASS |
| `400638133393` | **1** | `4006381333931`（EAN-13） | PASS |

**手算留痕（可复核）**：

- `0234567`（数据 7 位 → 全长 8，偶 → 起 3）：`0·3+2·1+3·3+4·1+5·3+6·1+7·3 = 57` → `(10-7)%10 = 3`。
- `41600033610`（数据 11 → 全长 12，偶 → 起 3）：和 `= 62` → `(10-2)%10 = 8`。
- `0950110153000`（数据 13 → 全长 14，偶 → 起 3）：和 `= 47` → `(10-7)%10 = 3`。
- `400638133393`（数据 12 → 全长 13，**奇 → 起 1**）：和 `= 89` → `(10-9)%10 = 1`。

### 4.3 纪律沉淀（写进 M1 验收）

- **校验位算法必须有向量回归**，且向量的每一行都要能追溯到官方源码/官方单测/公开规范范例。
- 代理另列的两个"期望值"是**现场臆测、非权威向量**，**已剔除、不计入**本表。
- 首版写错这件事本身是证据：**"看起来显然"的算法也需要 oracle**，所以 M1 的验收不是"实现完了"，而是"四个向量全 PASS 且手算留痕可复核"。

---

## 五、印刷数值：二手标注表（⚠️ 全部须核对 GenSpec 原表）

> **纪律**：下表每一项都必须带 `source` 与 `status`。**没有任何一项是本轮直接核实的一手 GenSpec 原文**。M3 的阈值**全部从版本化数据文件读取**（`src/bpreflight/data/vectors/*.json`），代码里不出现裸数字；每个阈值在数据文件里带 `source` / `status` / `verified_at` 三字段。

| # | 数值 / 判据 | 值 | 来源 | 状态 | 处置 |
|---|---|---|---|---|---|
| P1 | 100% 名义 X-dimension | **0.330 mm** | 二手（行业通行值，本轮未取到 GenSpec 原表） | ⚠️ | 默认值，须核 GenSpec |
| P2 | 零售 POS 可接受放大率区间 | 约 **80% – 200%** | **仅在 BarStripeLab 源码见到**（1★ 项目），属二手 | ⚠️ | 默认区间，须核 GenSpec；`<80%` 或 `>200%` → `warn` |
| P3 | EAN-13 / UPC-A 条高 | **22.85 mm @ X = 0.330 mm ⇒ 69.24 模块** | 自洽换算（22.85 / 0.330 = 69.24），非独立一手 | ⚠️ | 与 P1 联动的派生值；核 GenSpec 后固化 |
| P4 | 每模块点数 | `dots_per_module = X_mm / 25.4 × DPI` | **本工具定义的工程判据**（栅格混叠探针），非标准条款 | — | `< 2.0` → `warn`（高风险栅格混叠）；`< 1.5` → `error` |
| P5 | 条/空颜色可比性 | 红条 + **红光源/红滤镜** → 该通道反射率差 ≈ 0.216 → 不可读；红条 + **白光无滤镜** 不属此类，走亮度项（`#C8102E` vs 白底 `contrast_ratio = 5.88`，代理实算） | 物理常识 + 条/空反射率对比的定义；分级术语源自 ISO/IEC 15416 ⚠️ 编号未核实；亮度阈值 3.0/4.5、通道差阈值 **0.30** 为工程判据 | ⚠️ | 按"亮度对比 + 波长通道"两项判定，**两项不合并**，见 §8.4 |
| P7 | 条高模块比 | EAN-13/EAN-8/UPC-A 用 `69.24` 模块（= 22.85 / 0.330，P3 的派生值）；其余符号**无阈值、不判** | 自洽换算，非独立一手 | ⚠️ | 每符号一项 `bar_height_modules_min_<symbol>`，未核时降级；缺项即不判（不借别符号的数） |
| P8 | 贴近带宽度 | `1.2`（`modules_min` 的倍数） | **本工具定义的工程判据**（"贴近下限"的带宽），非标准条款 | — | `gen_spec.json#engineering_heuristics.quiet_zone_marginal_factor`；不参与降级 |
| P6 | 静区模块数 | **本工具不硬编码**：按符号类别从 `src/bpreflight/data/vectors/quiet_zone.json` 读取，每项带 `source`/`status` | 各符号规范表（本轮**未取得**，iso.org 403 / gs1.org 403） | ⚠️ | 默认值全部标 `status: "unverified"`；`--strict-thresholds` 模式拒用未核值 |

> **P6 是本题最重要的工程约束**：静区模块数是"印刷可读性"最常出问题的项，但本轮**一个都没核实到**。因此 M3 **不写死**静区阈值，而是把它做成**带来源标签的数据**。这样工具在阈值未核时仍然可用（判定结果标 `threshold_status: unverified`），且永远不会把传闻伪装成标准。

---

## 六、数据源可获取性记录

| 数据源 | 获取方式 | 结果 | 状态 |
|---|---|---|---|
| `ref.gs1.org` JSON-LD（AI 表） | HTTP GET | **200，约 546 KB** | ✅ |
| `gs1/gs1-syntax-dictionary`（AI 表 + linter 规则） | GitHub 源码 | **可获取，Apache-2.0**；✅ **M1 已内嵌**（commit `c63d8a12`，见 §3.1） | ✅ |
| `gs1/gs1-syntax-engine`（官方参考实现，可作 M1 对照组） | GitHub 源码 | 可获取（52★ @ 2026-10-08） | ✅ |
| `iso.org` | HTTP GET | **403** | ⬜ |
| `gs1.org` | HTTP GET | **403** | ⬜ |
| `en.wikipedia.org` | HTTP GET | **000（超时）** | ⬜ |
| Google / DuckDuckGo | HTTP GET | **000** | ⬜ |
| GitHub search API | 部分检索式 | **中途 403 secondary rate limit** | ⚠️ 限流式记「未取」，不记 0 |
| StackOverflow（网页直取） | 网页 | 原话由检索摘要取得；**正文页本轮未逐页直取** | ⚠️ |
| zxing-cpp / zbar（M5 oracle） | 本地安装（**外部命令**，不 import 绑定） | 探测顺序 `zxing-cpp` → `ZXingReader` → `zbarimg`；一个都没有时 M5 **显式跳过并标 `skipped: oracle_absent`**（`agreement` 字段不产出） | ✅ **M5 已实测**：本机三者全无 ⇒ 一律 `oracle_absent`；**真引擎解码路径未验证**（命令模板未被观测过），一致逻辑用可注入替身验过（§9 第 7 项） |

**运行期依赖**：首期**零网络**。所有外部数据（AI 字典 / 阈值向量）在建仓时**一次性内嵌进仓库**，运行时不发任何请求。

---

## 七、合成数据纪律

1. **全部程序化生成**：不采集任何真实商品/标签照片。向量集与 fixture 全部由脚本按确定性规则生成。
   **例外（唯一一处第三方数据）**：`src/bpreflight/data/gs1-syntax-dictionary/` 是官方 AI 表的
   **原样副本**（Apache-2.0，附上游 `LICENSE` 与来源 `NOTICE`）——它是**官方数据**，不是合成样本，
   也正因如此才必须**照抄而不是转述**（`plan/00` D1）。
2. **确定性**：同一 `--seed` 与同一向量文件 ⇒ **逐字节一致**的输出（JSON key 有序、无时间戳、无随机、浮点一律转成定点或字符串）。
3. **可自证**：任何一个"期望判定"，都必须能追到三处之一——①官方源码/官方单测向量；②官方 JSON-LD/字典原文；③本文件 §8 的口径定义 + 手算留痕。
4. **不造真实主体**：GTIN/SSCC 样例一律取自官方单测向量与公开规范范例（`09501101530003`、`4006381333931` 等），**不对应任何真实在售商品**；公司前缀等敏感信息一律不出现。
5. **规模诚实**：仓库内 fixture 规模按"覆盖全部判定分支"设定，**不得**描述为"大规模压测"。
6. **产物不入仓**：`*.png`（栅格化仿真产物）、`out/`、`reports/` 由 `.gitignore` 排除；入库的只有**生成脚本 + 向量 + 期望值**。

---

## 八、数值口径（**唯一定义处**）

> `plan/01`、`plan/00`、代码、报告只引用本节的口径键名，不复述数值。

### 8.1 GS1 校验位（`csum`）

```
输入：数据位串 d（不含校验位），长度 n
起始权重 W = 3 if (n + 1) % 2 == 0 else 1     # 按"含校验位的全长"奇偶定起始
sum = Σ d[i] * (W if i 为偶数 else 4 - W)      # 自左向右交替 3/1（W=3↔1，故另一权重 = 4 - W）
check = (10 - sum % 10) % 10
```

> **易错点记录**：交替的另一权重是 **`4 - W`**，不是 `6 - W`。写成 `6 - W` 时 W=3 会退化成"全 3"，首版即因此得错值。该行已由 `tests/test_checksum.py` 的四向量回归覆盖。

- 只对**数据位**求和；校验位本身不计入。
- 与 §4.2 四个向量绑定为回归测试；**任何实现改动必须四个向量全 PASS**。
- 不实现"另一种流派"（不要加 fallback 分支——两套算法并存等于没有判定）。
- 唯一实现：`src/bpreflight/gs1/checksum.py::gs1_check_digit`（✅ M1 已落盘；
  `tests/test_checksum.py` 用 AST + 文本两条判据把"只有一个"钉住）。

### 8.1.1 日期口径（`yymmd0` / `yymmdd` / `yyyymmdd`）——✅ M1 已落盘

```
输入：日期字段文本 v（宽度由组件规格决定：YY 2 位 or YYYY 4 位，MM/DD 各 2 位）
month ∈ 01..12（越界 → invalid_date）
DD == 00 且在 d0 族 linter 下 → 合法，归一到当月最后一天（info: dd00_last_day_of_month）
DD ∈ 01..当月天数 → 合法；DD > 当月天数 → invalid_date
月天数用 calendar.monthrange(year, month)（闰年交给标准库，不手写）
```

- **YY → CCYY 的世纪窗口固定**在 `src/bpreflight/data/vectors/gs1_vectors.json`
  （`yymmd0.century_resolution`：参考年 21 / 窗口 50 / 世纪 19·20·21）——对应上游
  `lint_yymmd0.c` 的编译期 `CURRENT_YEAR`。**不读系统时钟**（K10）。
- DD=00 的两个反例必须同时存在（`(17)251200` 报 info 且归一到 2025-12-31；
  `(17)251301` 必须 invalid_date），否则"特例"可能被实现成"日期校验全关"。

### 8.2 静区（quiet zone）判定

- 输入：`symbol`、`side`（`left`/`right`/`top`/`bottom`）、`quiet_zone_mm`、`x_dimension_mm`。
- 计算：`quiet_zone_modules = quiet_zone_mm / x_dimension_mm`（报告里保留 3 位小数定点字符串）。
- **判定分三档，从"不需要任何标准数字"到"需要已核数字"排列**：

| 档 | `id` | 条件 | 需要 `modules_min` | `threshold_status` | `severity` |
|---|---|---|---|---|---|
| 结构 | `quiet_zone_absent` | 该侧 `required == true` 且 `quiet_zone_mm == 0` | **否** | `not-applicable`（不比较任何阈值） | 恒 `error` |
| 阈值 | `quiet_zone_insufficient` | `qz_modules < modules_min` | 是 | 跟随阈值 | `verified→error` / `unverified→warn` |
| 贴近 | `quiet_zone_marginal` | `modules_min <= qz_modules < modules_min × marginal_factor` | 是 | 跟随阈值 | `warn` |

- 阈值来源：`src/bpreflight/data/vectors/quiet_zone.json[symbol][side]`，字段
  `{modules_min, required, source, status, verified_at}`。
- **`required` 是结构事实，不是标准数值**：1D 符号只要求 `left`/`right`（`top`/`bottom`
  的 0 是合法的）；2D（`qr` / `datamatrix`）四边都要求。**它必须写在数据里、
  由装载期断言为 bool**，不许由 `modules_min > 0` 推断——否则"未核阈值"会被悄悄
  提升成结构事实，而结构档恰恰是唯一不需要任何标准数字的锚点。
- **结构档是本模块的"零标准"锚点**：`quiet_zone_absent` 不依赖任何未核数字，因此
  **在任何阈值状态下都是 `error`**，也是 M3 的第一优先验收用例（对应 BinaryEye #616
  的"静区不再生成"）。`--strict-thresholds` 与未核降级都**不得**触及它；它的
  `threshold_status` 是 `not-applicable`——报 `unverified` 会让读者以为"等阈值核过
  这条错就可能消失"，与事实相反。
- `marginal_factor`（贴近带宽度）是 `basis: engineering-heuristic` 项，在
  `gen_spec.json#engineering_heuristics.quiet_zone_marginal_factor`，**不参与降级**。
- **未核阈值兜底**：若阈值 `status != "verified"`，报告条目必须带 `threshold_status: "unverified"`，
  且**不得**在 CI 门禁里按 `error` 拦（降为 `warn`）——避免用未核数字卡住别人的流水线。
  `--strict-thresholds` 时改为 `error` 并在报告首屏标注。
- **降级的适用边界（重要）**：`status` 只属于**「标准数值，本轮未核实」**这一类（`basis: "gen-spec"`）：静区模块数、放大率区间、名义 X、条高模块比。`basis: "engineering-heuristic"` 的判据（**DPI 每模块点数**、**颜色亮度/波长对比**、**贴近带宽度**）**没有 `status` 字段、不参与降级**，其 `severity` 恒定。混淆这两类会让"未核"变成万能挡箭牌。

### 8.3 X-dimension / 放大率 / DPI / 条高

- `magnification_pct = x_dimension_mm / nominal_x_mm × 100`（`nominal_x_mm` 来自 `src/bpreflight/data/vectors/gen_spec.json`）。
- 判定：`magnification_pct < magnification_min_pct` → `warn: magnification_below_range`；
  `> magnification_max_pct` → `warn: magnification_above_range`；
  `x_dimension_mm <= 0` 或字段缺失 → `error: x_dimension_missing`（`basis: engineering-heuristic`）。
- `dots_per_module = x_dimension_mm / mm_per_inch × target_dpi`
  （`mm_per_inch` 是 `gen_spec.json#constants` 里的单位换算常量，不是阈值）。
- 判定：`dots_per_module < error_below` → `error: raster_alias_high_risk`；
  `< warn_below` → `warn: raster_alias_risk`；`>= warn_below` → 不产出条目。
- `bar_height_modules = bar_height_mm / x_dimension_mm`，与
  `gen_spec.json#values.bar_height_modules_min_<symbol>` 比较；不足 →
  `error: bar_height_insufficient`（未核时降 `warn`）。**没有该符号阈值的符号不判**
  （不借别的符号的数字）。
- **DPI 混叠是本工具定义的工程判据**，不冒称标准条款。报告里必须写
  `basis: "engineering-heuristic"`，且**不带 `status` 字段、不参与未核降级**（见 §8.2 末条）。
- 边界语义（**闭区间内侧**）：`dots_per_module == 2.0` 判 ok（`< 2.0` 才 warn）；
  `== 1.5` 判 warn（`< 1.5` 才 error）；放大率 `== 80%`/`== 200%` 不报。
  **边界值逐条测**：`1.4999 / 1.5000 / 1.9999 / 2.0000`；
  `0.2640 / 0.2639 / 0.6600 / 0.6601`（X mm，对应 80% / 200% 两侧）。

### 8.4 条 / 空颜色可比性

- 输入：`bar_color`、`space_color`、`illumination`（`white` / `red` / `ir`）。
- **照明建模表在数据里**：`src/bpreflight/data/vectors/color_cases.json#illuminations`，
  每项 `{modelled, channel, source, note}`。`modelled: false`（当前是 `ir`，以及任何
  表里没有的名字）**不判**，产 `info: surface_effect_unmodeled`（§8.9 G5）——
  不给 pass 也不给 fail。
- 判据两项（都用相对亮度，不用绝对色值）：
  1. **亮度对比**：`contrast_ratio = (L_light + 0.05) / (L_dark + 0.05)`，`L` 按 sRGB
     相对亮度公式由 8-bit 通道算；`< 3.0` → `error: insufficient_contrast`；
     `< 4.5` → `warn: low_contrast`。两项**互斥**（error 档不再叠一条 warn）。
  2. **波长通道可比性**：照明建模到某个窄带通道时（`red` → `red` 通道），若条/空在
     **该通道**的相对反射率差 `< 0.30`，判 `error: wavelength_reflectance_collapse`。
     - **红条 + 红光**是典型态（`#C8102E` 的红通道 200/255 vs 白底 255/255 → 差
       `0.216` → 塌陷）。
     - **红条 + 白光不算 collapse**：白光是宽谱，它的 `channel` 是 `luminance`，
       **不跑**波长项；红条对白光的相对亮度仍低（`#C8102E` 的 `L = 0.1285`，对白底
       `contrast_ratio = 5.88`），此时**只走亮度项**。把"红光"与"白光"混为一谈是本项
       最常见的误判，单测必须分开锁。
     - **不可读 ≠ 低对比**：两项判据的 `id` 不同，报告里**不合并、不互相压制**
       （`#C86E00` + 红光会同时触发两条，测试逐条断言）。
- **"相对反射率"的定义**：单通道 8-bit 值 / 255，不做色彩管理、不引入 ICC
  （弃选项）。只做阈值判定，输出风险，不输出"扫描仪读到什么"。
- **公式常数（不是阈值，无 `status`、不参与降级）**：sRGB 线性化
  `c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4`，亮度权重
  `0.2126 / 0.7152 / 0.0722`，对比公式的常数项 `0.05`，8-bit 通道上限 `255`。
  它们只在 `src/bpreflight/print/color.py` 出现一次（改校准值才会动它们）。
- **M5 采样器的灰度化（`oracle/sampler.py`）用同一份定义**：**不抄第二份**系数，
  直接调 `print/color` 的 `relative_luminance` / `channel_reflectance`；并且按
  `color_cases.json#illuminations.<name>.channel` 取值 —— `luminance`（白光）走相对亮度，
  `red`（红光）走该通道的相对反射率。这样"红条 + 红光塌陷"在**参数域**（本节）与
  **回读域**（M5 位图）是同一个物理量，而不是两套说法。
- 分级术语若引用 ISO/IEC 15416 → ⚠️ 编号未核实，且**本工具不做 15416 分级本身**（见 §8.6）。

### 8.5 严重级别与退出码

| 级别 | 含义 |
|---|---|
| `ok` | 通过 |
| `info` | 有提示但不影响扫描 |
| `warn` | 有风险，可能影响某些扫描器/某些工况 |
| `error` | 判定为"印出来大概率扫不出"或数据层硬错误 |

**退出码由 `--fail-on` 与"最严重级别"共同决定**（不是两个独立机制）：

```
最严重级别 worst = max(severity of all findings)   # ok < info < warn < error
门槛 crossed(for fail-on) :
  fail-on=none  -> 永不 crossed
  fail-on=warn  -> worst >= warn
  fail-on=error -> worst >= error

exit = 3   若 用法错误 / 输入不可解析 / 内嵌字典缺失     # 优先，且不参与判定计数
exit = 2   若 crossed 且 worst == error
exit = 1   若 crossed 且 worst == warn
exit = 0   其余（含 covered 未触发，或 fail-on=none 的任意 worst）
```

| 退出码 | 含义 |
|---|---|
| `0` | 门槛未触发（`--fail-on=none` 下恒为 0；`warn`/`error` 档下表示未跨门槛） |
| `1` | 跨门槛且最严重级别为 `warn` |
| `2` | 跨门槛且最严重级别为 `error` |
| `3` | 用法错误 / 输入不可解析 / 内嵌字典缺失（**优先于 0/1/2，不参与判定计数**） |

**矩阵（M4 已逐格测试）**：`--fail-on ∈ {none, warn, error}` × `worst ∈ {info, warn, error}` = **9 格**；再加 `3` 的三类触发（用法错误 / 输入不可解析 / 字典缺失）。判据在 `tests/test_exit_codes.py`：9 格**逐格一条**（不 parametrize 压成 3 条），三类 `3` 各一条且都从真实入口触发，同一矩阵再经 CLI 端到端跑一遍。

> **设计取舍**：默认 `--fail-on=none`（只报告不拦），因为默认拦死会让人第一次用就被劝退；要接 CI 显式写 `--fail-on=error`。这一条写进 README 首屏，避免"为什么我的流水线一直是绿的"。

### 8.6 不做 ISO/IEC 15416 ⚠️ 图像式分级（口径声明）

本工具**不输出 A/B/C/D/F 等级**，不计算 `SC`（symbol contrast）、`MOD`（modulation）、`DEF`（defects）、`DEC`（decode）等图像指标。原因：那些指标需要**真实印刷品的扫描图像**，属图像采集域；本题是**参数域**审计（从生成参数推出风险）。引用 15416 ⚠️ 仅用于术语对齐，不用于分级。

### 8.7 报告字段（稳定契约）

```json
{
  "schema": "bpreflight/1",
  "input": {"file": "<path>", "sha256": "<hex>", "mode": "spec|params"},
  "tools": {"version": "<x.y.z>", "dict_version": "<hash>", "vectors_version": "<hash>"},
  "findings": [{"id": "quiet_zone_insufficient", "severity": "error",
                "module": "M3", "evidence": {...},
                "threshold_status": "unverified", "basis": "gen-spec|engineering-heuristic"}],
  "summary": {"ok": 0, "info": 0, "warn": 1, "error": 2},
  "verdict": "fail"
}
```

- **`findings` 的 `id` 是稳定标识符**（改语义即改 `id`，不许悄悄改判定）。
- **`encoding_plan`（M2）**：只在数据**可编码进目标符号**时出现：
  `{symbol, mode, segments[], total_modules, checksum, tie_break, profile_version}`。
  不可编码时**不输出半个计划**，原因在 `findings` 里（见 §8.10）。
- **`tools` 身份**：`dict_version` / `dict_sha256`（M1 字典）、
  `symbol_profiles_version` / `symbol_profiles_sha256`（M2 规则表）与
  `vectors_sha256`（M3 阈值册：`quiet_zone.json` + `gen_spec.json` + `color_cases.json`
  三份的**合并摘要**，装载时按固定序复算）都可独立复算。
- **M3 的 findings 走同一个 `findings` 数组**，不另开 `scanability` 段——`verdict` 由全量
  findings 的最严重级别派生（§8.8），把 M3 单独装一段会让"条码整体能不能扫"有两个答案
  （`plan/01` 的 `scanability` 是这一段的口径名，不是第二个字段）。
- `fingerprint = sha256(f"{id}\x1f{module}\x1f{canonical_target}").hexdigest()[:16]`，**不含**时间戳/路径/机器名，用于跨 run diff。
- 报告**默认无时间戳**（确定性优先）；`--with-timestamp` 时显式标注"非确定性导出"：
  报告新增 `timestamp` 字段，格式固定 **`YYYY-MM-DDTHH:MM:SSZ`（ISO-8601 / UTC，句尾字面 `Z`）**。
  **不得**出现本地时区名、时区缩写或主机名——那正是"同一输入在不同机器/不同时区产出不同报告"的入口（D11）。
  JSON 与 MD 都读同一个 `Report.timestamp`，因此两格式不可能一个有、一个没有。
- 报告**不含**任何网络请求结果、不含用户主目录绝对路径（写相对路径或脱敏路径）。
- **M5 的 oracle 报告是独立文档**（schema `bpreflight/oracle-report/1`，固定落
  `out/oracle-report.{json,md}`）：字段
  `{engine, m3_verdict, m3_findings, skipped, oracle_result, agreement,
  known_disagreements, bugs, raster}`。**不掺进主报告** —— 主报告的 `findings` /
  `summary` / `verdict` 一个字都不变（K25），且 `engine` 只写名字与版本，
  **不写可执行文件的绝对路径**（同本节末条）。`agreement` / `oracle_result` / `raster`
  只在**真跑过回读**时出现。

### 8.8 判定结论词表（一处定义）

**`verdict` 只有三个值**，由 `findings` 的最严重级别直接派生：

| `verdict` | 触发条件 |
|---|---|
| `pass` | 无 `warn` / `error` |
| `warn` | 有 `warn`，无 `error` |
| `fail` | 有 `error` |

- **不设 `unknown` 作为 `verdict`**。原因：`verdict` 必须只由 `findings` 决定，否则同一输入会因为"是否装了 oracle"而产出不同 `verdict`，破坏确定性。
- "不可判"信息放在**独立字段**：
  - `skipped: "oracle_absent"`（M5 未跑，`--oracle` 被请求但引擎缺失）；
  - `skipped: "reference_engine_absent"`（M1 的向量没交给官方 `gs1-syntax-engine`
    做过一致性对照——**没有对照就说没对照**，不伪造"一致"）；
  - `skipped: "gcp_lookup_unavailable"`（该判定要 GCP 分配库 = GEPIR 联网授权，
    属非目标）；
  - `skipped: "module_not_implemented:<Mk>"`（该模块尚未落地，报告必须自己说）；
  - 每条 finding 的 `threshold_status: "unverified"`（该条阈值本轮未核）；
  - 报告头 `strict_thresholds: true|false`。
- `--strict-thresholds` 的作用是把 `unverified` 项的 `severity` 由 `warn` 恢复为 `error`，从而 `verdict` 自然变成 `fail`——**不引入第四种 verdict**。

**M5 的 `agreement`（本节唯一一处定义，K25）**：M5 只做**一致性对照**，**不改 M3 判定**
（`plan/00` D10）。`oracle` 报告里三件：`{m3_verdict, oracle_result, agreement}`。

| `agreement` | 条件 | 归宿 |
|---|---|---|
| `consistent` | M3 的风险结论与 oracle 回读一致（判有风险且解不出 / 判干净且解得出来） | 不登记 |
| `m3_stricter` | M3 判有风险，oracle **解得出来** | `known-disagreements`（可能是假阳性） |
| `m3_laxer` | M3 判干净，oracle **解不出来** | **bug 通道**：必须修 M3 判定，**不许**藏进 `known-disagreements` |

- `agreement` 是**独立字段**，**不是** `verdict` 的第四个值，也**不参与** `verdict`：
  同一输入不会因为"本机装没装解码引擎"而产出不同 `verdict`（§8.8 首条理由）。
- **引擎缺失时 `agreement` 字段不产出**（不是 `null` —— 是缺席）：这一层没跑（G6）。
- `m3_verdict` 是 M3 findings 自己的投影（`pass|warn|fail`），不掺 M1/M2 的结论。

### 8.9 不可判（gray）条件

> 本题不设第四种 `verdict`（§8.8），但**必须有显式的"不可判"通道**，否则工具会用未核阈值假装确定。以下情形一律**降级标注**，不得当作确定结论：

| # | 情形 | 处置 |
|---|---|---|
| G1 | 该条判定所依赖的阈值 `status != "verified"` | 条目带 `threshold_status: "unverified"`；`severity` 降为 `warn`（`--strict-thresholds` 除外） |
| G2 | 判定需要**真实扫描/图像采集**（如"这台扫描器实际能否解出"） | **不产出该条 finding**；报告落 `skipped: "oracle_absent"` 或 `skipped: "requires_capture"` |
| G3 | 输入参数**不足以判定**（如只给了 `target_dpi` 没给 `x_dimension_mm`） | 产 `error: input_incomplete` 并列出缺失字段；**不得**用默认值静默补齐 |
| G4 | 符号不在首期集合（`aztec`/`pdf417`/`maxicode`/`dotcode`/复合码） | 产 `error: symbol_unsupported`（明确拒绝，不猜） |
| G5 | 颜色/照明组合的物理行为**超出两项判据覆盖**（如金属油墨、荧光、透明承印物、镜面反射） | 产 `info: surface_effect_unmodeled`，**不给 `pass`**，也不给 `fail`；报告注明"该材质不在判据覆盖内" |
| G6 | M5 请求了 oracle 但引擎缺失 | `skipped: "oracle_absent"`；M3 判定保持不变，`agreement` 字段不产出 |

- **gray 的唯一合法表达** = `threshold_status` / `skipped` / `severity` 降级**三者之一**，而**不是** `verdict` 的第四个值。
- **禁止"用 `pass` 表示不知道"**：G1–G6 任一触发时，该条目不得以 `ok`/`pass` 形式出现。

**M5 的 `skipped` 值（同一原则：没跑就说没跑；一处定义在此，K25 的落地词表）**：

| 值 | 触发 | 含义 |
|---|---|---|
| `oracle_absent` | 本机没有任何候选解码引擎（`shutil.which` 全空） | 这一层没跑 |
| `engine_unusable:<detail>` | 引擎在，但驱动不起来（起不来 / 超时 / 退出码与输出无法解释） | 没跑 —— **不等于**"解不出" |
| `sampler_unsupported:<symbol>` | 模块图案表没建模该符号（2D、图案表外的 1D） | 不猜图案 |
| `sampler_input_incomplete:<field,…>` | 采样所需参数不全（`x_dimension_mm` / `target_dpi` / `quiet_zone_mm` / `bar_height_mm`），或 M3 已判 `input_incomplete` | 不补默认值 |
| `sampler_unmodelled_colour:<…>` | 颜色 / 照明超出建模面（与 G5 同族：`ir` 或表外照明） | 不猜灰度 |
| `sampler_unencodable_data:<symbol>` | 字符流与图案表结构不符（长度 / 字符集 / 没有 `encoding_plan`） | 不产出半条模块行 |

- **`engine_unusable` 与"解不出"必须分开**：把前者读成后者会凭空产出一条 `m3_laxer`
  并逼人去"修"一个并不存在的 M3 bug（`plan/HANDOFF-M5` §二.7）。
- 这些值**只出现在 `oracle` 报告**里；`check` 的主报告不因本机装没装引擎而改变一个字。

### 8.10 符号可行性（M2）

- **判据三段，全部数据驱动**（`src/bpreflight/data/vectors/symbol_profiles.json`）：
  ① **字符集 ⊆**：数据里每个字符都在该符号某个模式的字符集里；
  ② **长度 ∈**：定长符号必须精确匹配（**含校验位**），变长符号必须落在 `[min, max]`；
  ③ **模式可覆盖**：字符集 / 分组宽度 / 优先级决定切分。
- **切分唯一**：从前往后贪心取最长可覆盖段；同长时按数据文件里的 `priority`，再按模式名。
  `tie_break: "longest-first"` 写进 `encoding_plan`，不是隐含约定。
- **`encoding_plan`**：`{symbol, mode, segments[], total_modules, checksum, tie_break,
  profile_version}`。`mode` 单段时是模式名、多段时为 `mixed`；`segments` 的 `text`
  顺序拼接必须等于被编码的字符流（元素串按 `AI+value` 重建，变长字段后跟 FNC1）。
- **`(01)` 与零售符号**：AI 01 是 GTIN-14；零售形态 = 去掉固定的前导零
  （GTIN-13 去 1 位、GTIN-12 去 2 位、GTIN-8 去 6 位）。前导位必须**真的是零**，
  否则那是另一个 GTIN（结构原因）。**禁止**把"不可"写成"国家前缀不兼容"——
  前缀归属要 GEPIR 联网授权，属非目标。
- **未核纪律**：本轮没有取到任何符号规范原文，`symbol_profiles.json` 的每条规则都是
  `status: "unverified"`。由未核规则派生的 `error` 级判定默认降为 `warn` 并标
  `threshold_status: "unverified"`；`--strict-thresholds` 恢复 `error`。
  **不得**把这些值写成规范要求。
- **校验位不复制**：`encoding_plan.checksum` 的 GS1 值由 `gs1/checksum.py` 复核
  （`verified: true` = 用单一实现验过）；`mod103` / `mod43` / Reed–Solomon 只在数据文件里
  记名字，**M2 不实现**（由编码器负责）。
- **不可判通道**：没给 `symbol` → `skipped: symbol_not_specified`；元素串解析不出元素 →
  `skipped: symbol_data_unparsed`；GS1 数据 + 2D 符号的 FNC1 首位置**未建模** →
  `skipped: gs1_2d_fnc1_not_modelled`。三者都**不是** `pass`。
- **finding id（M2）**：`symbol_charset_violation` / `symbol_length_mismatch` /
  `capacity_exceeded` / `symbol_structure_mismatch` / `gs1_data_missing_fnc1`
  （error 基线）；`mode_switch_required`（info）。`target = symbol:<symbol>:<scope>`。
  `checksum_mismatch` **不产出**：校验位由 M1 的 `invalid_csum` 判，M2 不重复第二份。

### 8.11 文件身份摘要（行尾归一）——M6 定稿

**定义**：凡是"对随包数据文件算摘要"的地方（`dict_sha256` / `vectors_sha256` /
`symbol_profiles_sha256`，以及 `fixtures/manifest.json` 的 `thresholds_sha256`），
摘要面都是 **把 `\r\n` 归一成 `\n` 之后的字节流**（`src/bpreflight/canonical.py`），
**不**是磁盘上的原始字节。

**为什么**（M6 实测，发布阻塞级）：同一个 blob 在 Windows（Git for Windows 默认
`core.autocrlf=true`）检出为 CRLF，在 Linux/macOS 上为 LF；`git archive` 也按
`core.autocrlf` 转换。原始字节做摘要 ⇒ 同一份内嵌字典有两个摘要，而运行期校验是
"摘要不符即 exit 3"：实测从 `git archive` 导出的树打出的 wheel，装好后
`dictionary.load()` 直接抛 `DictionaryError`（清单 `1ea02f4e…` vs CRLF 文件 `84359ef1…`）。

**范围与边界**：

- 只归一 `\r\n` → `\n`；**不做** Unicode 归一、不重排 JSON、不修剪空白 —— 摘要仍对内容敏感
  （换版本、改一个数值都会变）。
- **用户输入文件**（`input.input_info` 的 `sha256`）**不归一**：那是"用户给的那份文件"的
  身份，不是随包数据的快照身份。
- 配套 `.gitattributes` 的 `* text=auto eol=lf`：代码侧归一保证正确性，仓库侧钉 LF 保证
  克隆 / 导出 / 打包三条路字节一致。两者缺一：只有前者 —— 摘要一致但包内字节仍随平台漂；
  只有后者 —— 老克隆仍可能带着 CRLF。

---

## 九、未核对项清单（⬜ / ⚠️，不得当已验证）

| # | 项 | 状态 | 原因 |
|---|---|---|---|
| 1 | 全部 ISO/IEC 编号（15417 / 15420 / 16388 / 16022 / 18004 / 15418 / 15416） | ⚠️ | iso.org 403，未能直连任何条款 |
| 2 | 各符号的静区模块数（EAN/UPC、Code 128、Data Matrix、QR 等） | ⚠️ **M3 已落库但全部 `unverified`** | gs1.org 403；仅二手。判定已接：未核项降级为 `warn`，`--strict-thresholds` 恢复 `error`；结构档（零静区）不依赖这些数字 |
| 3 | 零售 POS 放大率区间 80%–200% | ⚠️ | 仅 BarStripeLab 源码（1★）见到 |
| 4 | 名义 X = 0.330 mm、条高 22.85 mm、放大率区间、贴近带 1.2 | ⚠️ **M3 已接判定** | 二手；须核 GenSpec 原表。放大率与条高已外置并降级；贴近带是工程判据（不降级） |
| 5 | `yymmd0` 在 11/13/15/17 四类日期上的逐条适用性 | ✅ **M1 已核对** | 以字典原文行逐条确认（实为 8 条：11/12/13/15/16/17/4324/4325，见 §3）；同族 `yymmdd` 6 条、`yyyymmdd` 2 条另计 |
| 6 | 各符号的容量/模式切换表 | ⚠️ **M2 已落库但全部 `unverified`** | 规范原文仍 403；`symbol_profiles.json` 每条规则带 `source`/`status`/`verified_at`，未核规则派生的判定降级为 `warn`（§8.10）；官方编码器交叉验证未做 |
| 7 | zxing-cpp / zbar 本机可用性 | ✅ **M5 已实测探测** | `zxing-cpp` / `ZXingReader` / `zbarimg` 在本机 `shutil.which` 全为空 ⇒ `oracle` 走 `skipped: oracle_absent`。**真引擎的解码路径本轮未验证**（命令模板未被观测过）；一致性三态用可注入的解码器替身验过（替身读的是真实落盘的 PNG 像素） |
| 8 | StackOverflow 正文页 | ⚠️ | 本轮取到检索摘要，未逐页直取正文 |
| 9 | en.wikipedia.org / Google / DuckDuckGo | ⬜ | 000 超时 |
| 10 | 本机 Python 运行时 | ✅ **已确认** | `python` / `python3` 指向 Windows Store 占位（执行即 exit 49）；可用解释器 `py -3.8` = 3.8.8、`py -3.12` = 3.12.10。M3 起双通道实跑；历史真值：M4 时点 269 条、M5 时点 299 条。**M6.1 起 `requires-python` 抬到 `>=3.12`**（3.8 已 2024-10-07 EOL，且 SPDX license 需 `setuptools>=77` 而它要求 py>=3.9），当前实测 `py -3.12 -m pytest -q` → **306 passed**，由 `tests/test_reported_counts.py` 常驻守 |
| 11 | M5 采样器的模块图案表（`src/bpreflight/data/vectors/sampler_patterns.json`） | ⚠️ **全部 `unverified`** | 零售符号（EAN-13）的模块图案属公开常识，但本轮同样没取到规范原表（`iso.org` / `gs1.org` 403），且**真引擎未复核**。表内只放 `L` 组 10 个 7 位码，`R` = `complement(L)`、`G` = `reverse(complement(L))` 由装载期派生，parity 表逐首位；结构不变量（L 奇校验、G 偶校验、守卫、95 模块）由 `tests/test_oracle.py` 常驻断言。**不得**把它写成规范要求 |

---

## 十、引用与更新

- 官方依据：`gs1/gs1-syntax-dictionary`（Apache-2.0）、`gs1/gs1-syntax-engine`、（可选）`ref.gs1.org` JSON-LD。
- 需求原话：StackOverflow 问题页 / GitHub issue，按编号引用（见 `plan/01-题目文档.md` §2.4）。
- 任何引用若与页面现状不符，**以页面现状为准**，并更新本文件（记更新日期）。
- **本文件改动必须先于或同提交于代码改动**；阈值类改动须同时更新 `src/bpreflight/data/vectors/*.json` 的 `status` 与 `verified_at`。
