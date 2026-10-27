# HANDOFF-M2 · 第 2 棒交接单（符号合法性）

> 上一棒：**M1 数据先行**（✅ 2026-10-27）
> 本棒目标：**M2 符号合法性**——符号 profile 表（数据驱动）+ 八符号的结构性可行性 +
> 容量/字符集/模式切换 + 跨符号等价性 + `encoding_plan` 切分唯一。
> 读法：**先跑布局门**（`AGENTS.md` 里的命令），绿了再读本文件。

## 一、当前进度与证据

M1 已完成并验证（**本地等价校验，未接远端，CI 待首推验证**）：

| 交付 | 证据（命令 + 结果） |
| --- | --- |
| 内嵌官方字典 | `src/bpreflight/data/gs1-syntax-dictionary/`（正文 + 上游 `LICENSE` + `NOTICE`），commit `c63d8a12` 钉版 |
| 字典身份可复算 | `py -3.12 -c "import hashlib,io;print(hashlib.sha256(io.open('src/bpreflight/data/gs1-syntax-dictionary/gs1-syntax-dictionary.txt','rb').read()).hexdigest())"` → `1ea02f4e…ffc94` |
| 整表解析 | `tests/test_gs1_semantics.py` → **224 条目 → 541 个具体 AI / 283 组件 / req 193 / ex 85**（行数逐条断言） |
| 四官方向量 | `tests/test_checksum.py` → `02345673` / `416000336108` / `09501101530003` / `4006381333931` 全 PASS |
| 校验位唯一实现 | 同上，AST + 文本双判据；`def gs1_check_digit` 出现次数 == 1（`gs1/checksum.py`） |
| `yymmd0` 对照对 | `(17)251200` → `dd00_last_day_of_month`(info) + 归一 `2025-12-31`；`(17)251301` → `invalid_date` |
| `req` / `ex` | `(10)` 单独报 / `(01)(10)` 不报；`(250)` 单独报 / `(01)(21)(250)` 不报 / `(01)(250)` 报；`(01)+(255)` 报、`(01)` 单独不报 |
| 全量测试 | `py -3.12 -m pytest -q` → **134 passed**；`py -3.8 -m pytest -q` → **134 passed** |
| 五道门 + 变异自检 | 四条常驻门全绿；`tools/verify_gates.py` → **23 组变异：符合预期 23 / 不符合 0** |
| 打包自足性 | `py -3.12 -m build --wheel` + 新 venv 装 wheel → 中立目录跑 `bpreflight check` 成功，`data/gs1-syntax-dictionary/*` 与 `data/vectors/*` 都在 wheel 里 |

**M1 的 DoD 在 `plan/05` §三（全部打勾）**。

## 二、当前事实·状态不变量（下一棒动手前必须知道）

1. **"没有判定 ⇒ 不敢说 pass"这条换了机制，但**没有**放宽**。
   `implementation_pending` 已退役（`plan/00` D16 兑现记录）。现在由两条不变式接管，
   `tests/test_pipeline_skeleton.py` 逐条守：
   - 该 id **不再作为字符串字面量**出现在 `src/`（AST 常量扫；注释里提到它是允许的）；
   - **有真实判定时 `verdict` 才可能 pass**：输入里没有可判的数据面时产
     `error: input_incomplete`（点名缺哪个字段），未实现的模块进 `skipped:
     module_not_implemented:<k>`。
2. **未实现模块的 `skipped` 必须在模块落地时收窄**。当前 M2/M3 都报
   `module_not_implemented:M2|M3`（由 `pipeline._module_skips` 依据"输入里出现没出现该模块的面"决定）。
   **M2 落地时要改三处**：`pipeline.IMPLEMENTED_MODULES`（加 `"M2"`）、`_module_skips`
   里删掉 M2 那一支、并同步改 `test_unimplemented_modules_are_announced_not_silent`
   （断言只剩 M3）。
3. **数据读取点一共三处，判定模块一处都不许有**（`plan/HANDOFF-M1` §二.3）：
   - `bpreflight/thresholds.py` —— 印刷阈值（`quiet_zone.json` / `gen_spec.json`）；
   - `bpreflight/gs1/dictionary.py` —— 字典正文 + `dict_manifest.json`（装载并复算摘要）；
   - `bpreflight/gs1/vectors.py` —— `data/vectors/gs1_vectors.json`（M1 向量与口径）。
   **判定模块接收装载好的对象**：`validators.validate_element_string(doc, issues, elements,
   resolution)` 的 `doc` 与 `resolution` 都是入参，函数体里没有 `open()` / `load()`。
   本棒踩过的坑（两处，都已修）：① `_check_date` 里给 `resolution=None` 兜底并现场
   `load_century_resolution()`；② `_check_parse_issues` 里现取 `dict_version()`。两处都会让
   "判定模块自己读文件"这条结构性质变成口头约定。
   `tools/check_thresholds.py` 会拦 `src/` 里的裸数值常量（允许集见 `ALLOWED_NUMBERS`，
   登记表 `REGISTERED` 目前仍是**空表**，请保持空）。另一个坑：写 `value[0:2]` /
   `value[4:6]` 这类**日期切片宽度**会被该门判红（`6` 不在允许集里）——改成从
   `yy_mm_dd` 宽度常量推导后自然消失。
4. **校验位只有一份实现**：`src/bpreflight/gs1/checksum.py::gs1_check_digit`。
   M2 要判符号校验位时**只能 import**。`tests/test_checksum.py::test_only_one_check_digit_implementation`
   同时扫 AST 与文本，复制第二份立刻红。
5. **`finding` 构造即校验**：`report/model.py` 的 `Finding.__init__` 拒绝 warn/error 无 `fix`、
   `evidence.kind` 非法、`threshold_status` 非法。**不要绕过它拼 dict**——M1 的每条 error 都带
   `fix`（`to` 是具体目标值，如"正确校验位的完整串"）。
6. **字典是第三方数据，改它要动三处**：正文、`data/vectors/dict_manifest.json` 的
   `sha256` + `dict_version`、`NOTICE`（本仓每次运行复算摘要，不符即 exit 3）。
7. **`data/README.md` §3 有过一处修正（本棒）**：`*` 的含义是"**定长且不需要 FNC1 分隔**"、
   `?` 是"**允许作为 Digital Link 数据属性**"，**不是**"必填 / 定长结束标志"。原表写错了，
   已按上游原话改正；引用这两个旗标时以 `data/README.md` §3 为准。
8. **状态副本是 3 处**：`plan/00` 里程碑表、`plan/05` 状态表、`README.md` 状态表。
   翻 M2 ✅ 时**三处同提交改**，否则布局门 `LAYOUT.STATUS` 红。
   台账（`plan/00` §四）里带 `⬜` 的行**不许在状态格里提已 ✅ 的里程碑号**（`LAYOUT.LEDGER` 会判红）。
9. **本轮没跑过 CI**。任何"绿"都只能写**本地等价校验**，并注明"未接远端，CI 待首推验证"。
   `plan/05` 与 `README` 已经这么写，别改成"CI 绿"。

## 三、下一棒待办（M2）

按顺序做，每步都有可跑红的判据：

1. **落 `src/bpreflight/data/vectors/symbol_profiles.json`**：八符号（`code128` / `gs1-128` /
   `ean13` / `ean8` / `upca` / `datamatrix` / `qr` / `code39`）的**字符集 / 容量 / 模式切换**规则，
   **全部是数据**，每项带 `source` / `status` / `verified_at`（⚠️ 本轮没取到规范原文，默认
   `status: "unverified"`，不许写成规范要求）。
2. **`src/bpreflight/symbols/profiles.py`**：读上表。代码只做"字符集 ⊆ / 长度 ∈ / 模式可覆盖"
   三段判定，**不手抄容量表**。
3. **`src/bpreflight/symbols/feasibility.py`**：产出
   `encoding_plan = {symbol, mode, segments[], total_modules, checksum}`；
   切分**唯一**，落 `tie_break: "longest-first"`。
4. **跨符号等价性 3 组**（`plan/05` M2 DoD 逐条）：
   - `012345678905`（12 位）/ `0012345678905`（13 位）/ `00012345678905`（14 位）→ 各自只在
     对应长度的符号下合格，**每个"不可"都要给具体原因**（字符集/长度/模式）；
   - `4006381333931`：`ean13` PASS、`upca` 不可 —— 原因写**长度/结构**，
     **不得**写"国家前缀不兼容"（前缀归属要 GEPIR 联网，属非目标）；
   - `(01)…(10)…`：`gs1-128` PASS；`code128` 缺 FNC1 → `gs1_data_missing_fnc1`。
5. **校验位不复制**：一律 `from bpreflight.gs1 import checksum`。
6. **接进 pipeline**：`module_not_implemented:M2` 收窄（见 §二.2），M2 findings 进报告，
   `ai_position` 与 `target` 的命名延续 M1 的 `ai:<ai>:<scope>` 风格。
7. **回写状态**：`plan/00` 台账 + 里程碑表、`plan/05` 状态表与 DoD、`README` 状态表（3 处同提交）。
8. **写 `plan/HANDOFF-M3.md`**（七节），然后 commit。

## 四、既定口径清单（K 编号 —— 动了会打挂测试）

| K | 约定 | 位置 |
| --- | --- | --- |
| K1 | 校验位算法唯一实现，`4 - W` 不是 `6 - W` | `data/README.md` §8.1；`gs1/checksum.py` |
| K2 | 向量只存"输入 + 期望"，期望由输入独立复算 | `data/vectors/gs1_vectors.json`；`tests/test_checksum.py` |
| K3 | `verdict` 只有 `pass/warn/fail` 三值；"不可判"走 `threshold_status`/`skipped`/降级 | `data/README.md` §8.8；`severity.py` |
| K4 | `Finding.fingerprint = sha256(id \\x1f module \\x1f target)[:16]`，**不含 severity** | `report/model.py` |
| K5 | `findings` 排序键 = `(module, ai_position, id)`，不是严重级别 | `report/model.py` |
| K6 | 退出码只在 `exitcodes.py` 定义；`3` 优先且不参与判定计数 | `data/README.md` §8.5 |
| K7 | 数值一律定点字符串（如 `"1.559"`），不从 JSON 读 float 再格式化 | `data/README.md` §8；`plan/03` §五 |
| K8 | `basis: engineering-heuristic` 项**没有** `status`，不参与未核降级 | `data/README.md` §8.2 末条 |
| K9 | 首屏三段字面固定（`VERDICT:` / `FINDINGS:` / `TOP FIX:`） | `report/render_md.py`；`tests/test_report_render.py` |
| K10 | 报告默认不读时钟；`--with-timestamp` 才标 `deterministic: false` | `pipeline.py`；`gs1/vectors.py`（世纪窗口固定在数据里） |
| K11 | 运行期零第三方依赖、零网络；`tests/test_no_network.py` AST 守 | `tests/test_no_network.py` |
| K12 | `requires-python >= 3.8`：3.10 的 `match`、3.9 的 `list[int]` 注解一律禁 | `tools/check_python_floor.py` |
| K13 | 元素串的 `ai_position` = 元素串内**序号**（0 起）；`target` = `ai:<ai>:<scope>`（M2 沿用） | `gs1/validators.py` |
| K14 | 数据层不可判的三条出口：`reference_engine_absent` / `gcp_lookup_unavailable` / `module_not_implemented:<k>` | `pipeline.py`；`plan/00` D21 |

## 五、本机环境坑（实测过的）

- **`python` / `python3` 是 Windows Store 占位符，执行即 exit 49**。一律 `py -3.12`
  （或 `py -3.8`）；输出中文加 `-X utf8`。
- **`py -3.12 -m bpreflight …` 需要 `PYTHONPATH=src`**（或先 `pip install -e .`）：
  `pyproject.toml` 的 `pythonpath` 只对 pytest 生效。本棒实测不设它 → `No module named bpreflight`。
- `py -3.8` = 3.8.8，`py -3.12` = 3.12.10，两者都装了 pytest。
- Git Bash 下 heredoc 与 `cd` 复合命令容易被环境包装截断——**写临时脚本文件再执行**比
  `python - <<EOF` 稳；临时文件放 `.tmp/`（已在 `.gitignore` 里）。
- **`grep -rc` / `ugrep -E` 在 Git Bash 下对复杂正则不稳**（本棒实测 `ugrep` 直接报
  "invalid syntax"）。要判"某模式出现几次"就写进测试用 Python 数。
- `pytest` 通过 `pyproject.toml` 的 `pythonpath = ["src"]` 直接跑源码树，**不需要先安装**；
  但"安装后仍能读到数据"这条另外由 `tests/test_package_data.py` + CI 的 pip install 覆盖。
  本棒另跑过一次**真装**：`py -3.12 -m build --wheel` + 新 venv + 中立目录跑 CLI（全绿）。

## 六、DoD 逐项 checklist（M2 完成时须全部打勾）

- [ ] 跨符号等价性 3 组逐条有**具体原因**（字符集/长度/模式），无"国家前缀"式措辞
- [ ] `012345678905` / `0012345678905` / `00012345678905` 三例各自只在对应长度的符号下合格
- [ ] `4006381333931`：`ean13` PASS、`upca` 不可（原因是长度/结构）
- [ ] `(01)…(10)…`：`gs1-128` PASS；`code128` 报 `gs1_data_missing_fnc1`
- [ ] `encoding_plan.segments` 切分唯一，落 `tie_break: "longest-first"`
- [ ] M2 内不出现第二份校验位实现（AST + 文本判据仍绿）
- [ ] `symbol_profiles.json` 每项带 `source` / `status` / `verified_at`（未核一律 `unverified`）
- [ ] `module_not_implemented:M2` 已收窄（pipeline + 测试同步改）
- [ ] 三处状态副本同提交翻 ✅
- [ ] `plan/HANDOFF-M3.md` 七节齐
- [ ] 四道门 + `verify_gates.py` 仍全绿；`pytest` 3.8 / 3.12 双绿

## 七、关键命令速查

```bash
py -3.12 tools/check_sprint_layout.py     # 布局门（第一件事）
py -3.12 tools/check_desensitized.py      # 脱敏门
py -3.12 tools/check_thresholds.py        # 阈值零硬编码门
py -3.12 tools/check_python_floor.py      # Python 下限门
py -3.12 tools/verify_gates.py            # 门自检（23 组变异）
py -3.12 -m pytest -q                     # 全量测试
py -3.8  -m pytest -q                     # 3.8 通道（语法回归）
PYTHONPATH=src py -3.12 -X utf8 -m bpreflight check --input examples/spec-ean13.json
grep -rc "def gs1_check_digit" src/       # 必须 == 1
```

> 语义向量与用例都在 `src/bpreflight/data/vectors/gs1_vectors.json`（带 `source` 字段）。
> 要看"字典里某条 AI 长什么样"，用 `py -3.12 -c "import sys;sys.path.insert(0,'src');from bpreflight.gs1 import dictionary;print(dictionary.load().require('01'))"`。