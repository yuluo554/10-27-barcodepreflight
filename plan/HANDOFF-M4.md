# HANDOFF-M4 · 第 4 棒交接单（报告与门禁）

> 上一棒：**M3 印刷可读性**（✅ 2026-10-27）
> 本棒目标：**M4 报告与门禁**——退出码矩阵逐格覆盖 + JSON/MD 同源（按 fingerprint）+
> 首屏三段字面锁死 + 渲染层零判定 AST 守门。
> 读法：**先跑布局门**（`AGENTS.md` 里的命令），绿了再读本文件。

## 一、当前进度与证据

M3 已完成并验证（**本地等价校验，未接远端，CI 待首推验证**）：

| 交付 | 证据（命令 + 结果） |
| --- | --- |
| 五项检查模块 | `src/bpreflight/print/`：`quiet_zone.py` / `magnification.py` / `raster.py` / `bar_height.py` / `color.py` + `common.py`（降级规则单点）+ `audit.py`（编排 + 缺参拒判） |
| 阈值三态 | `quiet_zone.json` 每行 `{modules_min, required, source, status, verified_at}`；`gen_spec.json` 的 `values` 走同一口径、`engineering_heuristics` **无** status（装载期断言） |
| 静区三档 | 结构档 `quiet_zone_absent`（`required` 侧 == 0）恒 `error` 且 `threshold_status: "not-applicable"`；阈值档随 status；贴近档 `warn`（带宽来自 `quiet_zone_marginal_factor = 1.2`） |
| `quiet_zone_absent` 两态对照 | `tests/test_print_audit.py::test_zero_quiet_zone_is_an_error_regardless_of_threshold_status`：unverified（默认数据）与 **人工改成 verified** 两种情况都是 `error`，且 `threshold_status` 都是 `not-applicable` |
| python-barcode #41 类 | `quiet_zone_mm=0.6` → `1.818` modules → `quiet_zone_insufficient`，`fix.to = modules_min × X = 3.630`（由数据复算，测试算一遍再比） |
| 放大率边界 4 值 | `0.2640`/`0.6600` 不报；`0.2639`/`0.6601` 报（`pytest.mark.parametrize` 逐条） |
| DPI 边界 4 值 + 三实算例 | `1.4999` error / `1.5000` warn / `1.9999` warn / `2.0000` ok；`120→1.559 warn` / `100→1.299 error` / `203→2.637 ok` |
| 颜色两项不合并 | `tests/test_color.py`：红条+红光只出 `wavelength_reflectance_collapse`；红条+白光零 findings；`#C86E00`+红光**两条并存** |
| 未建模面 | `ir` / 未知照明 / 非 `#RRGGBB` 颜色 → 只有 `info: surface_effect_unmodeled`，无对比度结论 |
| 缺参拒判 | 缺 `x_dimension_mm` / `target_dpi` / `quiet_zone_mm` → 只有一条 `input_incomplete`，无任何 `quiet_zone_*` / `magnification_*` / `raster_*` / `bar_height_*` |
| `fix` 必填 | `tests/test_fix_contract.py`：18 条语料覆盖 M1/M2/M3 全部分支，每条 `warn`/`error` 都有 `to`/`min_delta` + `unit`，且 `fix.to` 可由输入复算 |
| fixture 生成器 | `tools/gen_fixtures.py`：31 件 / 7 套件；`--check` 位级 + 结论双向比对；`--suite` 部分运行保留其它条目 |
| 接进 pipeline | `IMPLEMENTED_MODULES = ("M1", "M2", "M3")`；`_module_skips` 恒空（登记点保留）；`PrintResult.judged` 区分"判了且干净"与"没判" |
| 首屏提示可读性 | `THRESHOLDS: unverified (...)` 现在只列**本次判定实际引用**的未核键 + "N more unverified in the book"（34 个键全列会让人不再读这一行） |
| 全量测试 | `py -3.12 -m pytest -q` → **253 passed** |
| 六道门 + 门自检 | 布局/脱敏/阈值/下限/CI 工作流全绿；`tools/verify_gates.py` → **32 组变异：符合预期 32 / 不符合 0**（新增 T3 / F1 / F2 / F3） |
| fixture 自检 | `py -3.12 tools/gen_fixtures.py --check` → 31 件位级一致 |

**M3 的 DoD 在 `plan/05` §三（全部打勾）**。

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **数据读取点仍是四处**（M1/M2 立的口径未变）：
   `bpreflight/thresholds.py`（现在装 **三份**：`quiet_zone.json` / `gen_spec.json` /
   `color_cases.json`）、`gs1/dictionary.py`、`gs1/vectors.py`、`symbols/profiles.py`。
   **M3 没有新建 `print/thresholds.py`**——`plan/03` §五早先那样写，本棒改的是文档措辞
   （见该节"阈值装载单点（修正）"）。**判定模块一处都不许有 `open()`**：
   `tests/test_print_audit.py::test_print_modules_do_not_read_files` 对 `print/*.py` 做 AST 扫描。
2. **降级规则是单点**：`print/common.py` 的 `gen_spec_finding` 是唯一把
   `unverified` 的 `error` 降成 `warn` 的地方；`engineering_finding` 是唯一产
   `not-applicable` 的地方。**新判据一律走这两个构造函数**，不要自己写 if。
3. **结构档故意绕开那个构造器**：`quiet_zone_absent` 在 `print/quiet_zone.py` 里手搓
   `Finding`，`threshold_status: "not-applicable"`、`threshold=None`。理由：它不比较任何
   阈值，只有一个来自数据的结构事实 `required`。**不要"统一"成 `gen_spec_finding`**——
   那会让它重新受降级影响，而它正是"未核也能钉死"的那条验收。
4. **`required` 是数据里的 bool**：装载期 `_validate_quiet_zone` 断言它必须是 bool。
   **不许**改成由 `modules_min > 0` 推断（那会把未核阈值提升成结构事实）。
5. **`symbol` 不算"请求了印刷层"**：`input.PRINT_INPUT_FIELDS` 不含它。
   `input.missing_fields()` 仍把 `symbol` 算进 `PRINT_FIELDS`（M3 判定需要它），
   但"是否请求了这一层"由 `PRINT_INPUT_FIELDS` 决定。**两者不是同一个集合，别合并**：
   合并会让只给 `symbol` + `identifier` 的干净 M1/M2 spec 判成 `fail`。
6. **`PrintResult.judged` 是必需字段**：干净的几何产出零 findings，缺参产
   `input_incomplete`——"零 findings"在这两种情况下含义相反。`pipeline` 靠这个布尔
   决定要不要再叠数据层的 `input_incomplete`。
7. **`module_not_implemented` 表已清空**：`pipeline._module_skips` 恒返回 `[]`，但**函数保留**
   ——M5 的 oracle 未落地前，它的"不可判"必须走这条通道。`tests/test_pipeline_skeleton.py`
   断言 M1–M3 都不再出现该前缀。
8. **fixture 清单与阈值册绑死**：`fixtures/manifest.json` 里存 `thresholds_sha256`
   （三份阈值文件的合并摘要）。**改任何阈值数据都必须同提交重跑
   `py -3.12 tools/gen_fixtures.py`**，否则 `--check` 红（`verify_gates.py` 的 F2 组
   就是这个判据）。产物 `fixtures/*.json` 不入仓（`.gitignore`），只有清单入仓。
9. **部分运行纪律**：`gen_fixtures.py --suite <name>` 只替换该套件条目，其余原样保留
   （`tests/test_fixtures.py::test_partial_run_keeps_other_suites` 用"篡改哨兵条目"证明，
   不只数条数）。
10. **首屏 `THRESHOLDS:` 行只列被引用的键**：`pipeline._cited_unverified` 从
    `finding.evidence.ref` 反推。**不要**改回"列全部未核键"——34 个键会把这一行变成噪音，
    等于没有提示。改 `evidence.ref` 的字符串格式要同步改那里的两个前缀常量。
11. **状态副本是 3 处**：`plan/00` 里程碑表、`plan/05` 状态表、`README.md` 状态表。
    翻 M4 ✅ 时**三处同提交改**。`plan/00` 台账里带 `⬜`/`🟡` 的行**不许在状态格里提
    已 ✅ 的里程碑号**（`LAYOUT.LEDGER` 会判红）；`plan/06` 缺口表的**缺口列**同理。
12. **本轮没跑过 CI**。任何"绿"都只能写**本地等价校验**，并注明"未接远端，CI 待首推验证"。
13. **提交门会在每次提交时报一条 medium「跨文件污点」**（`cli.py` 的
    `argv → args.input → load_spec → open()`）。这是按 `plan/00` D22 登记的预期判定，别去"消掉"它。
14. **`THRESHOLD_FILES` 的合并摘要进了报告**：`tools.vectors_sha256` 现在覆盖三份文件。
    加第四份数据文件时，`paths.VECTOR_FILES` 与 `thresholds.THRESHOLD_FILES` 都要登记
    （前者管"装好的包里能读到"，后者管"装载 + 摘要"），否则 `test_package_data.py` 或
    摘要一致性会红。

## 三、下一棒待办（M4）

按顺序做，每步都有可跑红的判据：

1. **退出码矩阵 12 格**（`data/README.md` §8.5）：
   `tests/test_exit_codes.py` 现在只覆盖骨架的一部分。补齐
   `--fail-on ∈ {none, warn, error}` × `worst ∈ {info, warn, error}` = **9 格**，
   再加跨三类 `3`（用法错误 / 输入不可解析 / 内嵌字典缺失）。**逐格一条测试**，
   不许用 parametrize 把 9 格压成 3 条。
   关键格显式断言：`none×error→0`、`warn×warn→1`、`error×error→2`、`warn×info→0`。
2. **JSON / MD 同源**：`test_two_formats_share_the_same_fingerprints` 已有（M0 骨架），
   但它是拿 `Report` 直接渲染的。M4 要补的是**端到端**：同一 spec 走 `check --json`
   与 `check --md`（或两次 render），`findings` 按 `fingerprint` 集合相等，且
   `summary`/`verdict` 一致。这判据挡住"某个渲染器少报了一条"。
3. **首屏三段字面**：`plan/03` §六的三行（`VERDICT:` / `FINDINGS:` / `TOP FIX:`）
   目前有字面断言（`test_markdown_headline_three_lines_are_literal`）。M4 要补：
   **顺序**断言（三行连续、位置固定）+ 三个 headline 常量与文档逐字一致。
4. **渲染层零判定**：`test_render_layer_has_no_judgement_imports` 已有 AST 判据
   （`forbidden = {gs1, symbols, print, oracle}`）。M4 再补一条：渲染模块**不得**调用
   `Report.worst_severity` 之外的重算（例如自己 `sorted`/`max` 严重级别），
   或直接断言 `render_*.py` 里不出现 `sev.rank` / `sev.worst` / `sev.verdict_for`。
5. **`--with-timestamp`**：目前只断言 `deterministic is False`。M4 要补：
   带时间戳时报告里**确实**有 `timestamp` 字段且格式固定（ISO-8601 UTC），
   且**不含**本机时区名/主机名（脱敏门会扫，但要有断言）。
6. **`out/` 落点**：`--json`/`--md` 写固定路径、目录不存在即 exit 3 且零副作用
   （已有 `test_report_paths_are_not_configurable`）。M4 补：写完的文件内容与
   stdout 完全一致（同一个 `render_*` 的返回值），且**不写入任何其它文件**
   （跑前跑后目录列表相等）。
7. **回写状态**：`plan/00`（台账 + 里程碑表）、`plan/05`（状态表 + DoD）、`README`
   （3 处同提交）；`plan/02`/`plan/03`/`plan/06` 与 `data/README.md` §9 同步。
8. **写 `plan/HANDOFF-M5.md`**（七节），然后 commit。

## 四、既定口径清单（K 编号 —— 动了会打挂测试）

| K | 约定 | 位置 |
| --- | --- | --- |
| K1 | 校验位算法唯一实现，`4 - W` 不是 `6 - W` | `data/README.md` §8.1；`gs1/checksum.py` |
| K2 | 向量只存"输入 + 期望"，期望由输入独立复算 | `data/vectors/*.json`；`tests/test_checksum.py` |
| K3 | `verdict` 只有 `pass/warn/fail` 三值；"不可判"走 `threshold_status`/`skipped`/降级 | `data/README.md` §8.8；`severity.py` |
| K4 | `Finding.fingerprint = sha256(id \x1f module \x1f target)[:16]`，**不含 severity** | `report/model.py` |
| K5 | `findings` 排序键 = `(module, ai_position, id)`，不是严重级别 | `report/model.py` |
| K6 | 退出码只在 `exitcodes.py` 定义；`3` 优先且不参与判定计数 | `data/README.md` §8.5 |
| K7 | 数值一律定点字符串（如 `"1.559"`），不从 JSON 读 float 再格式化 | `data/README.md` §8；`print/common.fixed` |
| K8 | `basis: engineering-heuristic` 项**没有** `status`，不参与未核降级（**M3 加了装载期断言**） | `data/README.md` §8.2 末条；`thresholds._validate_gen_spec` |
| K9 | 首屏三段字面固定（`VERDICT:` / `FINDINGS:` / `TOP FIX:`） | `report/render_md.py`；`tests/test_report_render.py` |
| K10 | 报告默认不读时钟；`--with-timestamp` 才标 `deterministic: false` | `pipeline.py`；`gs1/vectors.py` |
| K11 | 运行期零第三方依赖、零网络；`tests/test_no_network.py` AST 守 | `tests/test_no_network.py` |
| K12 | `requires-python >= 3.8`：3.10 的 `match`、3.9 的 `list[int]` 注解一律禁 | `tools/check_python_floor.py` |
| K13 | 元素串的 `ai_position` = 元素串内**序号**（0 起）；M1 `target = ai:<ai>:<scope>`，M2 `target = symbol:<symbol>:<scope>`，**M3 `target = quiet_zone.<side>` / `magnification` / `raster` / `bar_height` / `color.<probe>`** | `gs1/validators.py`；`symbols/feasibility.py`；`print/*.py` |
| K14 | 数据层不可判的三条出口：`reference_engine_absent` / `gcp_lookup_unavailable` / `module_not_implemented:<k>` | `pipeline.py`；`plan/00` D21 |
| K15 | M2 规则全部数据驱动 + 三态；`tie_break` 只实现 `longest-first` | `symbol_profiles.json`；`symbols/profiles.py` |
| K16 | `encoding_plan` 只在可编码时出现；`checksum` 的 GS1 值由 `gs1/checksum.py` 复核 | `symbols/feasibility.py`；`report/model.py` |
| **K17** | **零静区是结构档**：只读 `required`，`threshold_status` 恒 `not-applicable`，`severity` 恒 `error` | `print/quiet_zone.py`；`data/README.md` §8.2 |
| **K18** | **降级规则单点**：只有 `print/common.py` 的两个构造函数能做降级 / 产 `not-applicable` | `print/common.py`；`plan/03` §五 |
| **K19** | **`symbol` 不属于"请求了印刷层"**：`PRINT_INPUT_FIELDS` 不含它 | `input.py`；`print/audit.has_print_input` |
| **K20** | **fixture 清单与阈值册同摘要**：改阈值必须同提交重生成 `fixtures/manifest.json` | `tools/gen_fixtures.py`；`fixtures/manifest.json` |

## 五、本机环境坑（实测过的）

- **`python` / `python3` 是 Windows Store 占位符，执行即 exit 49**。一律 `py -3.12`
  （或 `py -3.8`）；输出中文加 `-X utf8`。
- **`py -3.12 -m bpreflight …` 需要 `PYTHONPATH=src`**（或先 `pip install -e .`）：
  `pyproject.toml` 的 `pythonpath` 只对 pytest 生效。
- `py -3.8` = 3.8.8，`py -3.12` = 3.12.10。本棒实测 `py -3.12 -m pytest -q` = **253 passed**；
  **`py -3.8` 通道本棒未跑**（M4 收尾前必须补跑，`requires-python` 的下限要有实跑）。
- Git Bash 下 heredoc 与 `cd` 复合命令容易被环境包装截断——**写临时脚本文件再执行**比
  `python - <<EOF` 稳；临时文件放 `.tmp/`（已在 `.gitignore` 里）。
- **`grep -rc` / `ugrep -E` 在 Git Bash 下对复杂正则不稳**。要判"某模式出现几次"就写进测试用 Python 数。
- **安全钩子会拦"用变量根路径拼路径再写文件"的写法**（静态判"路径穿越"）。写测试时
  优先**纯函数 + `monkeypatch`**（`tests/test_fixtures.py` 就是这样：把 `_write_bytes`
  换成记录器，一个字节都不落盘），而不是 `copytree` 到临时目录再改文件。
- `pytest` 通过 `pyproject.toml` 的 `pythonpath = ["src"]` 直接跑源码树，**不需要先安装**。
  `tools/gen_fixtures.py` 自己 `sys.path.insert(0, "src")`，所以未安装也能跑。
- 快速看一条印刷判定的全部结论：
  `PYTHONPATH=src py -3.12 -X utf8 -m bpreflight check --input examples/spec-ean13.json`
  （`examples/` 现在有三份：健康 / 红条+红光 / 零静区）。

## 六、DoD 逐项 checklist（M4 完成时须全部打勾）

- [ ] 退出码 9 格逐格一条测试 + 三类 `3`
- [ ] 关键格显式断言：`none×error→0`、`warn×warn→1`、`error×error→2`、`warn×info→0`
- [ ] 端到端两格式 `findings` 按 fingerprint 集合相等，`verdict`/`summary` 一致
- [ ] 首屏三段：字面 + 顺序 + 常量与 `plan/03` §六逐字一致
- [ ] 渲染层零判定：不 import 判定模块，也不重算严重级别
- [ ] `--with-timestamp` 有 `timestamp` 字段、格式固定、无主机名/时区名
- [ ] `out/` 落点：内容与 stdout 一致，且不写任何其它文件
- [ ] 三处状态副本同提交翻 ✅
- [ ] `plan/HANDOFF-M5.md` 七节齐
- [ ] 六道门 + `gen_fixtures.py --check` + `verify_gates.py` 全绿；`pytest` **3.8 / 3.12 双绿**

## 七、关键命令速查

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门
py -3.12 tools/check_thresholds.py        # 阈值零硬编码门
py -3.12 tools/check_python_floor.py      # Python 下限门
py -3.12 tools/check_ci_workflow.py       # CI 工作流门
py -3.12 tools/gen_fixtures.py --check    # fixture 位级自检（第七道常规检查）
py -3.12 tools/verify_gates.py            # 门自检（32 组变异）
py -3.12 -m pytest -q                     # 全量测试（253 passed）
py -3.8  -m pytest -q                     # 3.8 通道（语法回归；本棒未跑，M4 必补）
PYTHONPATH=src py -3.12 -X utf8 -m bpreflight check --input examples/spec-ean13.json
grep -rc "def gs1_check_digit" src/       # 必须 == 1
```

> 印刷阈值三份数据：`quiet_zone.json`（静区 + 结构事实 `required`）/ `gen_spec.json`
> （名义 X / 放大率 / 条高 + 工程判据）/ `color_cases.json`（照明建模 + 颜色用例）。
> 口径定义只在 `data/README.md` §8；`plan/03` §五记的是实现要点与两处**文档修正**
> （`print/thresholds.py` 不新建、降级单点在 `print/common.py`）。
