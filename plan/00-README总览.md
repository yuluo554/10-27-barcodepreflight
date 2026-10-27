# 00 · README 总览 — 10-27-barcodepreflight（条码印前可扫描性审计器）

> 方法论：`ai-tool-project-sprint`（装订 2026-10-27）｜布局门：`py -3.12 tools/check_sprint_layout.py`｜续接对话第一件事 = 跑它

- **性质**：不参赛项目题 · 发布 GitHub **公开仓库** · 署名 **yuluo554**
- **产出**：仓库 `10-27-barcodepreflight`，CLI 入口 `bpreflight`
- **形态**：**纯本地 CLI**（零网络、参数驱动；开源解码器只作可选 oracle）
- **基准日**：2026-10-27｜**代理实际检索窗口 2026-10-27T10:56Z – 11:14Z**
- **当前状态**：**M1 数据先已完成**（内嵌官方 AI 字典（commit 钉版 + 逐行哈希校验）+ 校验位单一实现 + 四个语义解释器 + GTIN/SSCC/日期/字符集/长度校验；`implementation_pending` 已退役）；**M2–M6 未开工**。远端未建，所有 CI 类结论均为"本地等价校验（未接远端，CI 待首推验证）"。
- **定位宣言**："生成器是红海（JsBarcode **5896★** / zint **821★** / python-barcode **658★** / BWIPP **504★**），GS1 AI 解析也已被官方参考实现占住（`gs1/gs1-syntax-engine` **52★**）。**空白在'印出来扫得出吗'这一层**：从生成参数（符号类型、X-dimension、静区、目标 DPI、条/空颜色、条高、放大率）直接判定'这个条码印出来会扫不出'并给可执行修复项——**不依赖图像采集**。"

---

## 一、文档索引表

| 文档 | 内容 | 状态 |
|---|---|---|
| `plan/00-README总览.md` | 本文档：索引 / 决策记录 / 弃选项 / 承诺-证据台账 / 里程碑 | ✅ v3（M1 收尾） |
| `plan/01-题目文档.md` | 十段式题面：头部 / 介绍 / 五模块任务 / 提交材料 / 评分 / 锚点 / 边界 | ✅ v1 |
| `plan/02-架构与技术选型.md` | 分层 / 模块边界 / 技术选型 / 构建 / 确定性 / 被否方案 | ✅ v1 |
| `plan/03-模块详设.md` | 通用契约（Finding/id 词表/fingerprint）/ CLI 契约 / M1–M5 详设 / 测试面 | ✅ v1 |
| `plan/04-数据计划.md` | 数据清单 / 真值纪律 / 阈值三态 / 生成与冻结 / 已知缺口 | ✅ v1 |
| `plan/05-里程碑与发布.md` | 里程碑表 / **状态表** / 逐里程碑 DoD / 已知未验证项 / 风险登记 | ✅ v2（M1 收尾） |
| `plan/06-交付对标与决策.md` | 评分对标 / 风险登记 / 缺口 / 决策 D14–D20 | ✅ v2（M1 收尾） |
| `plan/HANDOFF-M1.md` | 第 1 棒交接单（七节） | ✅ v1（已收尾） |
| `plan/HANDOFF-M2.md` | 第 2 棒交接单（七节） | ✅ v1 |
| `data/README.md` | 依据查证三态 + 已占位矩阵 + AI 字典实证 + 校验位自证 + 印刷数值二手标注 + 数据源可获取性 + 合成数据纪律 + **数值口径唯一定义（§8）** + **内嵌快照身份（§3.1）** | ✅ v2（M1 收尾） |
| `AGENTS.md` | 方法论锚点：布局门命令、强制布局清单、环境事实 | ✅ v1 |
| `README.md` | 对外 README：定位、安装、用法、退出码、状态表 | ✅ v2（M1 收尾） |
| `LICENSE` | Apache-2.0 全文 | ✅ v1 |
| `.gitignore` | Python 标准模板 + `*.png` 等生成产物不入仓 | ✅ v1 |

**待建（按里程碑产出，不预先占位）**：`src/bpreflight/symbols/`（M2）、
`src/bpreflight/print/`（M3）、`src/bpreflight/oracle/`（M5）、`tools/gen_fixtures.py`（M3）、
`plan/RELEASE-M6.md`（M6）。

> `src/bpreflight/gs1/`（M1）与 `src/bpreflight/data/gs1-syntax-dictionary/`（M1）**已落盘**，
> 从"待建"移到本表上方。

> 状态图例：✅ 已落盘 · 🟡 进行中 · ⬜ 待做。**状态列必须与里程碑同步翻转（同一提交内改）。**

---

## 二、决策记录表

> 含已定案决策与**弃选项**（弃选理由写死，后续里程碑不再重复论证）。

| # | 日期 | 决策 | 结论与理由 |
|---|---|---|---|
| **D1** | 2026-10-27 | **最重要的反直觉结论：GS1 AI 解析**不是**空白** | 官方 `gs1/gs1-syntax-engine` **52★**/12（2026-10-08）已占住 AI 元素串 / Digital Link 的解析**与校验**，C 核心 + 多语言绑定，lint 集含 `lint_csum`/`lint_yymmd0`/`lint_iso3166`/`lint_iban`/`lint_gcppos1\|2`；配套 `gs1/gs1-syntax-dictionary` **21★**/3 提供机器可读 AI 表 + Linter 规则集。**→ 本题必须内嵌官方字典，绝不自造 AI 表；M1 只实现 `req`/`ex`/`yymmd0`/`csum` 四个语义解释器。** 若立项做第三方 AI 解析器，等于正面撞官方参考实现。 |
| **D2** | 2026-10-27 | **印刷阈值只能二手印证，须以 GenSpec 原表为准** | 本轮 `gs1.org` **403**、`iso.org` **403**，因此：①**静区模块数**一个都没核实到；②放大率 **80%–200%** 仅在 `BarStripeLab`（1★）源码见到；③名义 X **0.330 mm**、条高 **22.85 mm（⇒69.24 模块）**均为二手。**→ 全部阈值外置到 `src/bpreflight/data/vectors/*.json`，每项带 `{source, status, verified_at}`；未核阈值在门禁里降级为 `warn`（不拦死）+ 报告标 `threshold_status: "unverified"`。落地前 2–3 天取数核对 GenSpec 原表，但此核对不阻塞 M1–M2。** |
| **D3** | 2026-10-27 | **校验位算法必须有向量回归——同一组向量当天抓出两次写法错误** | ①代理先按"数据位自右向左交替 3/1"实现，**与官方向量不符**（得 `…79`/`…06`，正确应 `…73`/`…08`）；重读官方 `gs1-syntax-dictionary/src/lint_csum.c` 后确认真规则："**权重按含校验位的全长决定起始**（偶长起 3、奇长起 1），**自左**交替 3/1，只对数据位求和，`check=(10-sum%10)%10`"。②把该规则写进 `data/README.md` §8.1 时，交替权重误写成 `6 - W`（应为 `4 - W`），同组向量立刻 1 PASS / 3 FAIL；改正后 `02345673` / `416000336108` / `09501101530003` / `4006381333931` 全 PASS。**→ M1 验收不是"实现完了"，而是"四个向量全 PASS + 手算留痕可复核"；实现里只允许一个校验位函数，不接受两套算法并存。** |
| **D4** | 2026-10-27 | **ISO/IEC 编号一律 ⚠️ 未核实** | `iso.org` **403**、`en.wikipedia.org` **000**、搜索引擎 **000** → **本轮没有任何 ISO/IEC 编号被直接核实**。凡 15417 / 15420 / 16388 / 16022 / 18004 / 15418 / 15416 **一律加 ⚠️ 并注明"落地前需核对"**。GS1 侧事实改走**官方源码 / 官方 JSON-LD** 实证（可追溯、可复跑）。 |
| D5 | 2026-10-27 | **GitHub search 限流 ≠ 0 结果** | 检索中途触发 **HTTP 403 secondary rate limit**。命中限流的检索式**一律记「⬜ 未取」**，绝不写成 `total_count = 0`。题面里出现的 0 结果只来自**请求成功**的检索式，且全部标为**软论据**。 |
| D6 | 2026-10-27 | **M3 不做图像式 ISO/IEC 15416 分级** | 15416 的 `SC`/`MOD`/`DEF`/`DEC` 需要**真实印刷品的扫描图像**，属图像采集域（`EnricoPittini/Barcodes-verification` 14★ 已占）。本题是**参数域**审计：从生成参数推风险。**不输出 A/B/C/D/F 等级**，引用 15416 ⚠️ 仅作术语对齐。 |
| D7 | 2026-10-27 | **许可证 = Apache-2.0（已定案）** | 与内嵌 `gs1-syntax-dictionary` 同许可，NOTICE/归属最简单，含专利授权条款；`LICENSE` 已落盘，`src/bpreflight/data/gs1-syntax-dictionary/` 内随附上游许可与来源哈希（M1 落字典时同做）。 |
| D8 | 2026-10-27 | **首期实现语言：Python ≥ 3.8（已定案）** | CLI 分发成本低、JSON/字典解析成熟；M5 采样器用 `array`/`struct` 足够。下限取 3.8 由 `tools/check_python_floor.py` 守（本机实测 `py -3.8` = 3.8.8 可跑）。若 M5 的 zxing-cpp 绑定不可用，则 M5 退化为"可选外部命令"，不阻塞 M1–M4。 |
| D9 | 2026-10-27 | **`fix` 字段是必填契约，不是"建议"** | M3 每个 `warn`/`error` 必须给**可执行修复**（目标数值或目标方向 + 最小增量）。理由：本题的差异化不是"发现问题"——`BarStripeLab` 已经在做 `scan-safety estimate`——而是**"发现问题并给出能直接改参数的修复项"**。`{"fix": "请检查你的条码"}` 视为缺陷。 |
| D10 | 2026-10-27 | **M5 只做一致性对照，不改 M3 判定** | `agreement ∈ {consistent, m3_stricter, m3_laxer}`。`m3_stricter` 记入 `known-disagreements`（可能是假阳性）；**`m3_laxer` 必须当 bug 修**（M3 判安全但 oracle 解不出）。这样"参数判定"和"实测判定"的差异变成**一等公民**，而不是被藏起来。 |
| D11 | 2026-10-27 | **报告默认无时间戳** | 确定性优先：同输入两次导出必须 byte 级一致。需要时间信息时用 `--with-timestamp`，报告头标 `"deterministic": false`。 |
| D12 | 2026-10-27 | **数值口径单点定义在 `data/README.md` §8** | 校验位算法 / 静区判定 / 放大率区间 / DPI 阈值 / 灰度条件 / 退出码 / 报告字段全部只在 §8 出现一次；`plan/01` 中的数字是**摘要**。**修改必须先改 §8 并同提交同步。** 代码里出现裸阈值字面量由 `tools/check_thresholds.py` 静态拦。 |
| D13 | 2026-10-27 | **仓库名与 CLI 名的重名检查推迟到 M6，但列入 DoD** | `bpreflight` / `10-27-barcodepreflight` 发布前须核对 PyPI 与 GitHub 同名占用；若占用则改名并记录映射。⬜ 未执行。 |
| D14 | 2026-10-27 | **首期输入格式只收 JSON** | `tomllib` 是 3.11+，而 `requires-python >= 3.8`；为 TOML 引第三方库违反零依赖红线。**扩展名不符即 exit 3，不做内容嗅探**。TOML 列二期。详见 `plan/06` §四。 |
| D15 | 2026-10-27 | **运行期数据全部随包安装** | 向量与字典放 `src/bpreflight/data/`，不放仓库根 `data/`/`vendor/`：`package-data` 的 glob 不递归且根目录数据进不了 wheel（`references/release.md` 安装面条）。`tests/test_package_data.py` 断言"装好的能读到"。 |
| D16 | 2026-10-27 | **骨架期用 `implementation_pending` 而非空 findings** | 空 findings 会派生 `verdict: pass`，等于"工具说这个条码没问题"。用一条 `error` 级 finding 让骨架必然 fail，M1 落地同提交退役。详见 `plan/03` §二。**✅ 2026-10-27 到期已履行**：该 id 已退役，换成两条更强的不变式——"该 id 不再出现"与"`pass` 只在真有判定发生时可能出现"（`plan/HANDOFF-M2` §二）。 |
| D17 | 2026-10-27 | **本轮不建远端、不推送** | 用户明示"先写好计划、部署骨架"。所有 CI 类结论写"本地等价校验（未接远端，CI 待首推验证）"，M6 补记真实 run id。 |
| D21 | 2026-10-27 | **M1 三条落地口径（都是"拒绝假装"的形态）** | ① **字典 / 向量装载失败 = exit 3**（§8.5 明列的第三类 `3`），不产任何领域结论——"读不到字典"不是关于条码的判定；② **`gcppos1/2` 不实现**：要 GCP 分配库（GEPIR，联网授权）才能判，属 `plan/01` §7 非目标 → 走 `skipped: gcp_lookup_unavailable`，**不冒充已判**；③ **YY→CCYY 的世纪窗口固定在数据文件**（`gs1_vectors.json`，不读系统时钟），否则同一输入会因跑的年份不同而产出不同报告（违反 K10）。 |

---

## 三、弃选项（理由写死，后续不再论证）

| 弃选项 | 理由 |
|---|---|
| **做条码生成器** | 红海：JsBarcode **5896★**/1113fork、zint **821★**/172（50+ 符号、GS1 数据校验强）、python-barcode **658★**/139、BWIPP **504★**/80、treepoem 164★、pyStrich 108★。再做一份只是第三份同类实现，且生成器天然不回答"印出来扫得出吗"。 |
| **做符号编解码库** | zxing **34185★**、quagga2 5212★、zxing-cpp **2070★**、zbar 1385★、pyzbar 832★ 已饱和且持续维护；重造等于用最贵的力气做最没有差异的事。**解码器只作 oracle，且只在 M5（可选）。** |
| **做纯 GS1 AI 解析器 / 校验器** | D1：官方 `gs1-syntax-engine` 52★ 已占且 lint 完整。立项即正面撞官方实现。**降级为 M1 内嵌。** |
| **做 GTIN/SSCC 主数据一致性（含厂商前缀归属）** | 需 **GEPIR 联网授权**，与"纯本地零网络"红线直接冲突；且数据正确性不是印刷可读性问题。 |
| **做图像式 ISO/IEC 15416 ⚠️ 验证器** | `EnricoPittini/Barcodes-verification` **14★** 已存在，且需要**真实扫描/图像采集**（硬件 + 采集条件 + 打光），不是参数能算的。本题明确不做分级（D6）。 |
| **做色彩管理 / ICC 处理** | 不做颜色变换，只做阈值判定（亮度对比 + 波长通道）。引入 lcms 会突破零依赖与"参数域"定位。 |
| **做扫描器型号适配库** | 各型号解码算法是黑箱且会版本变更；承诺"某型号能扫"无法兑现。只给风险等级 + 依据。 |
| **做 GUI / 服务端 / watch 模式** | 纯本地 CLI，接 CI 才是真实用法。 |
| **做复合码（CC-A/B/C）、Aztec、PDF417、MaxiCode、DotCode** | 首期范围外；每增一个符号就增一份容量/字符集表，必须逐个核规范（iso.org 403 未核实），收益不抵风险。二期候选。 |
| **做"自动修图"（按 `fix` 直接改参数并重新生成）** | 生成器是红海（见上），且"改完再生成"会让工具变成半个生成器，破坏"只审计不生成"的边界。`fix` 只给**目标数值**，由用户在自己的生成链里改。 |

---

## 四、承诺-证据台账（全项目唯一一份）

> 规则：**只此一份**，其他文档只引用不复述。状态：✅ 已达 · 🟡 进行中 · ⬜ 待做。

| 承诺项 | 素材来源 | 交付物内可达性 | 核验方式 | 状态 |
|---|---|---|---|---|
| 五模块 M1–M5 全部交付 | `plan/01` §3 | 源码 + 测试 | 各模块验收例逐条跑 | ⬜（已交付模块见 §六里程碑表） |
| 校验位四向量全 PASS（且只有一个实现） | `data/README.md` §4（官方 `lint_csum.c` + 单测向量） | 内嵌 | `pytest tests/test_checksum.py`；源码里 `gs1_check_digit` 只定义一次（AST + 文本双判据） | ✅ M1 |
| 校验位手算留痕可复核 | `data/README.md` §4.2 | 文档 | 逐行手算复现 | ✅（文档已落盘） |
| AI 表来自官方字典（不自造） | `gs1-syntax-dictionary` Apache-2.0 | `src/bpreflight/data/gs1-syntax-dictionary/` + `data/vectors/dict_manifest.json` | 报告头含 `dict_version`；字典文件哈希与清单一致（每次运行复算） | ✅ M1 |
| `yymmd0`（DD=00 → 当月最后一天）不被误判 | `data/README.md` §3；源码规则名 `lint_yymmd0` | M1 | 单测：`(17)251200` 不报 `invalid_date`，报 `dd00_last_day_of_month`（info）→ 2025-12-31；对照 `(17)251301` 必须报 `invalid_date` | ✅ M1 |
| `req` 的 OR / AND 语义正确 | 字典原文 `req=01,02,03` / `req=01+21` | M1 | 两条单测（缺 OR 组 / 缺 AND 项） | ✅ M1 |
| `ex` 互斥正确 | 字典原文 `ex=255,37` | M1 | 单测：`(01)`+`(255)` → `mutually_exclusive_ai` | ✅ M1 |
| 静区为零可复现（BinaryEye #616 类）—**零标准数字锚点** | GitHub #616 原话 | M3 | fixture：`quiet_zone_mm=0` → `quiet_zone_absent`（恒 `error`，与阈值状态无关） | ⬜ |
| 静区不足可复现（python-barcode #41 类） | GitHub #41 原话 + `src/bpreflight/data/vectors/quiet_zone.json` | M3 | fixture：`quiet_zone_mm=0.6, X=0.330`（`qz=1.818`）< 占位 `modules_min` → `quiet_zone_insufficient` + `fix.to = modules_min × X` | ⬜ |
| 放大率边界逐条测 | `data/README.md` §8.3 | M3 | `0.2640`/`0.6600` 不报；`0.2639`/`0.6601` 报警 | ⬜ |
| DPI 混叠可判 | `data/README.md` §8.3 | M3 | `X=0.330, DPI=120 → 1.559 → warn`；`DPI=100 → 1.299 → error`；`DPI=203 → 2.637 → ok` | ⬜ |
| 红条 + 红光判不可读（且与亮度对比分列） | `data/README.md` §8.4 | M3 | 两个 `id` 不同，不合并 | ⬜ |
| 未核阈值降级而非拦死 | 决策 D2 | M3 + M4 | 把 `status` 改 `unverified` 后同测试由 `error` 变 `warn`；`--strict-thresholds` 恢复 `error` | ⬜ |
| `fix` 字段必填且给目标数值 | 决策 D9 | M3 | 测试断言每个 `warn`/`error` 的 `fix` 含 `to` 或 `min_delta` | ⬜ |
| 退出码矩阵全覆盖 | `data/README.md` §8.5 | M4 | `tests/test_exit_codes.py`：`--fail-on` 三档 × 三种问题态 + 三类用法错误，逐格一条 | ⬜ |
| JSON / MD 同源（按 fingerprint 相等） | `data/README.md` §8.7 | M4 | `test_report.py::test_two_formats_same_findings` | ⬜ |
| `fingerprint` 稳定、不含时间戳/路径 | `data/README.md` §8.7 | M4 | 两次独立 run 的 fingerprint 集合相等 | ⬜ |
| 首屏三段字面固定 | `plan/01` §M4 | M4 | 字面断言 | ⬜ |
| M5 oracle 一致性三态（`consistent`/`m3_stricter`/`m3_laxer`） | 决策 D10 | M5 | `m3_laxer` 计为 bug；`out/oracle-report.json` 落盘 | ⬜ |
| 每模块 1 点样本 oracle 解不出 + M3 判 `raster_alias_high_risk` | `plan/01` §M5 | M5 | 双断言 | ⬜ |
| 纯本地零网络（AST 扫网络导入） | 隐私红线 | 全 | `tests/test_no_network.py`（AST 扫 `socket`/`urllib`/`requests`/`http`） | ✅ M0 |
| 阈值无裸字面量（除 `src/bpreflight/data/vectors/*.json`） | 决策 D12 | 全 | `py -3.12 tools/check_thresholds.py` 0 命中 | ✅ M0 |
| 不可判（gray）六种情形全部有显式通道，且**不借用 `pass`** | `data/README.md` §8.9 | 全 | 每种情形一条测试，断言不出现 `verdict: pass` 且带对应 `threshold_status`/`skipped`/`info` | ⬜（数据层的三条通道已落，见 `plan/03` §三） |
| 输入参数缺失时拒绝判定（不静默补默认值） | `data/README.md` §8.9 G3 | M3 | 缺 `x_dimension_mm` → `input_incomplete`（error），不出现任何 `quiet_zone_*` / `magnification_*` 结论 | ⬜ |
| 三态查证齐（✅/⚠️/⬜） | `data/README.md` | 文档 | 人工核对 + §9 未核清单 | ✅（骨架期） |
| ISO 编号全部 ⚠️ 标注 | 决策 D4 | 文档 | `grep -n "ISO/IEC"` 逐条看是否有 ⚠️ | ✅（骨架期） |
| 发布：tag + GitHub Release 附产物 + 发布留档三件套 | 发布纪律 | 公开仓库 | `plan/RELEASE-M6.md` §覆盖对账无空项 | ⬜ |

**台账外的"永不进判定路径"项**（写清以免被当欠债）：
- **GEPIR / 主数据** —— 需联网授权，永不实现（弃选项）。
- **图像式 15416 分级** —— 需真实扫描，永不实现（D6）。
- **复合码 / Aztec / PDF417 / MaxiCode / DotCode** —— 二期候选，首期不承诺。

---

## 五、承诺 → 文件路径 → 里程碑 → 核对命令（提交材料实物表）

| 承诺项 | 应存在的文件路径 | 里程碑 | 核对命令 |
|---|---|---|---|
| CLI 可运行入口 | `pyproject.toml`（`[project.scripts] bpreflight`）+ `src/bpreflight/cli.py` | M1 | `git ls-files pyproject.toml src/bpreflight/cli.py`；`bpreflight --help` |
| 校验位单一实现 | `src/bpreflight/gs1/checksum.py` | M1 | `grep -rc "def gs1_check_digit" src/` == 1；`pytest -q tests/test_checksum.py` |
| 官方 AI 字典（内嵌） | `src/bpreflight/data/gs1-syntax-dictionary/`（正文 + `LICENSE` + `NOTICE`）+ `src/bpreflight/data/vectors/dict_manifest.json` | M1 | `git ls-files src/bpreflight/data`；哈希与 manifest 一致 |
| GS1 向量集 | `src/bpreflight/data/vectors/gs1_vectors.json` | M1 | `git ls-files src/bpreflight/data/vectors/gs1_vectors.json`；`pytest -q tests/test_gs1_semantics.py` |
| 符号 profile 表 | `src/bpreflight/data/vectors/symbol_profiles.json` | M2 | `pytest -q tests/test_symbols.py`（跨符号等价性 3 组） |
| 印刷阈值 | `src/bpreflight/data/vectors/quiet_zone.json`、`gen_spec.json` | M3 | 每项有 `source`/`status`/`verified_at`（测试断言字段齐全） |
| 颜色用例 | `src/bpreflight/data/vectors/color_cases.json` | M3 | `pytest -q tests/test_color.py` |
| M3 五项检查 + `fix` | `src/bpreflight/print/` | M3 | `pytest -q tests/test_print_audit.py` |
| 报告器 | `src/bpreflight/report/`（model / render_json / render_md） | M4 | `pytest -q tests/test_report_render.py` |
| 退出码测试 | `tests/test_exit_codes.py` | M4 | `pytest -q tests/test_exit_codes.py`（矩阵逐格） |
| 阈值静态扫描门 | `tools/check_thresholds.py` | M3 | `py -3.12 tools/check_thresholds.py` 0 命中（M0 已落） |
| fixture 生成器 | `tools/gen_fixtures.py` + `fixtures/manifest.json` | M3 | 重跑哈希不变 |
| oracle 回读 | `src/bpreflight/oracle/` + `out/oracle-report.json`（不入仓） | M5 | `bpreflight oracle --help`；缺 oracle 时 `skipped: oracle_absent` |
| 零网络守门 | `tests/test_no_network.py` | M4 | `pytest -q tests/test_no_network.py`（M0 已落） |
| 发布留档 | `plan/RELEASE-M6.md` | M6 | `git cat-file -e <tag>:plan/RELEASE-M6.md` |

> 每一项都必须指得到一个文件；指不出的现在就删，不留到评分表里变成无主承诺。

---

## 六、里程碑

| 里程碑 | 内容 | DoD（完成判据） | 状态 |
|---|---|---|---|
| **M0 · 计划与骨架** | 装订三件（`AGENTS.md` + 五道门 + `plan/00` 装订行）+ `plan/00`–`06` + 可运行 CLI 骨架 + 报告层 + 五道门 + CI | 五道门本地全绿且**变异验证逐条变红**；`pytest` 双解释器全绿；`bpreflight check` 可跑并产出确定性 JSON/MD；`plan/HANDOFF-M1.md` 落盘 | ✅ |
| **M1 · 数据先行** | 内嵌官方 AI 字典（`gs1-syntax-dictionary` Apache-2.0）+ 四个语义解释器（`req`/`ex`/`yymmd0`/`csum`）+ 校验位向量集 + GTIN/SSCC/日期/字符集/长度校验 | 四个官方向量全 PASS 且**只有一个**校验位函数；`yymmd0`/`req`/`ex` 用例逐条过；`dict_version` 进报告头；`report.header.dict_sha256` 可复算 | ✅ |
| **M2 · 符号合法性** | `symbol_profiles.json` 数据驱动 + 八符号的结构性可行性 + 容量/字符集/模式切换 + 跨符号等价性 | 跨符号等价性 3 组逐条有原因；`encoding_plan.segments` 切分唯一（`tie_break: longest-first`）；校验位不在 M2 复制第二份 | ⬜ |
| **M3 · 印刷可读性** | 五项检查（静区/放大率/DPI 混叠/条高/颜色）+ `fix` 必填 + 阈值外置带三态 | **`quiet_zone_absent`（零静区）恒 error 且不依赖任何未核数字**；`quiet_zone_insufficient` 按阈值状态升降；python-barcode #41 类场景可复现；放大率边界 4 值逐条测；DPI 四值边界逐条测；阈值项未核降级为 `warn` 且 `--strict-thresholds` 恢复 `error`（**DPI/颜色两项不参与降级**）；`tools/check_thresholds.py` 0 命中 | ⬜ |
| **M4 · 报告与门禁** | JSON + MD 同源 + 退出码矩阵 + `--fail-on` + fingerprint | 退出码矩阵逐格全覆盖；两格式 `findings` 按 fingerprint 完全相等；首屏三段字面断言；零网络 AST 扫 0 命中 | ⬜ |
| **M5 · 仿真回读（可选）** | 最小采样器 + zxing-cpp oracle + `agreement` 三态 | 每模块 1 点样本：oracle 解不出且 M3 判 `raster_alias_high_risk`（一致）；健康样本一致；红条+红光一致；`m3_laxer` 记为 bug；oracle 缺失标 `skipped: oracle_absent` | ⬜ |
| **M6 · 发布** | 公开发布 | **DoD = `git tag` + GitHub Release（附产物：sdist + wheel + `SHA256SUMS`）+ 发布留档 `plan/RELEASE-M6.md`（tag 前落盘进 tag 树，"tag 时点事实 / tag 后追加事实"两栏）**；发布为 **GitHub 公开仓库**；许可证已落定（D7）；仓库名/包名重名已核对（D13） | ⬜ |

> **M1 排在最前是刻意的**：校验位与 AI 语义是**唯一有官方 oracle 的部分**，先把这块钉死（向量 + 官方字典），后面的判定才有可信基座。M3 是差异化核心，但它建立在 M1/M2 的"数据合法"前提上——数据层不合法时，印刷层判定的意义有限。
>
> **兑现记录（2026-10-27）**：M1 已收尾——字典按 commit 钉版入库、整表 224 条目 → 541 个具体 AI
> 逐行解析、四官方向量全 PASS、`implementation_pending` 同提交退役。风险 R2 的缓解条款
> （"退役不等于敢说 pass"）换成两条更强的不变式，见 `plan/HANDOFF-M2.md` §二。

---

## 七、工作纪律（本项目通用）

- **纯本地零网络**：运行时不发任何请求；文档里的 URL 只作依据引用。
- **阈值零硬编码**：所有阈值来自 `src/bpreflight/data/vectors/*.json`；源码出现裸字面量即失败（`tools/check_thresholds.py`）。
- **三态标注**：任何外部事实必须标 ✅ / ⚠️ / ⬜；ISO/IEC 编号一律 ⚠️。
- **限流不是 0**：GitHub 限流导致的未取，记 ⬜ 未取，不记 0。
- **`fix` 必填**：`warn`/`error` 不给空话。
- **产物不入仓**：`*.png`、`out/`、`reports/` 由 `.gitignore` 排除。
- **品牌隔离**：文档不提名、不比较任何同系列其他项目。
- **数值口径先改 `data/README.md` §8**，再改代码与 plan。
