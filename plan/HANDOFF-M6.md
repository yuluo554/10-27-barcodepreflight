# HANDOFF-M6 · 第 6 棒交接单（发布棒）

> 上一棒：**M5 仿真回读**（✅ 2026-10-28）
> 本棒目标：**M6 发布**——仓库名/包名重名核对（D13）→ 干净环境验证（真下载 + 中立目录 + 新 venv +
> README 逐条真敲）→ 脱敏四步 + 产物扫描 → `git tag` + GitHub Release（附 `sdist` + `wheel` +
> `SHA256SUMS`）→ `plan/RELEASE-M6.md` 两栏 + §覆盖对账 → 首次 CI 首推后回填真实 run id。
> 读法：**先跑布局门**（`AGENTS.md` 里的命令），绿了再读本文件。

## 一、当前进度与证据

M5 已完成并验证（**本地等价校验，未接远端，CI 待首推验证**）：

| 交付 | 证据（命令 + 结果） |
| --- | --- |
| 采样器纯函数 | `tests/test_oracle.py::test_sampler_is_a_pure_function_of_its_arguments`（两次调用 `pixels`/`line`/`min_module_width` 相等）+ `test_sampler_has_no_randomness_no_antialiasing_and_no_file_access`（AST 无 `random`、无 `open()`、不 import `io/os/pathlib/json`；运行时 ≤ 2 个灰度级） |
| 灰度照通道取值 | `test_gray_level_follows_the_illumination_channel`：`#C8102E` 白光 = **33**、红光 = **200**；未知通道报 `SampleError` |
| 图案表自洽 | `test_layout_code_sets_are_self_consistent`（L 奇校验、`R = complement(L)`、`G = reverse(complement(L))`、G 偶校验）+ `test_layout_parity_rows_cover_every_leading_digit`（首位 0 全 L；1–9 恰好 3 个 G）+ `test_module_row_has_the_documented_structure`（95 模块 + 守卫 + 非法输入报错） |
| 位图往返（DoD 健康样本） | `test_healthy_sample_decodes_and_m3_passes`：M3 `pass` + 测试侧小解码器只读落盘 PNG 像素 → 读回 `9501101530003` |
| 每模块不足 1 点 | `test_under_one_dot_per_module_cannot_be_read_back`（DPI=70 ⇒ `dots_per_module = 0.909`、`min_module_width == 0`、解不出、M3 `raster_alias_high_risk`、`agreement: consistent`） |
| 红条 + 红光 | `test_red_ink_under_red_light_cannot_be_read_back`（解不出 + M3 `wavelength_reflectance_collapse` + `consistent`）；同一红条白光 → 解得出来 + M3 无 finding |
| 三态归宿 | `test_m3_stricter_goes_to_known_disagreements` / `test_not_decoded_with_a_clean_m3_lands_in_the_bug_channel`（`m3_laxer` 只进 `bugs`，`known_disagreements` 为空）/ `test_agreement_is_a_three_value_enum`（3×2 组合全覆盖） |
| 缺引擎不伪造 | `test_oracle_absent_is_declared_and_agreement_is_absent`（`skipped == ["oracle_absent"]`、`agreement` 键**缺席**）+ `test_engine_unusable_is_not_read_as_not_decoded`（`OSError` ⇒ `engine_unusable`，`bugs == []`） |
| 前提不全不猜 | `test_unsupported_symbol_is_skipped_with_a_reason`（`qr`）/ `test_missing_print_fields_are_skipped_with_a_reason` / `test_unmodelled_illumination_is_skipped_not_guessed`（`ir`）/ `test_engine_with_a_plan_that_has_no_segments_is_skipped` |
| 不进 verdict（K25） | `test_oracle_never_touches_the_main_verdict`（三种回读结果下主报告 `verdict`/`fingerprints` 不变，oracle 文档里没有 `verdict`/`fingerprints` 键） |
| 落点固定 | `tests/test_cli_contract.py::test_oracle_writes_nothing_else`（目录前后只多 `out/oracle-report.{json,md}`，且**不**写 `report.*`）+ `test_oracle_exit_code_comes_from_the_m3_report` |
| 零第三方 / 零网络 | `tests/test_no_network.py`（自动覆盖新目录）：**0 命中**；`oracle/` 只用 `shutil` / `subprocess` / `tempfile` / `zlib` / `struct` |
| Python 下限 | `tools/check_python_floor.py` 全绿（`oracle/` 与 `tests/test_oracle.py` 无 `match` / `X \| Y` / `list[int]` 注解） |
| 全量测试 | `py -3.12 -m pytest -q` → **299 passed**；`py -3.8 -m pytest -q` → **299 passed**（同数） |
| 六道门 + 门自检 | 布局/脱敏/阈值/下限/CI 工作流全绿；`tools/gen_fixtures.py --check` → 31 件位级一致；`tools/verify_gates.py` → **32 组变异：符合预期 32 / 不符合 0** |

**M5 的 DoD 在 `plan/05` §三（全部打勾）**。

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **`agreement` 是独立字段，不进 `verdict`（K25）**：三值枚举
   `{consistent, m3_stricter, m3_laxer}`，口径只在 `data/README.md` §8.8。`check` 的主报告
   **不因本机装没装解码引擎而改变一个字**；`oracle` 报告是**独立文档**
   （schema `bpreflight/oracle-report/1`，固定落 `out/oracle-report.{json,md}`）。
2. **缺引擎 ⇒ `agreement` 键缺席，不是 `null`**：缺席与"跑了但没结论"是两件事
   （`data/README.md` §8.9 G6 一族）。`skipped` 词表：`oracle_absent` /
   `engine_unusable:<detail>` / `sampler_unsupported:<symbol>` /
   `sampler_input_incomplete:<field,…>` / `sampler_unmodelled_colour:<…>` /
   `sampler_unencodable_data:<symbol>` —— 一律**不是** exit 3（缺引擎不是用法错误）。
3. **`engine_unusable` 与 `not-decoded` 必须分开**：把前者读成后者会凭空产出
   `m3_laxer`，那会逼人去"修"一个并不存在的 M3 bug。三态契约在
   `oracle/zxing.py`（`DECODED` / `NOT_DECODED` / `UNUSABLE`），判据是
   `test_decode_status_contract`。
4. **`m3_laxer` 是 bug 通道**：它只进 `bugs`，**不许**进 `known_disagreements`
   （`oracle/agreement.py` 的 `_NOTE_LAXER` 与 `test_m3_laxer_is_a_bug_channel_not_a_known_disagreement`
   一起钉住）。
5. **采样器是纯函数**：`oracle/sampler.py` 不 `open()`、不 import `io/os/json/random`、
   只有硬边（≤ 2 个灰度级）；图案表由 `oracle/layout.py` 装载后**以参数传入**
   （与 `print/` 接收 `ThresholdBook` 同款）。**改采样器必须保持这条**。
6. **图案表全部 `unverified`**（`data/vectors/sampler_patterns.json`）：只存 `L` 组 10 个 7 位码，
   `R = complement(L)`、`G = reverse(complement(L))` 由装载期派生，`parity_first_digit` 逐首位；
   **只建模 EAN-13**，别的符号走 `skipped: sampler_unsupported:<symbol>`。
   改它等于改数据基座：结构不变量由 `tests/test_oracle.py` 常驻断言（第 95 模块总数、
   守卫、奇偶校验）。**它不是阈值册的一部分**（`thresholds.THRESHOLD_FILES` 不含它），
   所以改它**不需要**重生成 `fixtures/manifest.json`；但 `paths.VECTOR_FILES` 要含它
   （`tests/test_package_data.py` 会断言"包里读得到"）。
7. **灰度公式只有一份**：`print/color.py` 的 `relative_luminance` / `channel_reflectance`；
   采样器与 M3 颜色检查都调它。**不许**在 `oracle/` 里抄第二份系数
   （阈值门会抓裸数字，但"抄一份 Decimal 字符串"它抓不到——这条靠审查）。
8. **位图哈希不含 PNG 字节**：`raster.bitmap_sha256` 哈希的是"尺寸 + 像素"，
   因为 `zlib` 输出跨 Python 版本可能不同；**改哈希面等于破坏"同输入同摘要"**。
9. **引擎只写名字与版本，不写可执行文件路径**（`Engine.describe()`）：报告不许带主机绝对
   路径（`data/README.md` §8.7 末条），`test_probe_takes_the_first_declared_candidate`
   断言 `describe()` 的键集合恰为 `{name, version, kind}`。
10. **真引擎路径本轮未验证**（本机 `zxing-cpp` / `ZXingReader` / `zbarimg` 实测全无）：
    命令模板（名字 + 参数）**未被观测过**，模板不匹配只会得到 `unusable`（不产 agreement）。
    三样本的"解出/解不出"由 `tests/test_oracle.py` 的**可注入替身**复现（替身读真实落盘的
    PNG 像素）—— 它验**管线**，不验阈值。**发布时说清楚**（`plan/05` §四、`data/README.md` §9）。
11. **`cli.DATA_ERRORS` 现在含 `oracle.layout.LayoutError`**：图案表装载失败走 exit 3
    （安装问题，不是关于条码的结论）。`oracle` 的计算在**写盘之前**，所以 `out/` 不存在时
    exit 3 且零副作用。
12. **`pyproject.toml` 里没有任何解码引擎的绑定**（`[project.optional-dependencies]` 只有
    `dev`）：本层只用 `shutil.which` + `subprocess` 探测外部命令。将来若要加引擎的 Python
    绑定，**必须**留成 extra 且**运行期不 import**，否则零第三方依赖红线破
    （`plan/HANDOFF-M5` §二.11、`plan/03` §七）——发布时别顺手把它塞进 `dependencies`。
13. **`tools/verify_gates.py` 的 L5 变异已改**（M5 收尾）：交接单通常在上一棒收尾时**预写**
    （`plan/HANDOFF-M6.md` 现在就在盘上，而 M6 还是 ⬜），所以 L5 改为"选中一个待办里程碑，
    **先删掉它的交接单**再在三处副本标 ✅"——变异仍是"标 ✅ 却缺交接单"这一件事。
    **发布棒不要删掉这段两态探测**。
14. **状态副本是 3 处**：`plan/00` 里程碑表、`plan/05` 状态表、`README.md` 状态表。
    翻 M6 ✅ 时**三处同提交改**，并同提交落 `plan/RELEASE-M6.md`（两栏 + 覆盖对账 + ≥3 条三态行），
    否则 `LAYOUT.RELEASE` 判红。
15. **`plan/06` 缺口表的缺口列**不得提已 ✅ 的里程碑号（`LAYOUT.GAPS`）；台账里带 `⬜`/`🟡`
    的行**不许在状态格里提已 ✅ 的里程碑号**（`LAYOUT.LEDGER`）——措辞要绕开编号。
16. **本轮没跑过 CI**。任何"绿"只能写**本地等价校验**，并注明"未接远端，CI 待首推验证"；
    首推后回填真实 run id。
17. **提交门会在每次提交时报一条 medium「跨文件污点」**（`cli.py` 的
    `argv → args.input → load_spec → open()`）。这是按 `plan/00` D22 登记的预期判定，
    发布留档（`plan/RELEASE-M6.md` §覆盖对账）按 D20 先例如实登记，别去"消掉"它。
18. **Python 3.8 通道本棒已双跑**：`py -3.8 -m pytest -q` = **299 passed**（与 3.12 同数）。
    发布棒若动 `src/` 或 `tests/`，必须再双跑（`tools/check_python_floor.py` 常驻守）。

## 三、下一棒待办（M6）

按顺序做，每步都有可落档的证据：

1. **重名核对（D13）**：PyPI 与 GitHub 上 `bpreflight` / `10-27-barcodepreflight` 是否被占用；
   被占则改名并留映射（结果写进 `plan/RELEASE-M6.md` tag 前事实栏）。
2. **干净环境验证**：新 venv + 中立目录 + `py -3.12 -m pip install`（真下载）+ README 逐条真敲
   （`check` / `report` / `oracle` / `--fail-on` / `--with-timestamp`）。逐条留输出。
3. **脱敏四步 + 产物扫描**：`tools/check_desensitized.py` 全绿；确认 `out/`、`fixtures/`、
   `*.png`、`dist/` 未入仓（`.gitignore` 已是白名单外的反向清单）。
4. **构建产物**：`py -3.12 -m build` → `sdist` + `wheel`；`twine check`；
   `SHA256SUMS`（两件产物各一行）。
5. **`git tag` + GitHub Release**：tag 前先把 `plan/RELEASE-M6.md`（含 §覆盖对账）落进 tag 树，
   tag 之后再追加"tag 后事实"栏。Release 附件 = `sdist` + `wheel` + `SHA256SUMS`。
6. **首次推送 + 回填 run id**：CI 首推后把真实 run id 回填进 `plan/05` §四与
   `plan/RELEASE-M6.md`（此前一律写"本地等价校验（未接远端）"）。
7. **`plan/RELEASE-M6.md` §覆盖对账**：阶段 7 出口门逐条三态（`实现` / `不适用 + 理由` /
   `待首推`），**含 D22 的读路径污点判定登记**（D20 先例）。
8. **三处状态副本翻 ✅ + `plan/00` 兑现记录 + `plan/06` 缺口收尾**，然后 commit + tag。

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
| K8 | `basis: engineering-heuristic` 项**没有** `status`，不参与未核降级 | `data/README.md` §8.2 末条 |
| K9 | 首屏三段字面固定（`VERDICT:` / `FINDINGS:` / `TOP FIX:`）+ **顺序**（前三行连续） | `report/render_md.py`；`tests/test_report_render.py` |
| K10 | 报告默认不读时钟；`--with-timestamp` 才标 `deterministic: false` 并给 `timestamp` | `pipeline.run` / `pipeline.utc_timestamp` |
| K11 | 运行期零第三方依赖、零网络；`tests/test_no_network.py` AST 守（含 `oracle/`） | `tests/test_no_network.py` |
| K12 | `requires-python >= 3.8`：`match` / `list[int]` 注解一律禁 | `tools/check_python_floor.py` |
| K13 | `target` 形状：M1 `ai:<ai>:<scope>`、M2 `symbol:<symbol>:<scope>`、M3 `quiet_zone.<side>` / `magnification` / `raster` / `bar_height` / `color.<probe>` | `gs1/validators.py`；`symbols/feasibility.py`；`print/*.py` |
| K14 | 数据层不可判三条出口：`reference_engine_absent` / `gcp_lookup_unavailable` / `module_not_implemented:<k>` | `pipeline.py`；`plan/00` D21 |
| K15 | M2 规则全部数据驱动 + 三态；`tie_break` 只实现 `longest-first` | `symbol_profiles.json`；`symbols/profiles.py` |
| K16 | `encoding_plan` 只在可编码时出现；`checksum` 的 GS1 值由 `gs1/checksum.py` 复核 | `symbols/feasibility.py` |
| K17 | 零静区是结构档：只读 `required`，`threshold_status` 恒 `not-applicable`，`severity` 恒 `error` | `print/quiet_zone.py` |
| K18 | 降级规则单点：只有 `print/common.py` 的两个构造函数能做降级 / 产 `not-applicable` | `print/common.py` |
| K19 | `symbol` 不属于"请求了印刷层"：`PRINT_INPUT_FIELDS` 不含它 | `input.py`；`print/audit.has_print_input` |
| K20 | fixture 清单与阈值册同摘要：改阈值必须同提交重生成 `fixtures/manifest.json` | `tools/gen_fixtures.py` |
| K21 | `timestamp` 是模型字段：格式固定 `YYYY-MM-DDTHH:MM:SSZ`（UTC），无时区名/主机名；默认缺席 | `report/model.Report.timestamp` |
| K22 | 渲染层零判定是两条判据：import 面 + 重算面（且带阳性对照） | `report/render_*.py`；`tests/test_report_render.py` |
| K23 | 退出码矩阵逐格一条测试：9 格不许 parametrize 压成 3 条；三类 `3` 从真实入口触发 | `tests/test_exit_codes.py` |
| K24 | `out/` 落点判据 = "字节等于 stdout" + "目录列表前后相等"；oracle 落点**单列一条** | `cli._write_fixed`；`tests/test_cli_contract.py` |
| **K25** | **M5 的 `agreement` 不参与 `verdict`**；`m3_laxer` 是 bug 通道，`m3_stricter` 入 `known-disagreements`；缺引擎 ⇒ `agreement` 键**缺席** | `oracle/`；`data/README.md` §8.8；`plan/00` D10 |
| **K26** | **引擎三态 `decoded`/`not-decoded`/`unusable`**：`unusable` 必须走 `skipped`，不许读成"解不出" | `oracle/zxing.py`；`tests/test_oracle.py` |
| **K27** | **采样器是纯函数且不抄第二份灰度系数**（复用 `print/color.py`；硬边、无随机、不读文件） | `oracle/sampler.py` |

## 五、本机环境坑（实测过的）

- **`python` / `python3` 是 Windows Store 占位符，执行即 exit 49**。一律 `py -3.12`
  （或 `py -3.8`）；输出中文加 `-X utf8`。
- **`py -3.12 -m bpreflight …` 需要 `PYTHONPATH=src`**（或先 `pip install -e .`）：
  `pyproject.toml` 的 `pythonpath` 只对 pytest 生效。
- `py -3.8` = 3.8.8，`py -3.12` = 3.12.10。本棒实测双通道均 **299 passed**。
- **本机没有任何候选解码引擎**（`zxing-cpp` / `ZXingReader` / `zbarimg` 的 `shutil.which` 全为
  `None`，M5 实测）。因此 `oracle` 的真实运行**只会**给出 `skipped: oracle_absent`；
  想看 agreement 三态请用 `tests/test_oracle.py` 的可注入替身或自备引擎。
- Git Bash 下 heredoc 与 `cd` 复合命令容易被环境包装截断——**写临时脚本文件再执行**比
  `python - <<EOF` 稳；临时文件放 `.tmp/`（已在 `.gitignore` 里）。
- **本机 Bash 工具拒绝"直接写源码/临时脚本"的写法**（安全钩子）：一律用 Write/Edit 提交文件，
  不要用 `cat > file <<EOF`。
- `grep -rc` / `ugrep -E` 在 Git Bash 下对复杂正则不稳。要判"某模式出现几次"就写进测试用 Python 数。
- `pytest` 通过 `pyproject.toml` 的 `pythonpath = ["src"]` 直接跑源码树，**不需要先安装**。
  `tools/gen_fixtures.py` 自己 `sys.path.insert(0, "src")`，所以未安装也能跑。

## 六、DoD 逐项 checklist（M6 完成时须全部打勾）

- [ ] 仓库名 / 包名重名核对（D13）完成并留档
- [ ] 干净环境验证：真下载 + 中立目录 + 新 venv + README 逐条真敲（输出留档）
- [ ] 脱敏四步 + 产物扫描；提交身份与 tagger 邮箱为 noreply
- [ ] `git tag` + GitHub Release（附 `sdist` + `wheel` + `SHA256SUMS`）
- [ ] `plan/RELEASE-M6.md` 两栏（tag 前事实 / tag 后追加）+ §覆盖对账（阶段 7 出口门逐条三态，含 D22 污点登记）
- [ ] 首次 CI 首推后回填真实 run id；此前一律写"本地等价校验（未接远端）"
- [ ] 三处状态副本同提交翻 ✅（`plan/00` / `plan/05` / `README.md`）
- [ ] 六道门 + `gen_fixtures.py --check` + `verify_gates.py` 全绿；`pytest` **3.8 / 3.12 双绿**

## 七、关键命令速查

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门
py -3.12 tools/check_thresholds.py        # 阈值零硬编码门（oracle/ 也在扫描面内）
py -3.12 tools/check_python_floor.py      # Python 下限门
py -3.12 tools/check_ci_workflow.py       # CI 工作流门
py -3.12 tools/gen_fixtures.py --check    # fixture 位级自检（第七道常规检查）
py -3.12 tools/verify_gates.py            # 门自检（32 组变异）
py -3.12 -m pytest -q                     # 全量测试（299 passed）
py -3.8  -m pytest -q                     # 3.8 通道（299 passed）
PYTHONPATH=src py -3.12 -X utf8 -m bpreflight check --input examples/spec-ean13.json
mkdir -p out && PYTHONPATH=src py -3.12 -X utf8 -m bpreflight oracle --input examples/spec-ean13.json
grep -rc "def gs1_check_digit" src/       # 必须 == 1
```

> 回读层三件：`oracle/sampler.py`（纯函数位图）/ `oracle/zxing.py`（外部引擎三态）/
> `oracle/agreement.py`（`agreement` 三态 + 两条归宿）。口径只在 `data/README.md` §8.8（agreement）
> 与 §8.9（`skipped` 词表）；图案表在 `data/vectors/sampler_patterns.json`（全部 `unverified`）。