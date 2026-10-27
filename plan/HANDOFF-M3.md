# HANDOFF-M3 · 第 3 棒交接单（印刷可读性）

> 上一棒：**M2 符号合法性**（✅ 2026-10-27）
> 本棒目标：**M3 印刷可读性**——五项检查（静区 / 放大率 / DPI 混叠 / 条高 / 颜色）+
> `fix` 必填 + 阈值三态（未核降级、`--strict-thresholds` 恢复）+ `gen_fixtures.py`。
> 读法：**先跑布局门**（`AGENTS.md` 里的命令），绿了再读本文件。

## 一、当前进度与证据

M2 已完成并验证（**本地等价校验，未接远端，CI 待首推验证**）：

| 交付 | 证据（命令 + 结果） |
| --- | --- |
| 符号 profile 表 | `src/bpreflight/data/vectors/symbol_profiles.json`（八符号：`code128` / `gs1-128` / `ean13` / `ean8` / `upca` / `datamatrix` / `qr` / `code39`；每条规则带 `source` / `status` / `verified_at`，**全部 `unverified`**） |
| 规则装载单点 | `src/bpreflight/symbols/profiles.py`：`source` 必须是 `sources` 表里的键；`verified` 必须有日期、`unverified` 必须为 null；`tie_break` 不是 `longest-first` 直接 `ProfileError`（fail-closed） |
| 三段判定 | `src/bpreflight/symbols/feasibility.py`：字符集 ⊆ / 长度 ∈ / 模式可覆盖；判定模块**不 `open()`**（`tests/test_symbols.py` 走 AST 断言） |
| `encoding_plan` | `{symbol, mode, segments[], total_modules, checksum, tie_break, profile_version}`；**不可编码时不输出半个计划**（原因进 findings） |
| 跨符号等价性 3 组 | `tests/test_symbols.py`：`012345678905`→`upca` PASS / `ean13` 长度不符；`0012345678905`→`ean13` PASS / `upca` 长度不符；`00012345678905`→三只零售符号都不可（长度），`gs1-128` 可承载 |
| `4006381333931` | `ean13` PASS、`upca` 不可；断言原因只含长度/结构，**不含 "prefix"/"前缀"** |
| GS1 FNC1 | `(01)…(10)…`：`gs1-128` PASS；`code128` → `gs1_data_missing_fnc1`（`fix.to = "gs1-128"`） |
| `tie_break` 唯一 | 双跑 plan 相等；`segments` 文本顺序拼接 == 被编码字符流；`tie_break: "longest-first"` 原样落字段 |
| 未核降级 | 未核规则派生的 error 默认 `warn`、`threshold_status: "unverified"`；`--strict-thresholds` 恢复 `error`（`tests/test_symbols.py` 两态对照） |
| 校验位不复制 | `symbols/` 无 check-digit 函数（AST）；`encoding_plan.checksum` 的 GS1 值由 `gs1/checksum.py` 复核 |
| pipeline 收窄 | `IMPLEMENTED_MODULES = ("M1", "M2")`；`module_not_implemented:M2` 消失，M3 仍在；`symbol_not_specified` / `symbol_data_unparsed` / `gs1_2d_fnc1_not_modelled` 三条不判通道 |
| 报告 | `Report.encoding_plan`（可选键）+ MD `## Encoding plan` 段；`tools` 头带 `symbol_profiles_version` / `symbol_profiles_sha256` |
| 全量测试 | `py -3.12 -m pytest -q` → **161 passed**；`py -3.8 -m pytest -q` → **161 passed** |
| 打包自足性 | `py -3.12 -m build --wheel` → wheel 内 `bpreflight/data/vectors/` 五个 JSON 齐（含 `symbol_profiles.json`） |
| 六道门 + 变异自检 | 布局/脱敏/阈值/下限/CI 工作流全绿；`tools/verify_gates.py` → **28 组变异：符合预期 28 / 不符合 0** |

**M2 的 DoD 在 `plan/05` §三（全部打勾）**。

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **数据读取点现在是四处**（`plan/HANDOFF-M1` §二.3 + 本棒新增一处）：
   - `bpreflight/thresholds.py` —— 印刷阈值（`quiet_zone.json` / `gen_spec.json`）；
   - `bpreflight/gs1/dictionary.py` —— 字典正文 + `dict_manifest.json`；
   - `bpreflight/gs1/vectors.py` —— `gs1_vectors.json`；
   - **`bpreflight/symbols/profiles.py` —— `symbol_profiles.json`（本棒新增）**。
   **判定模块一处都不许有 `open()`**：M3 的五个检查模块必须接收 `ThresholdBook`
   （`pipeline` 已装载），不能自己读阈值文件。`tests/test_symbols.py` 已为 M2 立了
   AST 判据；M3 请照抄一条同样的。
2. **`plan/03` §五 写的 `print/thresholds.py` 与现有 `bpreflight/thresholds.py` 是同一职责。**
   现有模块已经装载 `quiet_zone.json` / `gen_spec.json` 并做三态校验——**M3 复用它，
   不要新建第二个装载器**（否则"阈值零硬编码门"的单点性质就断了）。若确需改文档，
   改 `plan/03` 的措辞，不改结构。
3. **未核降级已经是可复用的口径**：M2 的 `feasibility._make_finding` 演示了
   "`status != verified` ⇒ error 降 `warn`；`--strict-thresholds` 恢复"。M3 的
   `gen-spec` 阈值走同一口径；**`engineering-heuristic` 项（DPI 每模块点数、颜色两项）
   没有 `status`、永不降级**（`data/README.md` §8.2 末条）。别把两类混在一起。
4. **`Report.encoding_plan` 是可选键**：只在 M2 可编码时出现；`to_dict()` 不带它时不写键。
   M3 若要加报告字段（例如 `scanability`），沿用同一个"可选段"写法，别改已有键的语义。
5. **`module_not_implemented:M3` 收窄要改三处**（与 M2 同款）：
   `pipeline.IMPLEMENTED_MODULES`（加 `"M3"`）、`pipeline._module_skips`（删掉 M3 那一支）、
   `tests/test_pipeline_skeleton.py::test_unimplemented_modules_are_announced_not_silent`
   （断言 M2/M3 都不再出现 `module_not_implemented`）。
6. **M3 的"不可判"仍走三条既有出口**（`plan/00` K14 / D21）：`reference_engine_absent` /
   `gcp_lookup_unavailable` / 模块未实现；M3 新增的缺参走 `input_incomplete:<fields>`
   （`input.missing_fields` 已实现 `PRINT_FIELDS`）。**不要用 `pass` 表示不知道。**
7. **`fix` 构造即校验**：`report/model.py` 的 `Finding.__init__` 拒绝 warn/error 无 `fix`。
   M3 的每条 error/warn 都要给 `to` 或 `min_delta` + `unit`（决策 D9）。
8. **`tools/gen_fixtures.py` 已在布局门的 `PENDING_TOOLS`（M3）**：文件一落盘，
   布局门的 deferred 分支自动消失；**M3 翻 ✅ 时该文件必须存在**，否则报 stale。
9. **阈值门仍要求 `REGISTERED` 为空表**：M3 的所有数字（1.5 / 2.0 / 80 / 200 / 4.5 / 3.0 /
   0.2 / 1.2 …）必须从 `data/vectors/*.json` 读。写 `value[0:2]` 这类切片宽度也会被判红
   （M1 踩过），用常量推导。
10. **状态副本是 3 处**：`plan/00` 里程碑表、`plan/05` 状态表、`README.md` 状态表。
    翻 M3 ✅ 时**三处同提交改**，否则布局门 `LAYOUT.STATUS` 红。`plan/00` 台账里带 `⬜`
    的行**不许在状态格里提已 ✅ 的里程碑号**（`LAYOUT.LEDGER` 会判红）；`plan/06` 缺口表的
    **缺口列**同理（`LAYOUT.GAPS`）。
11. **本轮没跑过 CI**。任何"绿"都只能写**本地等价校验**，并注明"未接远端，CI 待首推验证"。
12. **提交门会在每次提交时报一条 medium「跨文件污点」**（`cli.py` 的 `argv → args.input →
    load_spec → open()`）。这是按 `plan/00` D22 登记的预期判定，别去"消掉"它。
13. **M2 的 profile 表全部 `unverified`**：如果 M3 要复用符号参数（例如条高模块比），
    也按数据读+三态标注处理，别把 M2 的占位值当规范。

## 三、下一棒待办（M3）

按顺序做，每步都有可跑红的判据：

1. **`src/bpreflight/data/vectors/color_cases.json`**：条/空颜色用例（红条+红光、红条+白光、
   黑条+白光、金属/荧光等未建模面），每条带 `source` / `status` / `verified_at`。
   `gen_spec.json` 里已有的 `contrast_ratio` / `wavelength_reflectance_delta_min` 继续用。
2. **`src/bpreflight/print/`**：五个检查模块（`quiet_zone.py` / `magnification.py` /
   `raster.py` / `bar_height.py` / `color.py`）。全部接收 `ThresholdBook`，不读文件。
   - `quiet_zone_absent`（任一侧 == 0）**恒 error，与阈值状态无关**——这是 M3 第一验收点；
   - 放大率边界 `0.2640/0.6600` 不报、`0.2639/0.6601` 报；
   - DPI 边界 `1.4999/1.5000/1.9999/2.0000` 逐条；
   - 颜色两项**不合并**（`wavelength_reflectance_collapse` vs `insufficient_contrast` /
     `low_contrast`），红条+白光走亮度项；
   - 未核 `gen-spec` 项降 `warn`，`--strict-thresholds` 恢复 `error`；
     `engineering-heuristic` 项**不参与降级**（`threshold_status: "not-applicable"`）。
3. **缺参拒判**：缺 `x_dimension_mm` / `target_dpi` / `quiet_zone_mm` 时**只产**
   `input_incomplete`，**不产**任何 `quiet_zone_*` / `magnification_*` / `raster_*` 结论
   （测试断言"这些 id 一个都不出现"）。
4. **`tools/gen_fixtures.py` + `fixtures/manifest.json`**：确定性、无网络、无随机、不读时钟；
   产物（`fixtures/*.json`）不入仓，清单入仓；`--check` 位级比对；部分运行不得改写全集清单。
5. **接进 pipeline**：`IMPLEMENTED_MODULES` 加 `"M3"`；删 `_module_skips` 的 M3 支；
   `_tools_info` 可加阈值册身份（`vectors_sha256` 已在）；M3 findings 进报告。
6. **测试**：`tests/test_print_audit.py`（五项 + 边界）、`tests/test_color.py`（两项不合并）、
   `tests/test_fix_contract.py`（每个 warn/error 有 `to` 或 `min_delta`）。
7. **回写状态**：`plan/00` 台账 + 里程碑表、`plan/05` 状态表与 DoD、`README` 状态表（3 处同提交）；
   `plan/02`/`plan/03`/`plan/04`/`plan/06` 与 `data/README.md` §8 同步。
8. **写 `plan/HANDOFF-M4.md`**（七节），然后 commit。

## 四、既定口径清单（K 编号 —— 动了会打挂测试）

| K | 约定 | 位置 |
| --- | --- | --- |
| K1 | 校验位算法唯一实现，`4 - W` 不是 `6 - W` | `data/README.md` §8.1；`gs1/checksum.py` |
| K2 | 向量只存"输入 + 期望"，期望由输入独立复算 | `data/vectors/*.json`；`tests/test_checksum.py` |
| K3 | `verdict` 只有 `pass/warn/fail` 三值；"不可判"走 `threshold_status`/`skipped`/降级 | `data/README.md` §8.8；`severity.py` |
| K4 | `Finding.fingerprint = sha256(id \x1f module \x1f target)[:16]`，**不含 severity** | `report/model.py` |
| K5 | `findings` 排序键 = `(module, ai_position, id)`，不是严重级别 | `report/model.py` |
| K6 | 退出码只在 `exitcodes.py` 定义；`3` 优先且不参与判定计数 | `data/README.md` §8.5 |
| K7 | 数值一律定点字符串（如 `"1.559"`），不从 JSON 读 float 再格式化 | `data/README.md` §8；`plan/03` §五 |
| K8 | `basis: engineering-heuristic` 项**没有** `status`，不参与未核降级 | `data/README.md` §8.2 末条 |
| K9 | 首屏三段字面固定（`VERDICT:` / `FINDINGS:` / `TOP FIX:`） | `report/render_md.py`；`tests/test_report_render.py` |
| K10 | 报告默认不读时钟；`--with-timestamp` 才标 `deterministic: false` | `pipeline.py`；`gs1/vectors.py` |
| K11 | 运行期零第三方依赖、零网络；`tests/test_no_network.py` AST 守 | `tests/test_no_network.py` |
| K12 | `requires-python >= 3.8`：3.10 的 `match`、3.9 的 `list[int]` 注解一律禁 | `tools/check_python_floor.py` |
| K13 | 元素串的 `ai_position` = 元素串内**序号**（0 起）；M1 `target = ai:<ai>:<scope>`，M2 `target = symbol:<symbol>:<scope>` | `gs1/validators.py`；`symbols/feasibility.py` |
| K14 | 数据层不可判的三条出口：`reference_engine_absent` / `gcp_lookup_unavailable` / `module_not_implemented:<k>` | `pipeline.py`；`plan/00` D21 |
| K15 | M2 规则全部数据驱动 + 三态；`tie_break` 只实现 `longest-first`（数据写别的直接报错） | `symbol_profiles.json`；`symbols/profiles.py` |
| K16 | `encoding_plan` 只在可编码时出现；`checksum` 的 GS1 值由 `gs1/checksum.py` 复核，M2 不复制 | `symbols/feasibility.py`；`report/model.py` |

## 五、本机环境坑（实测过的）

- **`python` / `python3` 是 Windows Store 占位符，执行即 exit 49**。一律 `py -3.12`
  （或 `py -3.8`）；输出中文加 `-X utf8`。
- **`py -3.12 -m bpreflight …` 需要 `PYTHONPATH=src`**（或先 `pip install -e .`）：
  `pyproject.toml` 的 `pythonpath` 只对 pytest 生效。
- `py -3.8` = 3.8.8，`py -3.12` = 3.12.10，两者都装了 pytest；本棒实测
  `pytest -q` 双解释器各 **161 passed**。
- Git Bash 下 heredoc 与 `cd` 复合命令容易被环境包装截断——**写临时脚本文件再执行**比
  `python - <<EOF` 稳；临时文件放 `.tmp/`（已在 `.gitignore` 里）。
- **`grep -rc` / `ugrep -E` 在 Git Bash 下对复杂正则不稳**。要判"某模式出现几次"就写进测试用 Python 数。
- `pytest` 通过 `pyproject.toml` 的 `pythonpath = ["src"]` 直接跑源码树，**不需要先安装**；
  "安装后仍能读到数据"由 `tests/test_package_data.py` + CI 的 `pip install` 覆盖。
  本棒新增的 `symbol_profiles.json` 已在 `paths.VECTOR_FILES` 与 `package-data` 的
  `data/vectors/*.json` 覆盖范围内。
- 快速看某个符号的判定：
  `PYTHONPATH=src py -3.12 -X utf8 -c "from bpreflight.symbols import profiles, feasibility; b=profiles.load(); r=feasibility.assess(b,'ean13',identifier='4006381333931'); print([(f.severity,f.id) for f in r.findings], r.plan)"`

## 六、DoD 逐项 checklist（M3 完成时须全部打勾）

- [ ] `quiet_zone_absent`（任一侧 == 0）恒 `error`，**与阈值状态无关**
- [ ] `quiet_zone_mm=0.6, X=0.330` → `qz=1.818` < 占位 `modules_min` → `quiet_zone_insufficient` + `fix.to`
- [ ] 放大率边界四值：`0.2640`/`0.6600` 不报；`0.2639`/`0.6601` 报
- [ ] DPI：`120→1.559 warn` / `100→1.299 error` / `203→2.637 ok`
- [ ] 颜色：红条+红光 → `wavelength_reflectance_collapse`；红条+白光 → `contrast_ratio=5.88` 走亮度项；两项**不合并**
- [ ] 未核 `gen-spec` 阈值在 `unverified` ↔ `verified` 间切换时 `severity` 对应 `warn` ↔ `error`；
      `--strict-thresholds` 恢复 `error` 且首屏标注
- [ ] DPI 与颜色两项**不参与降级**（`threshold_status: "not-applicable"`）
- [ ] 缺参即拒判：缺 `x_dimension_mm` → 只有 `input_incomplete`，没有任何 `quiet_zone_*` 结论
- [ ] `tools/gen_fixtures.py --check` 位级 0 差异；`fixtures/manifest.json` 入仓
- [ ] `tools/check_thresholds.py` 0 命中；`tests/test_fix_contract.py` 全 PASS
- [ ] `module_not_implemented:M3` 已收窄（pipeline + 测试同步改）
- [ ] 三处状态副本同提交翻 ✅
- [ ] `plan/HANDOFF-M4.md` 七节齐
- [ ] 六道门 + `verify_gates.py` 仍全绿；`pytest` 3.8 / 3.12 双绿

## 七、关键命令速查

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门
py -3.12 tools/check_thresholds.py        # 阈值零硬编码门
py -3.12 tools/check_python_floor.py      # Python 下限门
py -3.12 tools/check_ci_workflow.py       # CI 工作流门
py -3.12 tools/verify_gates.py            # 门自检（28 组变异）
py -3.12 -m pytest -q                     # 全量测试（161 passed）
py -3.8  -m pytest -q                     # 3.8 通道（语法回归）
PYTHONPATH=src py -3.12 -X utf8 -m bpreflight check --input examples/spec-ean13.json
grep -rc "def gs1_check_digit" src/       # 必须 == 1
```

> 符号规则与用例在 `src/bpreflight/data/vectors/symbol_profiles.json`（带 `source` 键）；
> 跨符号等价性用例与失败面在 `tests/test_symbols.py`；
> 报告的可选 `encoding_plan` 形状见 `data/README.md` §8.7 与 §8.10。
