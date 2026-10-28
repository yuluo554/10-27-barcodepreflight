# HANDOFF-M5 · 第 5 棒交接单（仿真回读，可选）

> 上一棒：**M4 报告与门禁**（✅ 2026-10-28）
> 本棒目标：**M5 栅格化仿真回读（可选）**——最小采样器（纯函数）+ zxing-cpp oracle 探测 +
> `agreement` 三态（`consistent` / `m3_stricter` / `m3_laxer`）。**M5 只做一致性对照，不改 M3 判定。**
> 读法：**先跑布局门**（`AGENTS.md` 里的命令），绿了再读本文件。

## 一、当前进度与证据

M4 已完成并验证（**本地等价校验，未接远端，CI 待首推验证**）：

| 交付 | 证据（命令 + 结果） |
| --- | --- |
| 退出码 9 格逐格 | `tests/test_exit_codes.py`：`test_none_info_is_zero` … `test_error_error_is_two` **9 条独立函数**（不 parametrize 压成 3 条） |
| 关键格显式 | `test_key_cells_are_pinned_explicitly`：`none×error→0` / `warn×warn→1` / `error×error→2` / `warn×info→0` |
| 三类 `3` | `test_usage_error_wins_over_any_gate`（纯函数）/ `test_unparseable_input_returns_three`（非法 JSON）/ `test_missing_dictionary_returns_three`（`monkeypatch` 让字典抛 `DictionaryError`） |
| 矩阵经 CLI 端到端 | `test_cli_info_spec_cells` / `test_cli_warn_spec_cells` / `test_cli_error_spec_cells`：9 格覆盖到真实 spec |
| JSON/MD 端到端同源 | `test_report_render.py::test_end_to_end_json_and_md_share_fingerprints`：fingerprint 集合相等 + `verdict`/`summary` 一致（同一 spec 经 `pipeline.run`） |
| fingerprint 跨 run 稳定 | `test_fingerprints_are_stable_across_two_runs`：两次独立 run 相等，不同输入必须不同 |
| 首屏三段顺序锁死 | `test_headline_three_lines_are_contiguous_and_in_order`：前三行连续且位置固定 |
| 常量与文档逐字一致 | `test_headline_constants_match_plan_03_verbatim`：从 `plan/03` §六 读回 `VERDICT:`/`FINDINGS:`/`TOP FIX:` 与计数行契约 |
| 渲染层零判定（import 面） | `test_render_layer_has_no_judgement_imports`（AST，原有） |
| 渲染层零判定（重算面） | `test_render_layer_does_not_recompute_severity`（AST：不得 import `bpreflight.severity`、不得 `.rank`/`.worst`/`.verdict_for`）+ `test_severity_recompute_detector_has_bite`（阳性对照，抓 3 种真实写法） |
| `--with-timestamp` | `test_with_timestamp_has_iso_utc_and_no_host_or_zone` + `test_timestamp_absent_by_default` + `test_timestamp_uses_injected_clock`；格式固定 `YYYY-MM-DDTHH:MM:SSZ` |
| `out/` 落点 | `test_cli_contract.py`：`test_out_json_file_content_equals_stdout_of_same_format`（字节等于 stdout）/ `test_out_writes_nothing_else`（目录列表前后只多那两个文件） |
| 全量测试 | `py -3.12 -m pytest -q` → **269 passed**；`py -3.8 -m pytest -q` → **269 passed**（同数） |
| 六道门 + 门自检 | 布局/脱敏/阈值/下限/CI 工作流全绿；`tools/gen_fixtures.py --check` → 31 件位级一致；`tools/verify_gates.py` → **32 组变异：符合预期 32 / 不符合 0** |

**M4 的 DoD 在 `plan/05` §三（全部打勾）**。

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **`timestamp` 是 `Report` 的字段，不是渲染期拼的**：`pipeline.utc_timestamp(now)` 只在
   `with_timestamp=True` 时调用；`Report.timestamp` 为 `None` 时 JSON/MD 都**不出现**该字段。
   格式固定 `YYYY-MM-DDTHH:MM:SSZ`（ISO-8601 / UTC，句尾字面 `Z`），**不含**本地时区名/主机名。
   `now` 参数只为测试钉时钟，正常调用不传。
2. **渲染层零判定现在是两条判据**：① 不得 import `gs1`/`symbols`/`print`/`oracle`（AST）；
   ② 不得重算严重级别（AST：`bpreflight.severity` 导入面 + `.rank`/`.worst`/`.verdict_for`
   属性面），且**判据自带阳性对照**。**M5 若新增 `oracle` 渲染段，必须读 `Report` 派生字段，
   不许在渲染期碰 `severity`**——`report/` 下的 `oracle` import 面现已被判据封锁（见 `forbidden` 集）。
3. **`out/` 落点判据是"字节等于 stdout + 目录列表前后相等"**，不是"文件存在"。M5 的
   `oracle` 子命令要写 `out/oracle-report.{json,md}`：**主报告与 oracle 报告必须分清**，
   `test_out_writes_nothing_else` 只针对 `check --json --md`；新增 oracle 落点时**另写一条**
   同族判据，不要改那条（否则会掩盖主报告面的回归）。
4. **退出码只在 `exitcodes.py` 定义**，`3` 优先且不参与判定计数（K6）。M5 的 oracle 缺失
   是 `skipped: oracle_absent`（`data/README.md` §8.9 G6），**不是** `3`——缺引擎不是用法错误，
   是"这一层没跑"。**M5 的 `agreement` 不参与 `verdict`**（§8.8：`verdict` 只由 findings 派生）。
5. **`module_not_implemented` 表已清空**：`pipeline._module_skips` 恒返回 `[]`，但函数保留。
   **M5 oracle 未落地前，"oracle 不可判"必须走 `skipped`，不许让报告沉默变绿**；M5 落地后
   若 oracle 被请求而引擎缺失，仍走 `skipped: oracle_absent`（不是 `module_not_implemented`）。
6. **`skipped` 是"不可判"的合法通道，不是 verdict 的第四个值**（K3）。M5 的三态
   `agreement ∈ {consistent, m3_stricter, m3_laxer}` 是**独立字段**，不是新 verdict。
7. **M5 不改 M3 判定**（决策 D10）：`agreement` 是对照，不是第二套判定。`m3_stricter`（M3
   判危险但 oracle 能解）记入 `known-disagreements`；**`m3_laxer`（M3 判安全但 oracle 解不出）
   必须当 bug 修 M3 判定**，不许把它藏进"已知差异"。
8. **数据读取点仍是四处**：`bpreflight/thresholds.py`（`quiet_zone.json` / `gen_spec.json` /
   `color_cases.json`）、`gs1/dictionary.py`、`gs1/vectors.py`、`symbols/profiles.py`。
   **判定模块一处都不许有 `open()`**（`tests/test_print_audit.py` 对 `print/*.py` 做 AST 扫描）；
   M5 的采样器**必须纯函数**（输入参数 + 尺寸 → 位图），不读文件、无随机、无抗锯齿。
9. **零第三方依赖 + 零网络是红线**（K11）：`src/bpreflight/` 只准 import 标准库。
   **zxing-cpp 只能通过外部命令探测**（`shutil.which` + 子进程），**不得 import 它**——
   `tests/test_no_network.py::test_third_party_imports_are_absent` 会红；`tests/test_no_network.py`
   另扫网络模块。M5 的 `oracle/zxing.py` 走 `subprocess`，**探测失败即 `skipped: oracle_absent`**。
10. **`test_no_network.py` 扫 `src/bpreflight/**` 全部 `.py`**：M5 新增 `oracle/` 目录会被自动纳入，
    不需要改那份测试——但 `sampler.py` 里**不许**出现 `socket` 等名字（连 `FORBIDDEN_CALLS` 都扫）。
11. **`pyproject.toml` 的 `[project.optional-dependencies]`** 若 M5 要写 zxing 绑定，**必须留成
    extra 且运行期不 import**；否则零依赖红线破。M5 文档里这条要写死。
12. **状态副本是 3 处**：`plan/00` 里程碑表、`plan/05` 状态表、`README.md` 状态表。
    翻 M5 ✅ 时**三处同提交改**。`plan/00` 台账里带 `⬜`/`🟡` 的行**不许在状态格里提已 ✅ 的
    里程碑号**（`LAYOUT.LEDGER` 会判红）；`plan/06` 缺口表的**缺口列**同理。
13. **fixture 清单与阈值册绑死**（K20）：`fixtures/manifest.json` 存 `thresholds_sha256`。
    **改任何阈值数据都必须同提交重跑 `py -3.12 tools/gen_fixtures.py`**。M5 若加 oracle fixture，
    它**不读阈值册**——不要把它塞进 `tools/gen_fixtures.py`（那份是纯判定面、无网络、无外部命令）。
14. **本轮没跑过 CI**。任何"绿"都只能写**本地等价校验**，并注明"未接远端，CI 待首推验证"。
15. **提交门会在每次提交时报一条 medium「跨文件污点」**（`cli.py` 的
    `argv → args.input → load_spec → open()`）。这是按 `plan/00` D22 登记的预期判定，别去"消掉"它。
16. **Python 3.8 通道本棒已补跑**：`py -3.8 -m pytest -q` = **269 passed**（与 3.12 同数）。
    M5 收尾**必须再双跑**（新代码同样受 `tools/check_python_floor.py` 约束：`match` / `X | Y`
    注解 / `list[int]` 注解一律禁止）。

## 三、下一棒待办（M5）

按顺序做，每步都有可跑红的判据：

1. **`src/bpreflight/oracle/sampler.py`（纯函数）**：`(plan, x_mm, dpi, bar_color, space_color)
   → 灰度位图 bytes`。1D 用像素行、2D 用位图矩阵；按固定 sRGB 相对亮度公式转灰度（系数见
   `data/README.md` §8.4，**从数据读**，不写裸字面量——`tools/check_thresholds.py` 会判红）。
   判据：同输入两次调用字节相等；不许 import `random` / 网络模块；不许有 `open()`。
2. **`src/bpreflight/oracle/zxing.py`（外部引擎探测）**：`shutil.which(...)` + `subprocess`。
   缺失 ⇒ 返回 `skipped: oracle_absent`，**不伪造结论**。判据：本机无引擎时路径必走 `skipped`；
   `tests/test_no_network.py` 仍 0 命中（`subprocess` 是标准库，不在禁止面）。
3. **`agreement` 三态**：`{m3_verdict, oracle_result, agreement}`，三值枚举 + 缺引擎时**不产出**
   `agreement`。判据：`m3_laxer` 有显式测试并**记为 bug 通道**；`m3_stricter` 入
   `known-disagreements`（独立字段，不动 `verdict`）。
4. **`oracle` 子命令落点**：写固定 `out/oracle-report.json` / `out/oracle-report.md`（D20：
   落点不含 argv 成分）。**主报告与 oracle 报告分清**：新增一条"只多那两个 oracle 文件"的
   目录判据，不改 `test_out_writes_nothing_else`。
5. **每模块 1 点样本**：oracle 解不出 + M3 判 `raster_alias_high_risk`（双断言一致）；健康样本
   oracle 解出 + M3 `pass`；红条 + 红光 oracle 解不出 + M3 `wavelength_reflectance_collapse`。
   **没有引擎时这三条要么跳过并显式登记**（`pytest.skip` 带原因 + 一份 `skipped: oracle_absent`
   的断言），要么用**可注入的假引擎**跑一致逻辑——**不许**把"没跑"写成"通过"。
6. **不 import 第三方**：`oracle/` 全部走标准库 + 子进程；`tests/test_no_network.py` 的
   `test_third_party_imports_are_absent` 覆盖到新目录（自动）。
7. **回写状态**：`plan/00`（台账 + 里程碑表）、`plan/05`（状态表 + DoD）、`README`
   （3 处同提交）；`plan/02`（新增 `oracle/` 落点行）、`plan/03` §七、`plan/06`（评分对标 +
   缺口 + 决策）、`data/README.md` §8.9 G6/§9 同步。
8. **写 `plan/HANDOFF-M6.md`**（七节，发布棒），然后 commit。

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
| K8 | `basis: engineering-heuristic` 项**没有** `status`，不参与未核降级 | `data/README.md` §8.2 末条；`thresholds._validate_gen_spec` |
| K9 | 首屏三段字面固定（`VERDICT:` / `FINDINGS:` / `TOP FIX:`）+ **顺序**（前三行连续） | `report/render_md.py`；`tests/test_report_render.py` |
| K10 | 报告默认不读时钟；`--with-timestamp` 才标 `deterministic: false` 并给 `timestamp` | `pipeline.run` / `pipeline.utc_timestamp`；`gs1/vectors.py` |
| K11 | 运行期零第三方依赖、零网络；`tests/test_no_network.py` AST 守 | `tests/test_no_network.py` |
| K12 | `requires-python >= 3.8`：3.10 的 `match`、3.9 的 `list[int]` 注解一律禁 | `tools/check_python_floor.py` |
| K13 | 元素串的 `ai_position` = 元素串内**序号**（0 起）；M1 `target = ai:<ai>:<scope>`，M2 `target = symbol:<symbol>:<scope>`，M3 `target = quiet_zone.<side>` / `magnification` / `raster` / `bar_height` / `color.<probe>` | `gs1/validators.py`；`symbols/feasibility.py`；`print/*.py` |
| K14 | 数据层不可判的三条出口：`reference_engine_absent` / `gcp_lookup_unavailable` / `module_not_implemented:<k>` | `pipeline.py`；`plan/00` D21 |
| K15 | M2 规则全部数据驱动 + 三态；`tie_break` 只实现 `longest-first` | `symbol_profiles.json`；`symbols/profiles.py` |
| K16 | `encoding_plan` 只在可编码时出现；`checksum` 的 GS1 值由 `gs1/checksum.py` 复核 | `symbols/feasibility.py`；`report/model.py` |
| K17 | 零静区是结构档：只读 `required`，`threshold_status` 恒 `not-applicable`，`severity` 恒 `error` | `print/quiet_zone.py`；`data/README.md` §8.2 |
| K18 | 降级规则单点：只有 `print/common.py` 的两个构造函数能做降级 / 产 `not-applicable` | `print/common.py`；`plan/03` §五 |
| K19 | `symbol` 不属于"请求了印刷层"：`PRINT_INPUT_FIELDS` 不含它 | `input.py`；`print/audit.has_print_input` |
| K20 | fixture 清单与阈值册同摘要：改阈值必须同提交重生成 `fixtures/manifest.json` | `tools/gen_fixtures.py`；`fixtures/manifest.json` |
| **K21** | **`timestamp` 是模型字段**：格式固定 `YYYY-MM-DDTHH:MM:SSZ`（UTC），无时区名/主机名；默认缺席 | `report/model.Report.timestamp`；`pipeline.utc_timestamp` |
| **K22** | **渲染层零判定是两条判据**：import 面 + 重算面（且带阳性对照）；渲染只读 `Report` 派生字段 | `report/render_*.py`；`tests/test_report_render.py` |
| **K23** | **退出码矩阵逐格一条测试**：9 格不许 parametrize 压成 3 条；三类 `3` 从真实入口触发 | `tests/test_exit_codes.py`；`data/README.md` §8.5 |
| **K24** | **`out/` 落点判据 = "字节等于 stdout" + "目录列表前后相等"**；oracle 落点单列一条 | `cli._write_fixed`；`tests/test_cli_contract.py` |
| **K25** | **M5 的 `agreement` 不参与 `verdict`**；`m3_laxer` 是 bug 通道，`m3_stricter` 入 `known-disagreements` | `oracle/`；`plan/00` D10 |

## 五、本机环境坑（实测过的）

- **`python` / `python3` 是 Windows Store 占位符，执行即 exit 49**。一律 `py -3.12`
  （或 `py -3.8`）；输出中文加 `-X utf8`。
- **`py -3.12 -m bpreflight …` 需要 `PYTHONPATH=src`**（或先 `pip install -e .`）：
  `pyproject.toml` 的 `pythonpath` 只对 pytest 生效。
- `py -3.8` = 3.8.8，`py -3.12` = 3.12.10。本棒实测双通道均 **269 passed**；
  M5 收尾**必须双跑**。
- Git Bash 下 heredoc 与 `cd` 复合命令容易被环境包装截断——**写临时脚本文件再执行**比
  `python - <<EOF` 稳；临时文件放 `.tmp/`（已在 `.gitignore` 里）。
- **本机 Bash 工具拒绝"直接写源码/临时脚本"的写法**（安全钩子）：一律用 Write/Edit 提交文件，
  不要用 `cat > file <<EOF`。实测被拦过一次（写 `.tmp/probe.py`）。
- **`grep -rc` / `ugrep -E` 在 Git Bash 下对复杂正则不稳**。要判"某模式出现几次"就写进测试用 Python 数。
- **安全钩子会拦"用变量根路径拼路径再写文件"的写法**（静态判"路径穿越"）。写测试时
  优先**纯函数 + `monkeypatch`**，而不是 `copytree` 到临时目录再改文件。
- `pytest` 通过 `pyproject.toml` 的 `pythonpath = ["src"]` 直接跑源码树，**不需要先安装**。
  `tools/gen_fixtures.py` 自己 `sys.path.insert(0, "src")`，所以未安装也能跑。
- **M5 的 zxing-cpp 本机可用性未验**（`data/README.md` §9 第 7 项）。落到测试上时优先
  用**可注入的假引擎**跑一致逻辑，真引擎缺失时显式 `pytest.skip` + 一条
  `skipped: oracle_absent` 断言（不许把"没跑"写成"通过"）。

## 六、DoD 逐项 checklist（M5 完成时须全部打勾）

- [ ] 采样器是纯函数：同输入两次字节相等、无随机、无抗锯齿、无 `open()`
- [ ] zxing 探测缺失 ⇒ `skipped: oracle_absent`（不伪造结论）
- [ ] `agreement` 三态枚举 + 缺引擎时**不产出**该字段
- [ ] `m3_laxer` 记为 bug 通道并修复 M3；`m3_stricter` 入 `known-disagreements`
- [ ] 每模块 1 点样本：双断言一致（解不出 + `raster_alias_high_risk`）
- [ ] 健康样本一致；红条+红光一致
- [ ] `oracle` 落点固定 `out/oracle-report.{json,md}`，且有"只多那两个文件"的目录判据
- [ ] `tests/test_no_network.py` 0 命中（含新 `oracle/` 目录）；零第三方 import
- [ ] 三处状态副本同提交翻 ✅
- [ ] `plan/HANDOFF-M6.md` 七节齐
- [ ] 六道门 + `gen_fixtures.py --check` + `verify_gates.py` 全绿；`pytest` **3.8 / 3.12 双绿**

## 七、关键命令速查

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门
py -3.12 tools/check_thresholds.py        # 阈值零硬编码门（采样器的灰度系数也在扫描面内）
py -3.12 tools/check_python_floor.py      # Python 下限门
py -3.12 tools/check_ci_workflow.py       # CI 工作流门
py -3.12 tools/gen_fixtures.py --check    # fixture 位级自检（第七道常规检查）
py -3.12 tools/verify_gates.py            # 门自检（32 组变异）
py -3.12 -m pytest -q                     # 全量测试（269 passed）
py -3.8  -m pytest -q                     # 3.8 通道（269 passed）
PYTHONPATH=src py -3.12 -X utf8 -m bpreflight check --input examples/spec-ean13.json
PYTHONPATH=src py -3.12 -X utf8 -m bpreflight oracle --input examples/spec-ean13.json  # M5 落地后
grep -rc "def gs1_check_digit" src/       # 必须 == 1
```

> 报告层三件：`report/model.py`（唯一数据结构 + `fingerprint` + `timestamp`）/ `render_json.py` /
> `render_md.py`。首屏三段契约只在 `plan/03` §六 与 `data/README.md` §8.7 定义；
> 退出码只在 `data/README.md` §8.5；M5 的 `agreement` 口径只该新加在 §8.8 附近（不新开 verdict）。
